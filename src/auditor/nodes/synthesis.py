"""Nó de síntese: pontua a saúde do projeto e escreve o resumo executivo."""
from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import get_llm
from ._messages import content_text
from ..prompts.templates import SYNTHESIS_PROMPT, SYSTEM_PERSONA
from ..scoring import compute_health_score, severity_counts  # reexportados (compat.)
from ..state import AuditState

__all__ = ["compute_health_score", "severity_counts", "synthesis_node"]


def synthesis_node(state: AuditState) -> dict:
    """Gera pontuação de saúde e resumo executivo consolidado."""
    findings = state.get("findings", [])
    score = compute_health_score(findings)
    counts = severity_counts(findings)

    llm = get_llm(state.get("provider"), state.get("model"))
    prompt = SYNTHESIS_PROMPT.format(
        user_goal=state.get("user_goal") or "(não especificado)",
        user_context=json.dumps(state.get("user_context", {}), ensure_ascii=False),
        stack_profile=json.dumps(state.get("stack_profile", {}), ensure_ascii=False),
        health_score=score,
        dimension_summaries=json.dumps(state.get("dimension_summaries", []), ensure_ascii=False, indent=2),
        severity_counts=json.dumps(counts, ensure_ascii=False),
    )
    response = llm.invoke(
        [SystemMessage(content=SYSTEM_PERSONA), HumanMessage(content=prompt)]
    )
    summary_text = content_text(response.content)

    return {
        "health_score": score,
        "executive_summary": summary_text,
        "status": "synthesized",
    }
