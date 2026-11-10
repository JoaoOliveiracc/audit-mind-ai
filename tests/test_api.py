"""Testes da API que não dependem do LLM (via TestClient)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from auditor.api.main import app
from auditor.api.runner import _counts

client = TestClient(app, base_url="http://localhost")  # Host permitido (AD-002)


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


# --- POST /audits/{id}/resume (api-hardening: RES-04..07) ------------------------- #
from auditor.llm import LLMConfigError  # noqa: E402


@pytest.fixture
def resume_env(tmp_path, monkeypatch):
    store = AuditStore(tmp_path / "meta.sqlite")
    monkeypatch.setattr(routes, "get_store", lambda: store)
    monkeypatch.setattr(routes, "get_graph", lambda: "GRAPH")
    llm_calls = []
    monkeypatch.setattr(routes, "get_llm", lambda p, m: llm_calls.append((p, m)))
    started = []

    class _FakeRunner:
        def __init__(self, audit_id, graph, st, initial, resume=False):
            self.args = (audit_id, graph, initial, resume)
            self.done = threading.Event()

        def start(self):
            started.append(self)

    monkeypatch.setattr(routes, "AuditRunner", _FakeRunner)
    for aid, status in (("int", "interrupted"), ("done", "completed"), ("err", "error")):
        store.create(aid, "/proj", None, "anthropic", "claude-x")
        store.update(aid, status=status)
    yield store, started, llm_calls
    for aid in ("int", "done", "err"):
        routes.registry.pop(aid, None)


def test_resume_interrupted_returns_200_running_and_registers_runner(resume_env):
    store, started, llm_calls = resume_env
    r = client.post("/audits/int/resume")
    assert r.status_code == 200
    assert r.json()["status"] == "running"
    assert store.get("int")["status"] == "running"
    assert len(started) == 1 and started[0].args == ("int", "GRAPH", None, True)
    assert routes.registry["int"] is started[0]
    assert llm_calls == [("anthropic", "claude-x")]


def test_resume_unknown_returns_404(resume_env):
    r = client.post("/audits/nope/resume")
    assert r.status_code == 404
    assert r.json()["detail"] == "Auditoria não encontrada."


@pytest.mark.parametrize("aid", ["done", "err"])
def test_resume_non_interrupted_returns_409(resume_env, aid):
    store, started, _ = resume_env
    assert client.post(f"/audits/{aid}/resume").status_code == 409
    assert started == []


def test_resume_with_live_runner_returns_409(resume_env, monkeypatch):
    store, started, _ = resume_env

    class _Live:
        done = threading.Event()

    monkeypatch.setitem(routes.registry, "int", _Live())
    assert client.post("/audits/int/resume").status_code == 409
    assert started == []


def test_resume_with_bad_llm_config_returns_400_and_keeps_status(resume_env, monkeypatch):
    store, started, _ = resume_env

    def bad(p, m):
        raise LLMConfigError("credencial ausente")

    monkeypatch.setattr(routes, "get_llm", bad)
    r = client.post("/audits/int/resume")
    assert r.status_code == 400
    assert "credencial ausente" in r.json()["detail"]
    assert store.get("int")["status"] == "interrupted"
    assert started == []


def _blocking_llm(monkeypatch):
    """get_llm que bloqueia a 1ª chamada até ``release`` — abre a janela da corrida."""
    entered, release = threading.Event(), threading.Event()
    calls = []

    def slow(p, m):
        calls.append(p)
        if len(calls) == 1:
            entered.set()
            release.wait(5)

    monkeypatch.setattr(routes, "get_llm", slow)
    return entered, release


def _post_in_thread(path, out):
    t = threading.Thread(target=lambda: out.append(client.post(path)))
    t.start()
    return t


def test_concurrent_double_resume_starts_only_one_runner(resume_env, monkeypatch):
    store, started, _ = resume_env
    entered, release = _blocking_llm(monkeypatch)
    out = []
    t = _post_in_thread("/audits/int/resume", out)
    assert entered.wait(5)                      # 1ª requisição parada na validação

    second = client.post("/audits/int/resume")  # 2ª completa enquanto a 1ª espera
    release.set()
    t.join(5)

    assert second.status_code == 200
    assert out[0].status_code == 409
    assert len(started) == 1


def test_delete_during_resume_validation_does_not_500(resume_env, monkeypatch, tmp_path):
    store, started, _ = resume_env
    saver = SqliteSaver(sqlite3.connect(str(tmp_path / "cp2.sqlite"), check_same_thread=False))
    saver.setup()
    monkeypatch.setattr(routes, "get_checkpointer", lambda: saver)
    entered, release = _blocking_llm(monkeypatch)
    out = []
    t = _post_in_thread("/audits/int/resume", out)
    assert entered.wait(5)

    deleted = client.delete("/audits/int")
    release.set()
    t.join(5)

    assert deleted.status_code == 204
    assert out[0].status_code == 404
    assert started == []
    assert store.get("int") is None
