"""Nó de síntese: pontua a saúde do projeto e escreve o resumo executivo."""
from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import get_llm
from ._messages import content_text
from ..prompts.templates import SYNTHESIS_PROMPT, SYSTEM_PERSONA
from ..scoring import compute_health_score, dependency_penalty_line, score_with_breakdown, severity_counts
from ..state import AuditState

__all__ = ["compute_health_score", "severity_counts", "synthesis_node"]  # reexportados (compat.)


def synthesis_node(state: AuditState) -> dict:
    """Gera pontuação de saúde e resumo executivo consolidado."""
    findings = state.get("findings", [])
    score, dp = score_with_breakdown(findings)     # nota e detalhamento da mesma conta (SCORE-06)
    breakdown = dp._asdict()
    counts = severity_counts(findings)
    explanation = dependency_penalty_line(breakdown)

    llm = get_llm(state.get("provider"), state.get("model"))
    prompt = SYNTHESIS_PROMPT.format(
        user_goal=state.get("user_goal") or "(não especificado)",
        user_context=json.dumps(state.get("user_context", {}), ensure_ascii=False),
        stack_profile=json.dumps(state.get("stack_profile", {}), ensure_ascii=False),
        health_score=score,
        dependency_penalty_line=f"\n{explanation}" if explanation else "",
        dimension_summaries=json.dumps(state.get("dimension_summaries", []), ensure_ascii=False, indent=2),
        severity_counts=json.dumps(counts, ensure_ascii=False),
    )
    response = llm.invoke(
        [SystemMessage(content=SYSTEM_PERSONA), HumanMessage(content=prompt)]
    )
    summary_text = content_text(response.content)

    return {
        "health_score": score,
        "dependency_penalty": breakdown,
        "executive_summary": summary_text,
        "status": "synthesized",
    }
