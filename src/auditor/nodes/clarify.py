"""Nós de esclarecimento: gera perguntas e coleta respostas via human-in-the-loop."""
from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt

from ..llm import get_llm
from ..prompts.templates import CLARIFY_PROMPT, SYSTEM_PERSONA
from ..state import AuditState, ClarifyingQuestions


def plan_questions_node(state: AuditState) -> dict:
    """Gera perguntas de esclarecimento com base na descoberta.

    Isolado do nó de interrupção para não repetir a chamada ao LLM quando o
    grafo é retomado após o ``interrupt``. Em modo não interativo
    (``skip_questions``), evita a chamada ao LLM por completo.
    """
    if state.get("skip_questions"):
        return {"clarifying_questions": []}

    llm = get_llm().with_structured_output(ClarifyingQuestions)
    prompt = CLARIFY_PROMPT.format(
        user_goal=state.get("user_goal") or "(não especificado)",
        stack_profile=json.dumps(state.get("stack_profile", {}), ensure_ascii=False, indent=2),
        inventory=state.get("inventory", "")[:6000],
    )
    result: ClarifyingQuestions = llm.invoke(
        [SystemMessage(content=SYSTEM_PERSONA), HumanMessage(content=prompt)]
    )
    return {"clarifying_questions": [q.model_dump() for q in result.questions]}


def clarify_node(state: AuditState) -> dict:
    """Pausa o grafo e solicita respostas ao usuário (human-in-the-loop).

    Se não houver perguntas, segue sem interromper. As respostas são fornecidas
    pela camada de interface via ``Command(resume=...)``.
    """
    questions = state.get("clarifying_questions") or []
    if not questions:
        return {"user_context": state.get("user_context", {}), "status": "clarified"}

    answers = interrupt(
        {
            "type": "clarifying_questions",
            "questions": questions,
        }
    )

    # ``answers`` pode vir como dict {pergunta: resposta} ou lista alinhada.
    if isinstance(answers, dict):
        user_context = {str(k): str(v) for k, v in answers.items()}
    elif isinstance(answers, list):
        user_context = {
            questions[i]["question"]: str(ans)
            for i, ans in enumerate(answers)
            if i < len(questions)
        }
    else:
        user_context = {}

    return {"user_context": user_context, "status": "clarified"}
