"""Nó de auditoria: um investigador ReAct por dimensão selecionada."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.prebuilt import create_react_agent
from rich.console import Console

from ..config import get_settings
from ..llm import get_llm
from ..prompts.templates import (
    DIMENSION_GUIDANCE,
    INVESTIGATOR_PROMPT,
    SALVAGE_PROMPT,
    STRUCTURE_PROMPT,
    WRAP_UP_NOTICE,
)
from ..state import AuditState, DimensionResult
from ..tools.filesystem import make_project_tools
from ._messages import content_text

try:  # disponível apenas em versões recentes do LangGraph
    from langgraph.config import get_stream_writer
except ImportError:  # pragma: no cover
    get_stream_writer = None

_console = Console(stderr=True)

# Com remaining_steps ≤ este valor, o investigador recebe o aviso para concluir (G32).
# O loop ReAct consome 2 passos por tool call e o prebuilt aborta abaixo de 2.
_WRAP_UP_AT = 5

# Mensagem final do agente prebuilt quando o recursion_limit acaba com tool calls pendentes
# (langgraph.prebuilt.chat_agent_executor). Detalhe upstream — coberto por teste real.
_BUDGET_SENTINEL = "Sorry, need more steps to process this request."
_TOOL_RESULT_CHARS = 2_000     # por resultado de ferramenta no histórico de resgate
_TRANSCRIPT_CHARS = 60_000     # teto do histórico de resgate (mantém o mais recente)
PARTIAL_PREFIX = "⚠️ Investigação parcial (orçamento de passos esgotado). "


def _emit(data: dict) -> None:
    """Emite um evento no stream 'custom' do LangGraph (para a API/SSE).

    No-op seguro: fora de um run com stream_mode='custom' (ex.: CLI, testes),
    a escrita é simplesmente descartada.
    """
    if get_stream_writer is None:
        return
    try:
        get_stream_writer()(data)
    except Exception:
        pass


def _final_report(messages: list) -> str:
    """Extrai o texto do último ``AIMessage`` (o relatório final do investigador)."""
    for msg in reversed(messages):
        if not isinstance(msg, AIMessage):
            continue
        content = content_text(msg.content)  # alguns provedores retornam blocos
        if content.strip():
            return content
    return ""


def is_partial(result: DimensionResult) -> bool:
    """True se o relatório da dimensão veio do resgate (orçamento esgotado)."""
    return result.summary.startswith(PARTIAL_PREFIX)


def _budget_exhausted(messages: list) -> bool:
    last = messages[-1] if messages else None
    return (isinstance(last, AIMessage) and not last.tool_calls
            and content_text(last.content).strip() == _BUDGET_SENTINEL)


def _condensed_transcript(messages: list) -> str:
    """Histórico enxuto para o resgate: textos do agente, chamadas e resultados truncados."""
    parts: list[str] = []
    for msg in messages:
        if isinstance(msg, AIMessage):
            text = content_text(msg.content).strip()
            if text and text != _BUDGET_SENTINEL:
                parts.append(f"[investigador] {text}")
            for call in msg.tool_calls:
                args = json.dumps(call.get("args", {}), ensure_ascii=False)
                parts.append(f"[chamada] {call['name']}({args})")
        elif isinstance(msg, ToolMessage):
            text = content_text(msg.content)
            if len(text) > _TOOL_RESULT_CHARS:
                text = text[:_TOOL_RESULT_CHARS] + "\n… [truncado]"
            parts.append(f"[resultado {msg.name}]\n{text}")
    transcript = "\n\n".join(parts)
    return transcript[-_TRANSCRIPT_CHARS:]


def _salvage_report(llm, dimension: str, messages: list) -> str:
    """Uma chamada sem ferramentas que escreve o relatório com a evidência já coletada.

    O histórico (dado não confiável, vem do código auditado) vai delimitado; delimitadores
    dentro dele são neutralizados para não "fechar" o bloco. Histórico vazio → sem chamada.
    """
    transcript = _condensed_transcript(messages)
    if not transcript.strip():
        return ""
    transcript = transcript.replace("<historico>", "‹historico›").replace("</historico>", "‹/historico›")
    response = llm.invoke([
        SystemMessage(content=SALVAGE_PROMPT.format(dimension=dimension)),
        HumanMessage(content=f"<historico>\n{transcript}\n</historico>"),
    ])
    return content_text(response.content)


def _make_prompt(system: str):
    """Prompt-função do agente: system primeiro; aviso de conclusão perto do fim do orçamento.

    Roda dentro do nó do agente (``remaining_steps`` vem do estado), sem nó extra no
    grafo — ao contrário de ``pre_model_hook``, que consumiria passos do orçamento.
    """
    def prompt(state) -> list:
        messages = [SystemMessage(content=system), *state["messages"]]
        remaining = state.get("remaining_steps")
        if remaining is not None and remaining <= _WRAP_UP_AT:
            messages.append(HumanMessage(content=WRAP_UP_NOTICE))
        return messages
    return prompt


def _investigate_dimension(dimension: str, state: AuditState, tools, llm, settings) -> DimensionResult | None:
    """Investiga uma dimensão em duas fases desacopladas.

    Fase 1 — investigação: um agent ReAct usa as ferramentas para inspecionar o
    projeto e escreve um relatório textual (sem ``response_format``, evitando o
    passo terminal de structured-output que reenvia o histórico cheio de tool calls
    ao LLM). Fase 2 — estruturação: uma chamada isolada de ``with_structured_output``
    recebe apenas o texto do relatório (sem histórico de ferramentas) e o converte
    em ``DimensionResult``. Separar as fases elimina os erros de fronteira
    (tool call vazada / ``tool_calls`` sem resposta no histórico).
    """
    prompt = INVESTIGATOR_PROMPT.format(
        dimension=dimension,
        project_path=state["project_path"],
        guidance=DIMENSION_GUIDANCE.get(dimension, ""),
        focus_notes=state.get("plan", {}).get("focus_notes", ""),
        user_context=json.dumps(state.get("user_context", {}), ensure_ascii=False),
        stack_profile=json.dumps(state.get("stack_profile", {}), ensure_ascii=False),
    )
    # checkpointer=False (AD-001): o sub-agente nunca herda o checkpointer do grafo
    # pai — senão cada passo ReAct (com trechos de código) é persistido.
    agent = create_react_agent(llm, tools=tools, prompt=_make_prompt(prompt), checkpointer=False)
    result = agent.invoke(
        {"messages": [("user", f"Investigue e audite a dimensão '{dimension}' deste projeto.")]},
        config={"recursion_limit": settings.max_investigator_steps},
    )

    messages = result.get("messages", [])
    partial = _budget_exhausted(messages)
    # G32: orçamento esgotado → resgata o relatório em vez de descartar a investigação.
    report = _salvage_report(llm, dimension, messages) if partial else _final_report(messages)
    if not report.strip():
        return None

    structurer = llm.with_structured_output(DimensionResult)
    dimension_result = structurer.invoke([
        ("system", STRUCTURE_PROMPT.format(dimension=dimension)),
        ("user", report),
    ])
    if partial:
        dimension_result.summary = PARTIAL_PREFIX + dimension_result.summary
    return dimension_result


def audit_node(state: AuditState) -> dict:
    """Roda os investigadores das dimensões do plano em paralelo e agrega os achados.

    Cada investigador é I/O-bound (chamadas ao LLM), então rodam concorrentemente
    num thread pool (até ``AUDITOR_MAX_CONCURRENT_INVESTIGATORS``). O progresso
    (SSE/console) é emitido pela thread principal — onde o contexto do stream writer
    do LangGraph é válido — e a agregação final segue a ordem do plano
    (determinística, independente da ordem de conclusão).
    """
    settings = get_settings()
    root = Path(state["project_path"]).expanduser().resolve()
    tools = make_project_tools(root, settings)
    llm = get_llm(state.get("provider"), state.get("model"))

    dimensions = state.get("plan", {}).get("dimensions", [])
    total = len(dimensions)
    if not dimensions:
        return {"findings": [], "dimension_summaries": [], "status": "audited"}

    index_of = {dim: i for i, dim in enumerate(dimensions, start=1)}
    results: dict[str, DimensionResult | None] = {}
    errors: dict[str, str] = {}

    max_workers = max(1, min(settings.max_concurrent_investigators, total))
    _console.print(
        f"[cyan]›[/cyan] Auditando {total} dimensão(ões) "
        f"({max_workers} em paralelo): [bold]{', '.join(dimensions)}[/bold]"
    )
    for dim in dimensions:
        _emit({"type": "investigator", "dimension": dim, "status": "start",
               "index": index_of[dim], "total": total})

    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="investig") as pool:
        futures = {
            pool.submit(_investigate_dimension, dim, state, tools, llm, settings): dim
            for dim in dimensions
        }
        for future in as_completed(futures):
            dim = futures[future]
            idx = index_of[dim]
            try:
                dr = future.result()
            except Exception as exc:  # falha de uma dimensão não derruba as demais
                errors[dim] = str(exc)
                _console.print(f"[yellow]  aviso: falha ao auditar '{dim}': {exc}[/yellow]")
                _emit({"type": "investigator", "dimension": dim, "status": "error",
                       "index": idx, "total": total, "message": str(exc)})
                continue

            results[dim] = dr
            if dr is None:
                _emit({"type": "investigator", "dimension": dim, "status": "empty",
                       "index": idx, "total": total})
                continue
            if is_partial(dr):
                _console.print(f"[yellow]  ⚠ {len(dr.findings)} achado(s) em '{dim}' — investigação "
                               "parcial (orçamento de passos esgotado)[/yellow]")
            else:
                _console.print(f"[green]  ✓[/green] {len(dr.findings)} achado(s) em '{dim}'")
            _emit({"type": "investigator", "dimension": dim,
                   "status": "partial" if is_partial(dr) else "done",
                   "index": idx, "total": total, "findings_count": len(dr.findings)})

    # Agrega na ordem do plano (determinística, independente da conclusão).
    all_findings: list[dict] = []
    summaries: list[dict] = []
    for dim in dimensions:
        if dim in errors:
            summaries.append({"dimension": dim, "summary": f"Falha na análise: {errors[dim]}"})
            continue
        dr = results.get(dim)
        if dr is None:
            summaries.append({"dimension": dim, "summary": "Sem resultado estruturado."})
            continue
        for finding in dr.findings:
            finding.dimension = dim
            all_findings.append(finding.model_dump(mode="json"))
        summaries.append({"dimension": dim, "summary": dr.summary})

    return {
        "findings": all_findings,
        "dimension_summaries": summaries,
        "status": "audited",
    }
