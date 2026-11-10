"""Nós sem teste até o G39 (spec: .specs/features/coverage-and-e2e — DISC/PQ/CL/PL)."""
from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from auditor.nodes import clarify, discovery, planning
from auditor.state import AuditPlan, AuditState, ClarifyingQuestion, ClarifyingQuestions


class _Structured:
    def __init__(self, result, sink: list):
        self.result, self.sink = result, sink

    def invoke(self, messages):
        self.sink.append(messages)
        return self.result


class _LLM:
    """LLM falso: devolve ``result`` na saída estruturada e registra as entradas."""

    def __init__(self, result):
        self.result, self.calls, self.schemas = result, [], []

    def with_structured_output(self, schema):
        self.schemas.append(schema)
        return _Structured(self.result, self.calls)


# --- DISC ------------------------------------------------------------------------------
def test_disc01_valid_project(tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text("def test(): pass\n", encoding="utf-8")

    out = discovery.discovery_node({"project_path": str(tmp_path)})

    assert out["status"] == "discovered"
    assert out["stack_profile"]["languages"]["Python"] == 2
    assert out["stack_profile"]["has_tests"] is True
    assert "app.py" in out["inventory"] and "test_app.py" in out["inventory"]


def test_disc02_invalid_path_raises(tmp_path):
    with pytest.raises(ValueError):
        discovery.discovery_node({"project_path": str(tmp_path / "nao-existe")})


# --- PQ --------------------------------------------------------------------------------
def test_pq01_skip_questions_never_calls_llm(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("LLM não deveria ser chamado")

    monkeypatch.setattr(clarify, "get_llm", boom)
    assert clarify.plan_questions_node({"skip_questions": True}) == {"clarifying_questions": []}


def test_pq02_returns_questions_and_truncates_inventory(monkeypatch):
    llm = _LLM(ClarifyingQuestions(questions=[ClarifyingQuestion(question="Produção?",
                                                                 rationale="foco")]))
    monkeypatch.setattr(clarify, "get_llm", lambda *a, **k: llm)

    out = clarify.plan_questions_node({"skip_questions": False, "inventory": "X" * 10_000,
                                       "stack_profile": {}, "user_goal": ""})

    assert out == {"clarifying_questions": [{"question": "Produção?", "rationale": "foco"}]}
    assert llm.schemas == [ClarifyingQuestions]
    prompt = llm.calls[0][-1].content
    assert "X" * 6_000 in prompt and "X" * 6_001 not in prompt


# --- CL --------------------------------------------------------------------------------
QS = [{"question": "Q1?", "rationale": "r1"}, {"question": "Q2?", "rationale": "r2"}]


def _clarify_graph():
    b = StateGraph(AuditState)
    b.add_node("clarify", clarify.clarify_node)
    b.add_edge(START, "clarify")
    b.add_edge("clarify", END)
    return b.compile(checkpointer=MemorySaver())


def test_cl01_no_questions_no_interrupt():
    out = clarify.clarify_node({"clarifying_questions": [], "user_context": {"a": "b"}})
    assert out == {"user_context": {"a": "b"}, "status": "clarified"}


@pytest.mark.parametrize("answers, expected", [
    ({"Q1?": "sim", "Q2?": 3}, {"Q1?": "sim", "Q2?": "3"}),           # dict → str
    (["sim", "não", "extra"], {"Q1?": "sim", "Q2?": "não"}),         # lista por posição
    ("texto solto", {}),                                              # outro → {}
])
def test_cl02_interrupt_payload_and_resume_formats(answers, expected):
    graph = _clarify_graph()
    cfg = {"configurable": {"thread_id": "cl"}}

    chunks = list(graph.stream({"clarifying_questions": QS}, cfg, stream_mode="updates"))
    interrupt = chunks[-1]["__interrupt__"][0].value
    assert interrupt == {"type": "clarifying_questions", "questions": QS}

    list(graph.stream(Command(resume=answers), cfg, stream_mode="updates"))
    values = graph.get_state(cfg).values
    assert values["user_context"] == expected
    assert values["status"] == "clarified"


# --- PL --------------------------------------------------------------------------------
def test_pl01_keeps_valid_dimensions_in_order_and_focus(monkeypatch):
    llm = _LLM(AuditPlan(dimensions=["testing", "nao-existe", "security"], focus_notes="foco X"))
    monkeypatch.setattr(planning, "get_llm", lambda *a, **k: llm)

    out = planning.planning_node({"stack_profile": {}, "user_context": {}})

    assert out == {"plan": {"dimensions": ["testing", "security"], "focus_notes": "foco X"},
                   "status": "planned"}


def test_pl02_falls_back_to_default_dimensions(monkeypatch):
    llm = _LLM(AuditPlan(dimensions=["inventada"], focus_notes=""))
    monkeypatch.setattr(planning, "get_llm", lambda *a, **k: llm)

    out = planning.planning_node({})

    assert out["plan"]["dimensions"] == ["security", "quality", "architecture", "testing",
                                         "documentation"]
