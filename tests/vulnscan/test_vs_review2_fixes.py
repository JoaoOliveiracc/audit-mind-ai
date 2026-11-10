"""Regressões do code review da fase 2 (vuln-scan)."""
from __future__ import annotations

import json
import os

import httpx
import pytest

from auditor.config import Settings
from auditor.nodes import adversarial, verify
from auditor.nodes import dependency_scan as node
from auditor.vulnscan.models import Cycle, RuntimeDecl, is_deterministic
from auditor.vulnscan.runtime import detect_in_file, evaluate
from auditor.vulnscan.scanner import scan
from auditor.vulnscan.sources.eol import EOL_BASE_URL, EndOfLifeClient
from auditor.vulnscan.sources.osv import OSV_BASE_URL, OSVClient
from auditor.vulnscan.status import scan_status

from test_vs_scanner import FakeEOL, FakeOSV, _lock


def _osv(handler):
    return OSVClient(http=httpx.Client(base_url=OSV_BASE_URL, transport=httpx.MockTransport(handler)))


def _dep():
    from auditor.vulnscan.models import Dependency
    return Dependency(ecosystem="npm", name="a", version="1.0.0", file="f", line=1)


# 1 — respostas malformadas nunca lançam ----------------------------------------------
@pytest.mark.parametrize("body", [{"results": None}, {"results": ["x"]}, {"results": [[1]]}, [1, 2]])
def test_malformed_querybatch_is_recorded(body):
    client = _osv(lambda r: httpx.Response(200, json=body))
    client.query([_dep()])
    assert client.errors


@pytest.mark.parametrize("record", [["lista"], "texto", {"id": "X", "affected": "x"},
                                    {"id": "X", "affected": [{"package": "x"}]}])
def test_malformed_advisory_is_recorded(record):
    client = _osv(lambda r: httpx.Response(200, json=record))
    result = client.advisories({"X"})                 # não lança
    assert client.errors or set(result) == {"X"}


@pytest.mark.parametrize("payload", [{"result": {"releases": [{"name": "1", "latest": "1.0"}]}},
                                     {"result": {"releases": "x"}}, ["x"]])
def test_malformed_eol_is_recorded(payload):
    client = EndOfLifeClient(http=httpx.Client(base_url=EOL_BASE_URL,
                                               transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload))))
    client.cycles("nodejs")          # não lança


# 2 — o nó nunca derruba a auditoria -------------------------------------------------
def test_node_records_unexpected_scan_error(monkeypatch, tmp_path):
    class _C:
        errors: list = []

        def close(self):
            self.closed = True

    monkeypatch.setattr(node, "OSVClient", _C)
    monkeypatch.setattr(node, "EndOfLifeClient", _C)
    monkeypatch.setattr(node, "_emit", lambda e: None)

    def boom(*a, **k):
        raise RuntimeError("falha inesperada")

    monkeypatch.setattr(node, "scan", boom)
    out = node.dependency_scan_node({"project_path": str(tmp_path), "vuln_scan": True,
                                     "findings": [{"title": "llm"}]})
    assert out["findings"] == [{"title": "llm"}]
    assert out["dependency_scan"]["enabled"] is True
    assert any("falha inesperada" in e for e in out["dependency_scan"]["errors"])
    assert scan_status(out["dependency_scan"]).incomplete


def test_osv_client_closed_when_eol_client_fails(monkeypatch, tmp_path):
    closed = []

    class _OSV:
        errors: list = []

        def close(self):
            closed.append(True)

    def bad_eol():
        raise RuntimeError("eol")

    monkeypatch.setattr(node, "OSVClient", _OSV)
    monkeypatch.setattr(node, "EndOfLifeClient", bad_eol)
    monkeypatch.setattr(node, "_emit", lambda e: None)
    out = node.dependency_scan_node({"project_path": str(tmp_path), "vuln_scan": True})
    assert closed == [True] and out["dependency_scan"]["errors"]


@pytest.mark.parametrize("name, text", [("pyproject.toml", 'project = "x"\n'),
                                        ("package.json", '{"engines": "x"}'),
                                        ("composer.json", '{"require": ["php"]}')])
def test_runtime_detectors_tolerate_wrong_types(tmp_path, name, text):
    (tmp_path / name).write_text(text, encoding="utf-8")
    assert detect_in_file(tmp_path / name, name) == []


# 3 — arquivos simbólicos não são lidos ------------------------------------------------
def test_symlinked_lockfile_outside_root_is_ignored(tmp_path):
    outside = tmp_path / "fora"
    outside.mkdir()
    (outside / "package-lock.json").write_text(_lock({"segredo": ("1.0.0", {})}), encoding="utf-8")
    root = tmp_path / "proj"
    root.mkdir()
    os.symlink(outside / "package-lock.json", root / "package-lock.json")
    osv = FakeOSV()
    scan(root, Settings(), osv, FakeEOL())
    assert osv.queried == []


# 4/6 — status considera arquivos pulados, runtime e runtime não avaliado -------------------
BASE = {"enabled": True, "packages": 0, "queried": 0, "skipped_private": 0, "vulnerable": 0,
        "runtime_findings": 0, "runtime_unknown": 0, "truncated": False, "errors": [], "skipped_files": []}


def test_skipped_files_make_scan_incomplete():
    status = scan_status({**BASE, "skipped_files": ["requirements.txt"]})
    assert status.incomplete and any("requirements.txt" in r for r in status.reasons)


def test_runtime_findings_appear_in_headline():
    assert "1 alerta(s) de runtime" in scan_status({**BASE, "queried": 3, "runtime_findings": 1}).headline


def test_runtime_unknown_appears_in_headline():
    assert "2 declaração(ões) de runtime não avaliada(s)" in \
        scan_status({**BASE, "runtime_unknown": 2}).headline


# 5 — paginação esgotada é erro ---------------------------------------------------------
def test_pagination_cap_is_recorded():
    def handler(request):
        n = len(json.loads(request.content)["queries"])
        return httpx.Response(200, json={"results": [{"vulns": [{"id": "V"}], "next_page_token": "T"}] * n})

    client = _osv(handler)
    client.query([_dep()])
    assert any("pagina" in e for e in client.errors)


# 7 — verify lê cada arquivo uma vez só --------------------------------------------------
def test_verify_reads_each_file_once(tmp_path, monkeypatch):
    lock = tmp_path / "package-lock.json"
    lock.write_text('"version": "1.0.0"\n' * 10, encoding="utf-8")
    reads = []
    original = verify.Path.read_text

    def counting(self, *a, **k):
        reads.append(self.name)
        return original(self, *a, **k)

    monkeypatch.setattr(verify.Path, "read_text", counting)
    findings = [{"title": f"t{i}", "source": "osv", "file": "package-lock.json", "line": 1,
                 "evidence": '"version": "1.0.0"'} for i in range(5)]
    out = verify.verify_node({"project_path": str(tmp_path), "findings": findings})
    assert out["verification"]["verified"] == 5 and reads.count("package-lock.json") == 1


# 8 — recomendação/título de runtime coerentes com o motivo ------------------------------
CYCLES = [Cycle("23", False, "23.1.0"), Cycle("22", False, "22.20.0"), Cycle("20", False, "20.18.0"),
          Cycle("16", True, "16.20.2")]


def _finding(value):
    from auditor.vulnscan.scanner import _runtime_finding
    decl = RuntimeDecl("nodejs", value, "Dockerfile", 1, value)
    result = evaluate(decl, CYCLES)
    return _runtime_finding(decl, result, CYCLES)


def test_behind_patch_recommends_same_cycle_latest():
    f = _finding("20.11.1")
    assert "20.18.0" in f["recommendation"] and "23" not in f["recommendation"]
    assert "atualização recomendada" in f["title"]


def test_eol_range_title_says_unsupported():
    f = _finding(">=16")
    assert "sem suporte" in f["title"] and f["severity"] == "medium"


# 10 — uma única regra para achados determinísticos --------------------------------------
@pytest.mark.parametrize("source, expected", [("osv", True), ("endoflife", True), (None, False), ("llm", False)])
def test_is_deterministic(source, expected):
    assert is_deterministic({"source": source}) is expected
    assert adversarial._eligible({"file": "a", "severity": "critical", "source": source}, 4) is (not expected)
