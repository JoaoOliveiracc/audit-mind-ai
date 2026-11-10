"""Nó de auditoria: um investigador ReAct por dimensão selecionada."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import hook_config
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from rich.console import Console

from ..config import get_settings
from ..events import emit as _emit  # nome local mantido: ponto de patch dos testes
from ..llm import get_llm
from ..prompts.templates import (
    DIMENSION_GUIDANCE,
    INVESTIGATOR_PROMPT,
    SALVAGE_PROMPT,
    STRUCTURE_PROMPT,
    VULN_SCAN_NOTE,
    WRAP_UP_NOTICE,
)
from ..state import AuditState, DimensionResult
from ..tools.filesystem import make_project_tools
from .dependency_scan import vuln_scan_enabled
from ._messages import content_text


_console = Console(stderr=True)

# Orçamento do investigador (G32/G44): AUDITOR_MAX_INVESTIGATOR_STEPS ≈ 2 passos por tool
# call → até steps // 2 chamadas do modelo. As _WRAP_UP_CALLS últimas recebem o aviso para
# concluir; ao fim, o middleware encerra com o NOSSO marcador (sem depender de texto upstream).
_WRAP_UP_CALLS = 2
BUDGET_EXHAUSTED_MARKER = "[auditor] orçamento de chamadas do modelo esgotado"
_TOOL_RESULT_CHARS = 2_000     # por resultado de ferramenta no histórico de resgate
_TRANSCRIPT_CHARS = 60_000     # teto do histórico de resgate (mantém o mais recente)
PARTIAL_PREFIX = "⚠️ Investigação parcial (orçamento de passos esgotado). "




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
            and content_text(last.content) == BUDGET_EXHAUSTED_MARKER)


def _condensed_transcript(messages: list) -> str:
    """Histórico enxuto para o resgate: textos do agente, chamadas e resultados truncados."""
    parts: list[str] = []
    for msg in messages:
        if isinstance(msg, AIMessage):
            text = content_text(msg.content).strip()
            if text and text != BUDGET_EXHAUSTED_MARKER:
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


def _model_calls(messages: list) -> int:
    """Chamadas do modelo já feitas = ``AIMessage``s no histórico (sem estado extra)."""
    return sum(1 for m in messages if isinstance(m, AIMessage))


class _BudgetMiddleware(AgentMiddleware):
    """Orçamento de chamadas do modelo para o investigador (substitui ``remaining_steps``).

    - ``wrap_model_call``: nas últimas ``_WRAP_UP_CALLS`` chamadas, acrescenta o aviso de
      conclusão ao fim da entrada (o system prompt continua primeiro).
    - ``before_model``: esgotado o orçamento, encerra com ``BUDGET_EXHAUSTED_MARKER`` —
      sem chegar ao ``recursion_limit``, que no ``create_agent`` lança e perde o histórico.
    """

    def __init__(self, max_model_calls: int) -> None:
        super().__init__()
        self.max_model_calls = max_model_calls

    @hook_config(can_jump_to=["end"])
    def before_model(self, state, runtime) -> dict[str, Any] | None:
        if _model_calls(state["messages"]) >= self.max_model_calls:
            return {"messages": [AIMessage(content=BUDGET_EXHAUSTED_MARKER)], "jump_to": "end"}
        return None

    def wrap_model_call(self, request, handler):
        if self.max_model_calls - _model_calls(request.messages) <= _WRAP_UP_CALLS:
            request = request.override(
                messages=[*request.messages, HumanMessage(content=WRAP_UP_NOTICE)]
            )
        return handler(request)


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
    if vuln_scan_enabled(state):   # DUP-01: CVEs de dependências vêm da varredura determinística
        prompt += "\n\n" + VULN_SCAN_NOTE
    max_calls = max(2, settings.max_investigator_steps // 2)
    # checkpointer=False (AD-001): o sub-agente nunca herda o checkpointer do grafo
    # pai — senão cada passo ReAct (com trechos de código) é persistido.
    agent = create_agent(llm, tools=tools, system_prompt=prompt,
                         middleware=[_BudgetMiddleware(max_calls)], checkpointer=False)
    result = agent.invoke(
        {"messages": [HumanMessage(
            content=f"Investigue e audite a dimensão '{dimension}' deste projeto.")]},
        # Rede de segurança: o _BudgetMiddleware encerra muito antes (≈ 3–4 nós por volta).
        config={"recursion_limit": 4 * max_calls + 10},
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
