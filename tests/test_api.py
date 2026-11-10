"""Testes da API que não dependem do LLM (via TestClient)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from auditor.api.main import app
from auditor.api.runner import _counts

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_providers_lists_deepseek():
    r = client.get("/providers")
    assert r.status_code == 200
    names = {p["provider"] for p in r.json()}
    assert {"anthropic", "deepseek", "ollama"}.issubset(names)
    ds = next(p for p in r.json() if p["provider"] == "deepseek")
    assert ds["credential_env"] == "DEEPSEEK_API_KEY"


def test_create_audit_invalid_path():
    r = client.post("/audits", json={"project_path": "/caminho/que/nao/existe"})
    assert r.status_code == 400


def test_get_missing_audit_404():
    assert client.get("/audits/inexistente").status_code == 404


def test_counts_helper():
    findings = [{"severity": "high"}, {"severity": "high"}, {"severity": "low"}]
    assert _counts(findings) == {"high": 2, "low": 1}


# --- Fluxo de streaming + human-in-the-loop (F2/F3), sem LLM ---------------- #
import time  # noqa: E402

from langgraph.types import Command  # noqa: E402

from auditor.api.runner import AuditRunner  # noqa: E402


class _Intr:
    def __init__(self, value):
        self.value = value


class _State:
    def __init__(self, values):
        self.values = values


class FakeGraph:
    """Grafo mínimo que simula progresso, interrupt e retomada."""

    def __init__(self):
        self.calls = 0

    def stream(self, graph_input, config, stream_mode=None):
        self.calls += 1
        if self.calls == 1:
            yield ("updates", {"discovery": {"status": "discovered"}})
            yield ("custom", {"type": "investigator", "dimension": "security",
                              "status": "done", "findings_count": 1})
            yield ("updates", {"__interrupt__": (
                _Intr({"questions": [{"question": "Produção?", "rationale": "r"}]}),)})
        else:
            assert isinstance(graph_input, Command)
            yield ("updates", {"report": {"status": "completed"}})

    def get_state(self, config):
        return _State({"health_score": 80, "findings": [{"severity": "high"}]})


class FakeStore:
    def __init__(self):
        self.updates = []

    def update(self, audit_id, **fields):
        self.updates.append(fields)


def test_runner_streaming_and_human_in_the_loop():
    runner = AuditRunner("t1", FakeGraph(), FakeStore(), {"skip_questions": False})
    runner.start()

    # aguarda o evento de esclarecimento (interrupt)
    for _ in range(60):
        if any(e["event"] == "clarification" for e in runner.log):
            break
        time.sleep(0.05)

    events = [e["event"] for e in runner.log]
    assert "phase" in events            # discovery
    assert "investigator" in events     # stream custom por dimensão
    assert "clarification" in events    # interrupt
    assert not runner.done.is_set()     # pausado, aguardando resposta

    # responde e retoma
    runner.submit_answers({"Produção?": "sim"})
    assert runner.done.wait(timeout=5)

    events = [e["event"] for e in runner.log]
    assert "completed" in events
    assert events[-1] == "__end__"


# --- DELETE /audits/{id} (audit-retention: RET-01..04, RET-07) ----------------- #
import sqlite3  # noqa: E402
import threading  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: E402

from auditor.api import routes  # noqa: E402
from auditor.api.store import AuditStore  # noqa: E402


@pytest.fixture
def tmp_deps(tmp_path, monkeypatch):
    """Store/checkpointer temporários injetados na rota (não toca ~/.config/auditor)."""
    store = AuditStore(tmp_path / "meta.sqlite")
    saver = SqliteSaver(sqlite3.connect(str(tmp_path / "cp.sqlite"), check_same_thread=False))
    saver.setup()
    monkeypatch.setattr(routes, "get_store", lambda: store)
    monkeypatch.setattr(routes, "get_checkpointer", lambda: saver)
    report = tmp_path / "auditoria-x.md"
    report.write_text("r", encoding="utf-8")
    store.create("d1", "/proj", None, "p", "m")
    store.update("d1", status="completed", report_md=str(report))
    return store, report


def test_delete_audit_returns_204_and_audit_is_gone(tmp_deps):
    store, report = tmp_deps
    r = client.delete("/audits/d1")
    assert r.status_code == 204
    assert client.get("/audits/d1").status_code == 404
    assert "d1" not in [a["id"] for a in client.get("/audits").json()]
    assert not report.exists()


def test_delete_unknown_audit_returns_404(tmp_deps):
    assert client.delete("/audits/nao-existe").status_code == 404


def test_delete_live_audit_returns_409(tmp_deps, monkeypatch):
    store, report = tmp_deps

    class _Live:
        done = threading.Event()

    monkeypatch.setitem(routes.registry, "d1", _Live())
    r = client.delete("/audits/d1")
    assert r.status_code == 409
    assert store.get("d1") is not None and report.exists()


def test_delete_io_failure_returns_500_and_keeps_audit(tmp_deps, monkeypatch):
    store, _ = tmp_deps

    def boom(self, *a, **k):
        raise PermissionError("negado")

    monkeypatch.setattr(Path, "unlink", boom)
    r = client.delete("/audits/d1")
    assert r.status_code == 500
    assert store.get("d1") is not None
