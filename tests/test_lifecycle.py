"""Ciclo de vida de auditorias órfãs (spec: .specs/features/api-hardening — ORPH-01, RES-01..03)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from auditor.api import main as api_main
from auditor.api.store import AuditStore

_STATUSES = ["started", "running", "waiting_input", "completed", "error"]


def _store_with_all_statuses(tmp_path) -> AuditStore:
    store = AuditStore(tmp_path / "meta.sqlite")
    for s in _STATUSES:
        store.create(s, "/proj", None, "p", "m")
        store.update(s, status=s)
    return store


# --- ORPH-01 (store) -----------------------------------------------------------------
def test_mark_orphans_interrupted_changes_only_non_terminal(tmp_path):
    store = _store_with_all_statuses(tmp_path)

    changed = store.mark_orphans_interrupted()

    assert changed == 3
    assert {s: store.get(s)["status"] for s in _STATUSES} == {
        "started": "interrupted", "running": "interrupted", "waiting_input": "interrupted",
        "completed": "completed", "error": "error",
    }


# --- ORPH-01 (subida da API) ---------------------------------------------------------
def test_api_startup_reconciles_orphans(tmp_path, monkeypatch):
    store = _store_with_all_statuses(tmp_path)
    monkeypatch.setattr(api_main, "get_store", lambda: store)

    with TestClient(api_main.app, base_url="http://localhost"):  # dispara o lifespan
        pass

    assert store.get("running")["status"] == "interrupted"
    assert store.get("waiting_input")["status"] == "interrupted"
    assert store.get("completed")["status"] == "completed"


# --- RES-01..03: AuditRunner(resume=True) sobre um grafo real com checkpointer -------
from typing import Any, TypedDict  # noqa: E402

from langgraph.checkpoint.memory import MemorySaver  # noqa: E402
from langgraph.graph import END, START, StateGraph  # noqa: E402
from langgraph.types import interrupt  # noqa: E402

from auditor.api.runner import AuditRunner  # noqa: E402

QUESTIONS = [{"question": "Vai para produção?", "rationale": "foco"}]


class _St(TypedDict, total=False):
    answers: Any
    findings: list
    health_score: int
    report_html_path: str
    report_markdown_path: str
    report_sarif_path: str


class _RecStore:
    def __init__(self):
        self.updates: list[dict] = []

    def update(self, audit_id, **fields):
        self.updates.append(fields)

    def last(self, key):
        return next(u[key] for u in reversed(self.updates) if key in u)


def _graph(runs: list[str], *, interrupt_before=None):
    def ask(_s):
        runs.append("ask")
        return {"answers": interrupt({"type": "clarifying_questions", "questions": QUESTIONS})}

    def finish(s):
        runs.append("finish")
        return {"findings": [{"severity": "high"}], "health_score": 80,
                "report_html_path": "/r/a.html", "report_markdown_path": "/r/a.md",
                "report_sarif_path": "/r/a.sarif"}

    b = StateGraph(_St)
    b.add_node("ask", ask)
    b.add_node("finish", finish)
    b.add_edge(START, "ask")
    b.add_edge("ask", "finish")
    b.add_edge("finish", END)
    return b.compile(checkpointer=MemorySaver(), interrupt_before=interrupt_before)


CFG = {"configurable": {"thread_id": "x"}}


def _wait(cond, timeout=5.0):
    import time
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_resume_with_pending_clarification_reasks_and_completes():
    runs: list[str] = []
    graph = _graph(runs)
    list(graph.stream({}, CFG))  # processo "morre" parado no interrupt
    store = _RecStore()

    runner = AuditRunner("x", graph, store, None, resume=True)
    runner.start()
    assert _wait(lambda: any(e["event"] == "clarification" for e in runner.log))
    assert _wait(lambda: any(u.get("status") == "waiting_input" for u in store.updates))

    clar = next(e for e in runner.log if e["event"] == "clarification")
    assert clar["data"]["questions"] == QUESTIONS
    assert store.last("status") == "waiting_input"

    runner.submit_answers({"Vai para produção?": "sim"})
    assert runner.done.wait(5)
    assert store.last("status") == "completed"
    assert graph.get_state(CFG).values["answers"] == {"Vai para produção?": "sim"}
    assert runs.count("finish") == 1


def test_resume_with_pending_node_continues_from_checkpoint():
    runs: list[str] = []
    graph = _graph(runs, interrupt_before=["ask"])
    list(graph.stream({}, CFG))  # parou antes de "ask": nó pendente, sem interrupt
    graph.update_state(CFG, {"answers": "pre"}, as_node="ask")  # ask "concluído"; finish pendente
    assert graph.get_state(CFG).next == ("finish",)
    store = _RecStore()

    runner = AuditRunner("x", graph, store, None, resume=True)
    runner.start()
    assert runner.done.wait(5)

    assert runs == ["finish"]
    assert store.last("status") == "completed"
    assert store.last("health_score") == 80
    assert not any(e["event"] == "clarification" for e in runner.log)


def test_resume_with_nothing_pending_only_finalizes():
    runs: list[str] = []
    graph = _graph(runs)
    list(graph.stream({}, CFG))
    from langgraph.types import Command
    list(graph.stream(Command(resume={"q": "a"}), CFG))  # grafo concluído, metadados não
    runs.clear()
    store = _RecStore()

    runner = AuditRunner("x", graph, store, None, resume=True)
    runner.start()
    assert runner.done.wait(5)

    assert runs == []
    assert not any(e["event"] == "phase" for e in runner.log)
    assert store.last("status") == "completed"
    assert store.last("report_html") == "/r/a.html"
    assert store.last("report_sarif") == "/r/a.sarif"
    assert store.last("health_score") == 80
