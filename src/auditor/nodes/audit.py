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

_console = Console(stderr=True)


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

    for dim in dimensions:
        _console.print(f"[cyan]›[/cyan] Auditando dimensão: [bold]{dim}[/bold] …")
        try:
            dr = _investigate_dimension(dim, state, tools, llm, settings)
        except Exception as exc:  # investigação de uma dimensão não deve derrubar tudo
            _console.print(f"[yellow]  aviso: falha ao auditar '{dim}': {exc}[/yellow]")
            summaries.append({"dimension": dim, "summary": f"Falha na análise: {exc}"})
            continue

        if dr is None:
            summaries.append({"dimension": dim, "summary": "Sem resultado estruturado."})
            continue

        for finding in dr.findings:
            finding.dimension = dim
            all_findings.append(finding.model_dump(mode="json"))
        summaries.append({"dimension": dim, "summary": dr.summary})
        _console.print(f"[green]  ✓[/green] {len(dr.findings)} achado(s) em '{dim}'")

    return {
        "findings": all_findings,
        "dimension_summaries": summaries,
        "status": "audited",
    }
