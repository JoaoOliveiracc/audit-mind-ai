"""Nó de auditoria: um investigador ReAct por dimensão selecionada."""
from __future__ import annotations

import json
from pathlib import Path

from langgraph.prebuilt import create_react_agent
from rich.console import Console

from ..config import get_settings
from ..llm import get_llm
from ..prompts.templates import DIMENSION_GUIDANCE, INVESTIGATOR_PROMPT
from ..state import AuditState, DimensionResult
from ..tools.filesystem import make_project_tools

try:  # disponível apenas em versões recentes do LangGraph
    from langgraph.config import get_stream_writer
except ImportError:  # pragma: no cover
    get_stream_writer = None

_console = Console(stderr=True)


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


def _investigate_dimension(dimension: str, state: AuditState, tools, llm, settings) -> DimensionResult | None:
    """Executa um agent ReAct focado em uma dimensão e retorna o resultado estruturado."""
    prompt = INVESTIGATOR_PROMPT.format(
        dimension=dimension,
        project_path=state["project_path"],
        guidance=DIMENSION_GUIDANCE.get(dimension, ""),
        focus_notes=state.get("plan", {}).get("focus_notes", ""),
        user_context=json.dumps(state.get("user_context", {}), ensure_ascii=False),
        stack_profile=json.dumps(state.get("stack_profile", {}), ensure_ascii=False),
    )
    agent = create_react_agent(
        llm,
        tools=tools,
        prompt=prompt,
        response_format=DimensionResult,
    )
    result = agent.invoke(
        {"messages": [("user", f"Investigue e audite a dimensão '{dimension}' deste projeto.")]},
        config={"recursion_limit": settings.max_investigator_steps},
    )
    return result.get("structured_response")


def audit_node(state: AuditState) -> dict:
    """Roda os investigadores para cada dimensão do plano e agrega os achados."""
    settings = get_settings()
    root = Path(state["project_path"]).expanduser().resolve()
    tools = make_project_tools(root, settings)
    llm = get_llm()

    dimensions = state.get("plan", {}).get("dimensions", [])
    all_findings: list[dict] = []
    summaries: list[dict] = []

    total = len(dimensions)
    for idx, dim in enumerate(dimensions, start=1):
        _console.print(f"[cyan]›[/cyan] Auditando dimensão: [bold]{dim}[/bold] …")
        _emit({"type": "investigator", "dimension": dim, "status": "start",
               "index": idx, "total": total})
        try:
            dr = _investigate_dimension(dim, state, tools, llm, settings)
        except Exception as exc:  # investigação de uma dimensão não deve derrubar tudo
            _console.print(f"[yellow]  aviso: falha ao auditar '{dim}': {exc}[/yellow]")
            summaries.append({"dimension": dim, "summary": f"Falha na análise: {exc}"})
            _emit({"type": "investigator", "dimension": dim, "status": "error",
                   "index": idx, "total": total, "message": str(exc)})
            continue

        if dr is None:
            summaries.append({"dimension": dim, "summary": "Sem resultado estruturado."})
            _emit({"type": "investigator", "dimension": dim, "status": "empty",
                   "index": idx, "total": total})
            continue

        for finding in dr.findings:
            finding.dimension = dim
            all_findings.append(finding.model_dump(mode="json"))
        summaries.append({"dimension": dim, "summary": dr.summary})
        _console.print(f"[green]  ✓[/green] {len(dr.findings)} achado(s) em '{dim}'")
        _emit({"type": "investigator", "dimension": dim, "status": "done",
               "index": idx, "total": total, "findings_count": len(dr.findings)})

    return {
        "findings": all_findings,
        "dimension_summaries": summaries,
        "status": "audited",
    }
