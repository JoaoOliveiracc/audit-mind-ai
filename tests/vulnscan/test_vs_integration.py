"""Integração do vulnscan (spec: .specs/features/vuln-scan — CFG-01, FND-02, DUP-01, LOCK-05)."""
from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage
from typer.testing import CliRunner

from auditor import cli, events
from auditor.config import Settings, get_settings
from auditor.graph import build_graph
from auditor.nodes import adversarial, audit, verify
from auditor.nodes import dependency_scan as node
from auditor.vulnscan.models import Cycle

VULN_NOTE = ("Vulnerabilidades conhecidas (CVEs) de dependências já são verificadas por uma varredura "
             "determinística — não as reporte; foque em uso inseguro das dependências no código.")


class _OSV:
    instances: list = []

    def __init__(self, *a, **k):
        self.errors, self.closed = [], False
        _OSV.instances.append(self)

    def query(self, deps):
        return {}

    def advisories(self, ids):
        return {}

    def close(self):
        self.closed = True


class _EOL(_OSV):
    def cycles(self, product):
        return [Cycle("22", False, "22.20.0"), Cycle("16", True, "16.20.2")]


@pytest.fixture(autouse=True)
def _reset():
    _OSV.instances.clear()
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --- CFG-01: desligado por padrão; liga por env -----------------------------------------
def test_setting_defaults_off_and_reads_env(monkeypatch):
    assert Settings().vuln_scan is False
    monkeypatch.setenv("AUDITOR_VULN_SCAN", "true")
    assert Settings().vuln_scan is True


def test_disabled_node_makes_no_client_and_keeps_findings(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise AssertionError("nenhum cliente deveria ser criado")

    monkeypatch.setattr(node, "OSVClient", boom)
    monkeypatch.setattr(node, "EndOfLifeClient", boom)
    out = node.dependency_scan_node({"project_path": str(tmp_path), "vuln_scan": False,
                                     "findings": [{"title": "x"}]})
    assert out == {"dependency_scan": {"enabled": False}}


def test_enabled_node_appends_findings_emits_and_closes(monkeypatch, tmp_path):
    (tmp_path / ".nvmrc").write_text("16\n", encoding="utf-8")
    monkeypatch.setattr(node, "OSVClient", _OSV)
    monkeypatch.setattr(node, "EndOfLifeClient", _EOL)
    emitted = []
    monkeypatch.setattr(node, "_emit", emitted.append)

    out = node.dependency_scan_node({"project_path": str(tmp_path), "vuln_scan": True,
                                     "findings": [{"title": "do LLM"}]})

    assert [f["title"] for f in out["findings"]][0] == "do LLM"          # preserva os do audit
    assert any(f.get("source") == "endoflife" for f in out["findings"])
    assert out["dependency_scan"]["enabled"] is True
    assert emitted and emitted[0]["type"] == "dependency_scan"
    assert all(c.closed for c in _OSV.instances)


def test_state_absent_falls_back_to_setting(monkeypatch, tmp_path):
    monkeypatch.setenv("AUDITOR_VULN_SCAN", "false")
    assert node.vuln_scan_enabled({}) is False
    monkeypatch.setenv("AUDITOR_VULN_SCAN", "true")
    get_settings.cache_clear()
    assert node.vuln_scan_enabled({}) is True
    assert node.vuln_scan_enabled({"vuln_scan": False}) is False         # estado vence


# --- posição no grafo ------------------------------------------------------------------
def test_graph_runs_scan_after_audit_and_before_verify():
    edges = {(e.source, e.target) for e in build_graph().get_graph().edges}
    assert ("audit", "dependency_scan") in edges and ("dependency_scan", "verify") in edges
    assert ("audit", "verify") not in edges
    assert "dependency_scan" in events.NODE_LABELS


# --- CLI / API: flag/request vencem a env --------------------------------------------
class _Graph:
    def __init__(self):
        self.inputs = []

    def stream(self, inp, config, stream_mode=None):
        self.inputs.append(inp)
        return iter(())

    def get_state(self, config):
        return type("S", (), {"values": {"findings": [], "health_score": 100}})()


@pytest.mark.parametrize("args, env, expected", [
    ([], "false", False), ([], "true", True), (["--vuln-scan"], "false", True),
    (["--no-vuln-scan"], "true", False),
])
def test_cli_flag_precedence(monkeypatch, tmp_path, args, env, expected):
    monkeypatch.setenv("AUDITOR_VULN_SCAN", env)
    graph = _Graph()
    monkeypatch.setattr(cli, "build_graph", lambda: graph)
    monkeypatch.setattr(cli, "get_llm", lambda *a, **k: None)
    result = CliRunner().invoke(cli.app, ["audit", str(tmp_path), "--no-questions", *args])
    assert result.exit_code == 0, result.output
    assert graph.inputs[0]["vuln_scan"] is expected


@pytest.mark.parametrize("body_flag, env, expected", [(None, "true", True), (None, "false", False),
                                                      (True, "false", True), (False, "true", False)])
def test_api_request_precedence(monkeypatch, tmp_path, body_flag, env, expected):
    from fastapi.testclient import TestClient

    from auditor.api import routes
    from auditor.api.main import app

    monkeypatch.setenv("AUDITOR_VULN_SCAN", env)
    captured = {}

    class _Runner:
        def __init__(self, audit_id, graph, store, initial, resume=False):
            captured.update(initial)

        def start(self):
            pass

    monkeypatch.setattr(routes, "AuditRunner", _Runner)
    monkeypatch.setattr(routes, "get_llm", lambda *a, **k: None)
    monkeypatch.setattr(routes, "get_graph", lambda: None)
    body = {"project_path": str(tmp_path), **({"vuln_scan": body_flag} if body_flag is not None else {})}
    r = TestClient(app, base_url="http://localhost").post("/audits", json=body)
    assert r.status_code == 201 and captured["vuln_scan"] is expected


# --- FND-02: verify confirma (mesmo lockfile grande) e o juiz não julga ---------------
def test_verify_confirms_deterministic_finding_in_large_lockfile(tmp_path, monkeypatch):
    lock = {"lockfileVersion": 3, "packages": {f"node_modules/p{i}": {"version": "1.0.0"} for i in range(6_000)}}
    lock["packages"]["node_modules/lodash"] = {"version": "4.17.15"}
    (tmp_path / "package-lock.json").write_text(json.dumps(lock, indent=2), encoding="utf-8")
    assert (tmp_path / "package-lock.json").stat().st_size > Settings().max_file_bytes
    finding = {"title": "lodash@4.17.15", "severity": "high", "source": "osv", "file": "package-lock.json",
               "line": 1, "evidence": '"version": "4.17.15"', "confidence": 1.0, "dimension": "dependencies"}
    out = verify.verify_node({"project_path": str(tmp_path), "findings": [finding]})
    assert out["findings"][0]["verified"] is True and out["findings"][0]["confidence"] == 1.0


@pytest.mark.parametrize("source", ["osv", "endoflife"])
def test_adversarial_skips_deterministic_findings(source):
    f = {"file": "a", "severity": "critical", "source": source}
    assert adversarial._eligible(f, 4) is False
    assert adversarial._eligible({**f, "source": None}, 4) is True


# --- DUP-01: aviso aos investigadores quando a varredura está ligada --------------------
@pytest.mark.parametrize("enabled", [True, False])
def test_investigator_prompt_note(monkeypatch, tmp_path, enabled):
    prompts = []

    class _Agent:
        def invoke(self, *a, **k):
            return {"messages": [AIMessage(content="Relatório.")]}

    def fake_create_agent(llm, tools, system_prompt, middleware, checkpointer):
        prompts.append(system_prompt)
        return _Agent()

    class _LLM:
        def with_structured_output(self, schema):
            from langchain_core.runnables import RunnableLambda

            from auditor.state import DimensionResult
            return RunnableLambda(lambda m: DimensionResult(dimension="security", summary="s"))

    monkeypatch.setattr(audit, "create_agent", fake_create_agent)

    class _S:
        max_investigator_steps = 10

    state = {"project_path": str(tmp_path), "plan": {}, "user_context": {}, "stack_profile": {},
             "vuln_scan": enabled}
    audit._investigate_dimension("security", state, [], _LLM(), _S())
    assert (VULN_NOTE in prompts[0]) is enabled


# --- LOCK-05: .lock deixou de ser binário ---------------------------------------------
def test_lock_files_are_readable_by_tools(tmp_path):
    from auditor.tools.filesystem import make_project_tools

    assert ".lock" not in Settings().binary_extensions
    (tmp_path / "composer.lock").write_text('{"packages": []}\n', encoding="utf-8")
    tools = {t.name: t for t in make_project_tools(tmp_path, Settings())}
    assert '"packages"' in tools["read_file"].invoke({"path": "composer.lock"})
