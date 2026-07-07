"""Nó de planejamento: seleciona as dimensões de auditoria aplicáveis."""
from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import get_llm
from ..prompts.templates import PLANNING_PROMPT, SYSTEM_PERSONA
from ..state import AuditDimension, AuditPlan, AuditState

_VALID_DIMENSIONS = {d.value for d in AuditDimension}
_DEFAULT_DIMENSIONS = [
    AuditDimension.SECURITY.value,
    AuditDimension.QUALITY.value,
    AuditDimension.ARCHITECTURE.value,
    AuditDimension.TESTING.value,
    AuditDimension.DOCUMENTATION.value,
]


def planning_node(state: AuditState) -> dict:
    """Define o plano de auditoria (dimensões + notas de foco)."""
    llm = get_llm(state.get("provider"), state.get("model")).with_structured_output(AuditPlan)
    prompt = PLANNING_PROMPT.format(
        dimensions=", ".join(sorted(_VALID_DIMENSIONS)),
        stack_profile=json.dumps(state.get("stack_profile", {}), ensure_ascii=False, indent=2),
        user_context=json.dumps(state.get("user_context", {}), ensure_ascii=False, indent=2),
        user_goal=state.get("user_goal") or "(não especificado)",
    )
    plan: AuditPlan = llm.invoke(
        [SystemMessage(content=SYSTEM_PERSONA), HumanMessage(content=prompt)]
    )

    dimensions = [d for d in plan.dimensions if d in _VALID_DIMENSIONS]
    if not dimensions:
        dimensions = list(_DEFAULT_DIMENSIONS)

    return {
        "plan": {"dimensions": dimensions, "focus_notes": plan.focus_notes},
        "status": "planned",
    }
