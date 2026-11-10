"""Ciclo de correção 1 do Verifier (vuln-scan): mutantes sobreviventes e lacunas de spec."""
from __future__ import annotations


import pytest

from auditor.config import Settings
from auditor.vulnscan.lockfiles import python as py
from auditor.vulnscan.models import RuntimeDecl
from auditor.vulnscan.runtime import evaluate
from auditor.vulnscan.scanner import scan
from auditor.vulnscan.sources.osv import Advisory
from auditor.vulnscan.status import scan_status

from test_vs_scanner import FakeEOL, FakeOSV, _lock


def _adv(name, sev="high"):
    return Advisory(id="GHSA-x", cves=("CVE-1",), summary="s", severity=sev, severity_note=None,
                    affected=(("npm", name, (("introduced", "0"), ("fixed", "9.0.0"))),))


def _two_locks(tmp_path, first: dict, second: dict, npmrc_second: str | None = None):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "package-lock.json").write_text(_lock(first), encoding="utf-8")
    (tmp_path / "b" / "package-lock.json").write_text(_lock(second), encoding="utf-8")
    if npmrc_second:
        (tmp_path / "b" / ".npmrc").write_text(npmrc_second, encoding="utf-8")


# Gap 1 — RPT-01: incompleta também traz o sufixo de privadas ------------------------------
def test_incomplete_headline_carries_private_suffix():
    status = scan_status({"enabled": True, "queried": 3, "skipped_private": 2, "errors": ["x"]})
    assert status.headline == "Varredura de dependências incompleta (2 privada(s) não consultada(s))"


# Gap 2 — LOCK-03: privado em QUALQUER lockfile ⇒ nunca consultado ---------------------------
def test_private_in_one_lockfile_is_never_queried(tmp_path):
    _two_locks(tmp_path, {"@acme/x": ("1.0.0", {})}, {"@acme/x": ("1.0.0", {})},
               npmrc_second="@acme:registry=https://npm.acme.internal/\n")
    osv = FakeOSV()
    result = scan(tmp_path, Settings(), osv, FakeEOL())
    assert osv.queried == [] and result.stats["skipped_private"] == 1


# Gap 3 — FND-01: dev em um e prod em outro ⇒ severidade real ------------------------------
def test_dev_in_one_prod_in_other_keeps_severity(tmp_path):
    _two_locks(tmp_path, {"lodash": ("4.0.0", {"dev": True})}, {"lodash": ("4.0.0", {})})
    osv = FakeOSV(hits={("npm", "lodash", "4.0.0"): ["GHSA-x"]}, advisories={"GHSA-x": _adv("lodash")})
    (finding,) = [f for f in scan(tmp_path, Settings(), osv, FakeEOL()).findings if f["source"] == "osv"]
    assert finding["severity"] == "high"


# Gap 4 — RT-04: runtime desconhecido contado nas estatísticas -----------------------------
def test_unknown_runtime_counted_in_stats(tmp_path):
    (tmp_path / ".node-version").write_text("lts\n", encoding="utf-8")
    result = scan(tmp_path, Settings(), FakeOSV(), FakeEOL())
    assert result.stats["runtime_unknown"] == 1 and result.stats["runtime_findings"] == 0


# Gap 5 — LOCK-03: UV_FIND_LINKS ---------------------------------------------------------
def test_uv_find_links_env_skips_requirements(tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("acme==1.0\n", encoding="utf-8")
    monkeypatch.setenv("UV_FIND_LINKS", "./wheels")
    result = py.parse_requirements(tmp_path / "requirements.txt", "requirements.txt", tmp_path)
    assert result.skipped_files == ["requirements.txt"]


# Gap 6 — OSV-03: exatamente no teto não é truncado ----------------------------------------
@pytest.mark.parametrize("n, truncated", [(2, False), (3, True)])
def test_cap_boundary(tmp_path, n, truncated):
    (tmp_path / "package-lock.json").write_text(
        _lock({f"p{i}": ("1.0.0", {}) for i in range(n)}), encoding="utf-8")
    osv = FakeOSV()
    result = scan(tmp_path, Settings(), osv, FakeEOL(), max_packages=2)
    assert result.stats["truncated"] is truncated and len(osv.queried) == 2


# Gap 8 — RT-03: texto da faixa ------------------------------------------------------------
def test_range_message_says_range_allows_unsupported_runtime():
    from auditor.vulnscan.models import Cycle
    result = evaluate(RuntimeDecl("nodejs", ">=16", "package.json", 3, '"node": ">=16"'),
                      [Cycle("22", False, "22.20.0"), Cycle("16", True, "16.20.2")])
    assert result.severity == "medium"
    assert "A faixa declarada (>=16) permite Node.js 16, ciclo sem suporte (EOL)" in result.message


# Menor — poetry groups = ["dev"] ⇒ dev ------------------------------------------------------
def test_poetry_dev_group(tmp_path):
    text = ('[[package]]\nname = "pytest"\nversion = "8.0.0"\ngroups = ["dev"]\n\n'
            '[[package]]\nname = "requests"\nversion = "2.0.0"\ngroups = ["main", "dev"]\n')
    (tmp_path / "poetry.lock").write_text(text, encoding="utf-8")
    deps = {d.name: d.dev for d in py.parse_poetry_lock(tmp_path / "poetry.lock", "poetry.lock", tmp_path).dependencies}
    assert deps == {"pytest": True, "requests": False}
