"""LLM falso determinístico para os testes de ponta a ponta (sem rede, sem chave).

Injetado via ``auditor.llm._build_llm`` — a fábrica única por trás de todo ``get_llm``.
Sem estado mutável (decide pela entrada), então é seguro entre threads.
"""
from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda

from auditor.state import (
    AuditPlan,
    ClarifyingQuestion,
    ClarifyingQuestions,
    DimensionResult,
    Finding,
    Verdict,
)

QUESTION = "O projeto vai para produção?"
SUMMARY = "Resumo executivo E2E: um segredo hardcoded encontrado."
FINDING_TITLE = "Senha hardcoded em app.py"
EVIDENCE = "PASSWORD = 'hardcoded-secret'"
PROJECT_SOURCE = f"{EVIDENCE}\n\ndef run():\n    return 1\n"

_STRUCTURED: dict[type, Any] = {
    ClarifyingQuestions: ClarifyingQuestions(questions=[ClarifyingQuestion(question=QUESTION,
                                                                           rationale="foco")]),
    AuditPlan: AuditPlan(dimensions=["security"], focus_notes="segredos"),
    DimensionResult: DimensionResult(dimension="security", summary="Segredo hardcoded.", findings=[
        Finding(dimension="security", title=FINDING_TITLE, severity="high",
                description="Credencial no código-fonte.", recommendation="Usar variável de ambiente.",
                file="app.py", line=1, evidence=EVIDENCE, confidence=0.9)]),
    Verdict: Verdict(verdict="confirmed", rationale="trecho confere", confidence=0.9),
}


class FakeLLM(BaseChatModel):
    bound: bool = False

    @property
    def _llm_type(self) -> str:
        return "fake-e2e"

    def bind_tools(self, tools, **kwargs):
        names = {getattr(t, "name", None) for t in tools}
        if "read_file" not in names:  # pega ferramenta renomeada/removida na ligação
            raise AssertionError(f"read_file ausente das tools do investigador: {names}")
        return self.model_copy(update={"bound": True})

    def with_structured_output(self, schema, **kwargs):
        result = _STRUCTURED[schema]

        def structured(messages):
            if schema is DimensionResult:  # o relatório do investigador precisa chegar aqui
                text = " ".join(str(getattr(m, "content", m[-1] if isinstance(m, tuple) else m))
                                for m in messages)
                if EVIDENCE not in text:
                    raise AssertionError("relatório do investigador não chegou ao estruturador")
            return result.model_copy(deep=True)

        return RunnableLambda(structured)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        if not self.bound:  # chamadas simples (síntese)
            reply = AIMessage(content=SUMMARY)
        elif isinstance(messages[-1], ToolMessage):  # investigador: já leu o arquivo → relatório
            reply = AIMessage(content=f"Relatório: {FINDING_TITLE} (app.py:1) — {EVIDENCE}")
        else:  # investigador: primeira volta → lê o arquivo
            reply = AIMessage(content="", tool_calls=[{"name": "read_file",
                                                       "args": {"path": "app.py"}, "id": "c1"}])
        return ChatResult(generations=[ChatGeneration(message=reply)])
