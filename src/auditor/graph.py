"""Construção do grafo de auditoria (LangGraph).

Fluxo:

    START → discovery → plan_questions → clarify ─(interrupt)→ planning
          → audit → verify → adversarial → synthesis → report → END

O nó ``verify`` confere no disco a evidência de cada achado (anti-alucinação),
descartando os não-substanciados. O nó ``adversarial`` (opcional) usa um juiz LLM
cético que tenta refutar cada achado elegível antes da síntese/relatório.

O nó ``clarify`` usa ``interrupt`` para o human-in-the-loop; um checkpointer é
necessário para pausar e retomar a execução.
"""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import (
    adversarial_node,
    audit_node,
    clarify_node,
    discovery_node,
    plan_questions_node,
    planning_node,
    report_node,
    synthesis_node,
    verify_node,
)
from .state import AuditState


def build_graph(checkpointer=None):
    """Compila e retorna o grafo do agent.

    Args:
        checkpointer: checkpointer do LangGraph. Se ``None``, usa ``MemorySaver``
            (necessário para suportar ``interrupt`` no fluxo de esclarecimento).
    """
    graph = StateGraph(AuditState)

    graph.add_node("discovery", discovery_node)
    graph.add_node("plan_questions", plan_questions_node)
    graph.add_node("clarify", clarify_node)
    graph.add_node("planning", planning_node)
    graph.add_node("audit", audit_node)
    graph.add_node("verify", verify_node)
    graph.add_node("adversarial", adversarial_node)
    graph.add_node("synthesis", synthesis_node)
    graph.add_node("report", report_node)

    graph.add_edge(START, "discovery")
    graph.add_edge("discovery", "plan_questions")
    graph.add_edge("plan_questions", "clarify")
    graph.add_edge("clarify", "planning")
    graph.add_edge("planning", "audit")
    graph.add_edge("audit", "verify")
    graph.add_edge("verify", "adversarial")
    graph.add_edge("adversarial", "synthesis")
    graph.add_edge("synthesis", "report")
    graph.add_edge("report", END)

    return graph.compile(checkpointer=checkpointer or MemorySaver())
