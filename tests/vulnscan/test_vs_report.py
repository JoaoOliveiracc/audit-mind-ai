"""Status explícito da varredura no relatório/CLI (spec: .specs/features/vuln-scan — CFG-02, RPT-01)."""
from __future__ import annotations

import io

import pytest
from rich.console import Console

from auditor import cli
from auditor.report.renderer import build_context, render_html, render_markdown
from auditor.vulnscan.status import scan_status

BASE = {"enabled": True, "packages": 12, "queried": 10, "skipped_private": 0, "vulnerable": 0,
        "runtime_findings": 0, "truncated": False, "errors": []}


@pytest.mark.parametrize("stats, headline", [
    (None, "Verificação de dependências desativada (AUDITOR_VULN_SCAN)"),
    ({"enabled": False}, "Verificação de dependências desativada (AUDITOR_VULN_SCAN)"),
    (BASE, "Nenhuma vulnerabilidade conhecida nas 10 dependências consultadas"),
    ({**BASE, "skipped_private": 2},
     "Nenhuma vulnerabilidade conhecida nas 10 dependências consultadas (2 privada(s) não consultada(s))"),
    ({**BASE, "vulnerable": 3}, "3 pacote(s) vulnerável(is) entre 10 dependências consultadas"),
    ({**BASE, "errors": ["querybatch: timeout"]}, "Varredura de dependências incompleta"),
    ({**BASE, "truncated": True}, "Varredura de dependências incompleta"),
])
def test_status_headline(stats, headline):
    assert scan_status(stats).headline == headline


def test_incomplete_lists_reasons():
    status = scan_status({**BASE, "truncated": True, "errors": ["querybatch: timeout"]})
    assert status.incomplete is True
    assert any("10 000" in r for r in status.reasons) and "querybatch: timeout" in status.reasons


def test_clean_never_reads_as_incomplete():
    assert scan_status(BASE).incomplete is False and scan_status(BASE).reasons == []


def _ctx(stats):
    return build_context({"findings": [], "dependency_scan": stats}, "agora")


@pytest.mark.parametrize("render", [render_markdown, render_html])
@pytest.mark.parametrize("stats, expected", [
    (None, "Verificação de dependências desativada"),
    (BASE, "Nenhuma vulnerabilidade conhecida nas 10 dependências consultadas"),
    ({**BASE, "errors": ["endoflife/php: 500"]}, "endoflife/php: 500"),
])
def test_report_always_states_scan_status(render, stats, expected):
    assert expected in render(_ctx(stats))


def test_html_escapes_error_reasons():
    out = render_html(_ctx({**BASE, "errors": ["<script>x</script>"]}))
    assert "<script>x</script>" not in out and "&lt;script&gt;" in out


@pytest.mark.parametrize("stats, expected", [
    (None, "Verificação de dependências desativada"),
    ({**BASE, "vulnerable": 1}, "1 pacote(s) vulnerável(is) entre 10 dependências consultadas"),
    ({**BASE, "errors": ["querybatch: x"]}, "querybatch: x"),
])
def test_cli_summary_states_scan_status(monkeypatch, stats, expected):
    out = io.StringIO()
    monkeypatch.setattr(cli, "console", Console(file=out, width=200, color_system=None))
    cli._print_summary({"health_score": 90, "findings": [], "dependency_scan": stats})
    assert expected in out.getvalue()


def test_findings_endpoint_exposes_scan_stats(monkeypatch):
    from fastapi.testclient import TestClient

    from auditor.api import routes
    from auditor.api.main import app

    class _Store:
        def get(self, audit_id):
            return object()

    class _Graph:
        def get_state(self, config):
            return type("S", (), {"values": {"dependency_scan": BASE}})()

    monkeypatch.setattr(routes, "get_store", lambda: _Store())
    monkeypatch.setattr(routes, "get_graph", lambda: _Graph())
    r = TestClient(app, base_url="http://localhost").get("/audits/x/findings")
    assert r.status_code == 200 and r.json()["dependency_scan"] == BASE
