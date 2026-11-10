"""scanner.scan (spec: .specs/features/vuln-scan — FND-01, LOCK-03, OSV-03 teto, CFG-02, RT-*)."""
from __future__ import annotations

import json

import pytest

from auditor.config import Settings
from auditor.vulnscan.models import Cycle
from auditor.vulnscan.scanner import MAX_PACKAGES, scan
from auditor.vulnscan.sources.osv import Advisory


def _adv(vid, cve, sev, fixed_by_version):
    events = []
    for intro, fixed in fixed_by_version:
        events += [("introduced", intro)] + ([("fixed", fixed)] if fixed else [])
    return Advisory(id=vid, cves=(cve,) if cve else (), summary=f"resumo {vid}", severity=sev,
                    severity_note=None, affected=(("npm", "lodash", tuple(events)),))


class FakeOSV:
    def __init__(self, hits=None, advisories=None, errors=()):
        self.hits, self.advs, self.errors = hits or {}, advisories or {}, list(errors)
        self.queried: list[tuple[str, str, str]] = []

    def query(self, deps):
        self.queried.extend((d.ecosystem, d.name, d.version) for d in deps)
        return {k: v for k, v in self.hits.items() if k in {(d.ecosystem, d.name, d.version) for d in deps}}

    def advisories(self, ids):
        return {i: self.advs[i] for i in ids if i in self.advs}


class FakeEOL:
    def __init__(self, errors=()):
        self.errors = list(errors)

    def cycles(self, product):
        return {"nodejs": [Cycle("22", False, "22.20.0"), Cycle("16", True, "16.20.2")]}.get(product)


def _lock(pkgs: dict) -> str:
    return json.dumps({"lockfileVersion": 3, "packages": {
        f"node_modules/{n}": {"version": v, "resolved": f"https://registry.npmjs.org/{n}/-/x.tgz", **extra}
        for n, (v, extra) in pkgs.items()}}, indent=2)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "package-lock.json").write_text(_lock({"lodash": ("4.17.15", {}), "safe": ("1.0.0", {}),
                                                    "vitest": ("2.1.9", {"dev": True})}), encoding="utf-8")
    (root / ".npmrc").write_text("@acme:registry=https://npm.acme.internal/\n", encoding="utf-8")
    pkg = root / "packages" / "a"
    pkg.mkdir(parents=True)
    (pkg / "package-lock.json").write_text(_lock({"lodash": ("4.17.15", {}), "@acme/billing": ("3.0.0", {})}),
                                           encoding="utf-8")
    nm = root / "node_modules" / "x"
    nm.mkdir(parents=True)
    (nm / "package-lock.json").write_text(_lock({"ignored": ("1.0.0", {})}), encoding="utf-8")
    (root / ".nvmrc").write_text("16\n", encoding="utf-8")
    return root


ADVS = {"GHSA-a": _adv("GHSA-a", "CVE-2021-23337", "high", [("4.0.0", "4.17.21")]),
        "GHSA-b": _adv("GHSA-b", None, "medium", [("4.0.0", "4.17.19")]),
        "GHSA-c": _adv("GHSA-c", "CVE-2020-1", "low", [("0", None)])}


def _run(project, **osv_kw):
    osv = FakeOSV(**osv_kw)
    result = scan(project, Settings(), osv, FakeEOL())
    return result, osv


def _osv_findings(result):
    return [f for f in result.findings if f["source"] == "osv"]


# --- FND-01: um achado por pacote@versão, entre todos os lockfiles ---------------------
def test_one_finding_per_package_version_across_lockfiles(project):
    result, _ = _run(project, hits={("npm", "lodash", "4.17.15"): ["GHSA-a", "GHSA-b"]}, advisories=ADVS)
    (f,) = _osv_findings(result)
    assert f["title"] == "lodash@4.17.15 com 2 vulnerabilidade(s) conhecida(s)"
    assert (f["dimension"], f["severity"], f["file"]) == ("dependencies", "high", "package-lock.json")
    lines = (project / "package-lock.json").read_text(encoding="utf-8").splitlines()
    assert f["evidence"] == lines[f["line"] - 1].strip() and '"version": "4.17.15"' in f["evidence"]
    for expected in ("GHSA-a", "CVE-2021-23337", "GHSA-b", "packages/a/package-lock.json"):
        assert expected in f["description"]
    assert f["recommendation"] == "Atualize para ≥ 4.17.21."         # maior correção entre os advisories


def test_recommendation_without_any_fix(project):
    result, _ = _run(project, hits={("npm", "lodash", "4.17.15"): ["GHSA-c"]}, advisories=ADVS)
    assert _osv_findings(result)[0]["recommendation"] == "Sem correção publicada; avalie substituir/mitigar."


def test_recommendation_mixed_fix_and_no_fix(project):
    result, _ = _run(project, hits={("npm", "lodash", "4.17.15"): ["GHSA-a", "GHSA-c"]}, advisories=ADVS)
    assert _osv_findings(result)[0]["recommendation"] == \
        "Atualize para ≥ 4.17.21; 1 advisory(ies) sem correção publicada — avalie substituir/mitigar."


def test_dev_only_package_is_info(project):
    adv = _adv("GHSA-v", "CVE-9", "critical", [("0", "3.0.0")])
    adv = Advisory(**{**adv.__dict__, "affected": (("npm", "vitest", adv.affected[0][2]),)})
    result, _ = _run(project, hits={("npm", "vitest", "2.1.9"): ["GHSA-v"]}, advisories={"GHSA-v": adv})
    assert _osv_findings(result)[0]["severity"] == "info"


# --- LOCK-03 / poda: privados e node_modules nunca consultados --------------------------
def test_private_and_ignored_dirs_never_queried(project):
    result, osv = _run(project)
    names = {n for _, n, _ in osv.queried}
    assert "@acme/billing" not in names and "ignored" not in names
    assert names == {"lodash", "safe", "vitest"}
    assert result.stats["skipped_private"] == 1


# --- OSV-03: teto de pacotes --------------------------------------------------------
def test_max_packages_cap(project):
    assert MAX_PACKAGES == 10_000
    osv = FakeOSV()
    result = scan(project, Settings(), osv, FakeEOL(), max_packages=2)
    assert len(osv.queried) == 2 and result.stats["truncated"] is True


# --- runtime --------------------------------------------------------------------------
def test_runtime_finding(project):
    result, _ = _run(project)
    (rt,) = [f for f in result.findings if f["source"] == "endoflife"]
    assert (rt["severity"], rt["file"], rt["line"], rt["evidence"]) == ("high", ".nvmrc", 1, "16")
    assert "22" in rt["recommendation"]                               # ciclo suportado mais novo


# --- CFG-02: estatísticas e erros -----------------------------------------------------
def test_stats_and_errors(project):
    (project / "composer.lock").write_text("{ inválido", encoding="utf-8")
    osv = FakeOSV(hits={("npm", "lodash", "4.17.15"): ["GHSA-a"]}, advisories=ADVS, errors=["querybatch: x"])
    result = scan(project, Settings(), osv, FakeEOL(errors=["endoflife/php: y"]))
    s = result.stats
    assert s["enabled"] is True
    assert (s["packages"], s["queried"], s["skipped_private"], s["vulnerable"]) == (4, 3, 1, 1)
    assert (s["runtime_findings"], s["truncated"]) == (1, False)
    assert any("composer.lock" in e for e in s["errors"])
    assert "querybatch: x" in s["errors"] and "endoflife/php: y" in s["errors"]


def test_clean_project_has_no_findings_and_no_errors(tmp_path):
    (tmp_path / "package-lock.json").write_text(_lock({"safe": ("1.0.0", {})}), encoding="utf-8")
    result = scan(tmp_path, Settings(), FakeOSV(), FakeEOL())
    assert result.findings == [] and result.stats["errors"] == [] and result.stats["queried"] == 1
