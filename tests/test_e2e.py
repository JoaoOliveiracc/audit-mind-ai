"""Ponta a ponta offline (specs: coverage-and-e2e — E2E-01..03; report-chat-and-sarif — E2E-04)."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pytest
from fake_llm import EVIDENCE, FINDING_TITLE, PROJECT_SOURCE, QUESTION, SUMMARY, FakeLLM
from fastapi.testclient import TestClient
from langgraph.types import Command
from typer.testing import CliRunner

import auditor.llm as llm_module
from auditor.api.main import app
from auditor.cli import app as cli_app
from auditor.config import get_settings
from auditor.graph import build_graph


@pytest.fixture
def e2e(tmp_path, monkeypatch):
    """Projeto de fixture + saída temporária + juiz adversarial ligado + LLM falso."""
    project = tmp_path / "proj"
    (project / "tests").mkdir(parents=True)
    (project / "app.py").write_text(PROJECT_SOURCE, encoding="utf-8")
    (project / "tests" / "test_app.py").write_text("def test(): pass\n", encoding="utf-8")
    reports = tmp_path / "reports"
    monkeypatch.setenv("AUDITOR_OUTPUT_DIR", str(reports))
    monkeypatch.setenv("AUDITOR_ADVERSARIAL_VERIFY", "true")
    monkeypatch.setattr(llm_module, "_build_llm", lambda *a, **k: FakeLLM())
    get_settings.cache_clear()
    yield project, reports
    get_settings.cache_clear()


def _initial(project: Path) -> dict:
    return {"project_path": str(project), "user_goal": "", "provider": "fake", "model": "fake",
            "skip_questions": False, "user_context": {}, "findings": [],
            "dimension_summaries": [], "status": "started"}


def _assert_reports(reports: Path, final: dict) -> None:
    paths = [Path(final[k]) for k in ("report_markdown_path", "report_html_path",
                                      "report_sarif_path")]
    assert all(p.is_file() and p.parent == reports for p in paths)
    assert FINDING_TITLE in paths[0].read_text(encoding="utf-8")
    sarif = json.loads(paths[2].read_text(encoding="utf-8"))
    assert len(sarif["runs"][0]["results"]) == 1


# --- E2E-01: grafo completo -----------------------------------------------------------
def test_e2e01_graph_end_to_end(e2e):
    project, reports = e2e
    graph = build_graph()
    cfg = {"configurable": {"thread_id": "e2e-graph-0001"}}

    chunks = list(graph.stream(_initial(project), cfg, stream_mode="updates"))
    questions = chunks[-1]["__interrupt__"][0].value["questions"]
    assert [q["question"] for q in questions] == [QUESTION]

    list(graph.stream(Command(resume={QUESTION: "sim"}), cfg, stream_mode="updates"))
    final = graph.get_state(cfg).values

    assert final["user_context"] == {QUESTION: "sim"}
    assert final["plan"]["dimensions"] == ["security"]
    assert len(final["findings"]) == 1
    finding = final["findings"][0]
    assert (finding["title"], finding["evidence"]) == (FINDING_TITLE, EVIDENCE)
    assert finding["verified"] is True and finding["judged"] == "confirmed"
    assert final["verification"]["verified"] == 1 and final["adversarial"]["confirmed"] == 1
    assert final["health_score"] == 80
    assert final["executive_summary"] == SUMMARY
    assert final["status"] == "completed"
    _assert_reports(reports, final)


# --- E2E-02: API HTTP completa ----------------------------------------------------------


_SSE_ORDER = ["phase", "clarification", "investigator", "verification", "adversarial", "completed"]


def _wait_status(client: TestClient, audit_id: str, status: str, timeout: float = 15.0) -> dict:
    end = time.time() + timeout
    summary: dict = {}
    while time.time() < end:
        summary = client.get(f"/audits/{audit_id}").json()
        if summary["status"] == status:
            return summary
        assert summary["status"] != "error", summary
        time.sleep(0.05)
    raise AssertionError(f"timeout esperando {status!r}: {summary}")


def test_e2e02_api_end_to_end(e2e):
    project, _reports = e2e
    client = TestClient(app, base_url="http://localhost")

    created = client.post("/audits", json={"project_path": str(project), "interactive": True,
                                           "provider": "fake", "model": "fake"})
    assert created.status_code == 201
    audit_id = created.json()["id"]

    _wait_status(client, audit_id, "waiting_input")
    assert client.post(f"/audits/{audit_id}/answers",
                       json={"answers": {QUESTION: "sim"}}).status_code == 200
    summary = _wait_status(client, audit_id, "completed")
    assert summary["health_score"] == 80
    assert summary["counts"] == {"high": 1}

    stream = client.get(f"/audits/{audit_id}/stream")
    assert stream.status_code == 200
    events = [line.split(":", 1)[1].strip() for line in stream.text.splitlines()
              if line.startswith("event:")]
    first = [events.index(name) for name in _SSE_ORDER]          # todos presentes…
    assert first == sorted(first)                                 # …na ordem relativa esperada

    findings = client.get(f"/audits/{audit_id}/findings").json()["findings"]
    assert [f["title"] for f in findings] == [FINDING_TITLE]

    html = client.get(f"/audits/{audit_id}/report", params={"format": "html"})
    md = client.get(f"/audits/{audit_id}/report", params={"format": "md"})
    sarif = client.get(f"/audits/{audit_id}/report", params={"format": "sarif"})
    assert (html.status_code, md.status_code, sarif.status_code) == (200, 200, 200)
    assert FINDING_TITLE in html.text and FINDING_TITLE in md.text
    assert sarif.headers["content-type"].startswith("application/sarif+json")
    assert len(sarif.json()["runs"][0]["results"]) == 1

    # E2E-04: chat sobre o relatório concluído (contexto vem do estado salvo da auditoria)
    chat = client.post(f"/audits/{audit_id}/chat", json={"question": "Qual o achado mais grave?"})
    assert chat.status_code == 200
    assert chat.json() == {"answer": SUMMARY}           # LLM falso: chamadas simples → SUMMARY


# --- E2E-03: CLI `auditor audit` ----------------------------------------------------------


def test_e2e03_cli_end_to_end(e2e, monkeypatch):
    project, reports = e2e
    monkeypatch.setenv("COLUMNS", "400")      # Rich não quebra os caminhos longos em linhas

    result = CliRunner().invoke(cli_app, ["audit", str(project)], input="sim\n")

    assert result.exit_code == 0, result.output
    assert QUESTION in result.output                      # pergunta exibida ao usuário
    assert "Auditoria concluída" in result.output
    assert "80/100" in result.output
    paths = {label: Path(path) for label, path in
             re.findall(r"^(Markdown|HTML|SARIF):\s+(\S+)$", result.output, re.M)}
    assert set(paths) == {"Markdown", "HTML", "SARIF"}
    assert all(p.is_file() and p.parent == reports for p in paths.values())
