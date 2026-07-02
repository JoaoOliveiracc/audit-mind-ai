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
