"""Regressões do code review da fase 3 (vuln-scan)."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from auditor.config import Settings, get_settings
from auditor.nodes import dependency_scan as node
from auditor.vulnscan import scanner as scanner_mod
from auditor.vulnscan.lockfiles import npm
from auditor.vulnscan.lockfiles import python as py
from auditor.vulnscan.scanner import scan

from test_vs_scanner import FakeEOL, FakeOSV, _lock

PNPM = "lockfileVersion: '9.0'\n\npackages:\n\n  acme-billing@1.2.0:\n    resolution: {integrity: sha512-x}\n"


def _pnpm_private(tmp_path) -> bool:
    proj = tmp_path / "proj"
    proj.mkdir(exist_ok=True)
    (proj / "pnpm-lock.yaml").write_text(PNPM, encoding="utf-8")
    (dep,) = npm.parse_pnpm_lock(proj / "pnpm-lock.yaml", "pnpm-lock.yaml", proj).dependencies
    return dep.private


# 2 — configuração de registro do usuário/ambiente (fora do projeto) --------------------------
def test_user_npmrc_private_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    assert _pnpm_private(tmp_path) is False
    (tmp_path / "home" / ".npmrc").write_text("registry=https://nexus.corp/npm/\n", encoding="utf-8")
    assert _pnpm_private(tmp_path) is True


def test_user_yarnrc_private_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    (tmp_path / "home" / ".yarnrc.yml").write_text('npmRegistryServer: "https://nexus.corp"\n', encoding="utf-8")
    assert _pnpm_private(tmp_path) is True


@pytest.mark.parametrize("var", ["NPM_CONFIG_REGISTRY", "npm_config_registry", "YARN_NPM_REGISTRY_SERVER"])
def test_env_private_registry(tmp_path, monkeypatch, var):
    monkeypatch.setenv(var, "https://nexus.corp/npm/")
    assert _pnpm_private(tmp_path) is True


def test_env_public_registry_stays_public(tmp_path, monkeypatch):
    monkeypatch.setenv("NPM_CONFIG_REGISTRY", "https://registry.npmjs.org/")
    assert _pnpm_private(tmp_path) is False


def test_env_scope_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("npm_config_@acme:registry", "https://nexus.corp/npm/")
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "pnpm-lock.yaml").write_text(PNPM.replace("acme-billing@1.2.0", "'@acme/billing@1.2.0'"), encoding="utf-8")
    deps = npm.parse_pnpm_lock(proj / "pnpm-lock.yaml", "pnpm-lock.yaml", proj).dependencies
    assert [d.private for d in deps] == [True]


def _req_skipped(tmp_path) -> bool:
    proj = tmp_path / "proj"
    proj.mkdir(exist_ok=True)
    (proj / "requirements.txt").write_text("acme-billing==1.2.0\n", encoding="utf-8")
    return py.parse_requirements(proj / "requirements.txt", "requirements.txt", proj).skipped_files == \
        ["requirements.txt"]


@pytest.mark.parametrize("var", ["PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL", "PIP_FIND_LINKS",
                                 "UV_INDEX_URL", "UV_EXTRA_INDEX_URL", "UV_INDEX", "UV_DEFAULT_INDEX"])
def test_pip_env_private_index_skips_requirements(tmp_path, monkeypatch, var):
    assert _req_skipped(tmp_path) is False
    monkeypatch.setenv(var, "https://nexus.corp/simple")
    assert _req_skipped(tmp_path) is True


def test_pip_env_public_index_is_fine(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_INDEX_URL", "https://pypi.org/simple")
    assert _req_skipped(tmp_path) is False


@pytest.mark.parametrize("rel", [".config/pip/pip.conf", ".pip/pip.conf"])
@pytest.mark.parametrize("key", ["index-url", "extra-index-url", "find-links"])
def test_user_pip_conf_private_index(tmp_path, monkeypatch, rel, key):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    conf = home / rel
    conf.parent.mkdir(parents=True)
    conf.write_text(f"[global]\n{key} = https://nexus.corp/simple\n", encoding="utf-8")
    assert _req_skipped(tmp_path) is True


def test_pip_config_file_env(tmp_path, monkeypatch):
    conf = tmp_path / "custom.conf"
    conf.write_text("[install]\nindex-url = https://nexus.corp/simple\n", encoding="utf-8")
    monkeypatch.setenv("PIP_CONFIG_FILE", str(conf))
    assert _req_skipped(tmp_path) is True


def test_broken_pip_conf_is_conservative(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    (home / ".config" / "pip").mkdir(parents=True)
    (home / ".config" / "pip" / "pip.conf").write_text("isto não é ini\n[[[\n", encoding="utf-8")
    assert _req_skipped(tmp_path) is True        # dúvida ⇒ privado


# 3 — um lockfile quebrado não derruba a varredura inteira ---------------------------------
def test_one_crashing_parser_does_not_discard_other_results(tmp_path, monkeypatch):
    (tmp_path / "package-lock.json").write_text(_lock({"lodash": ("4.17.15", {})}), encoding="utf-8")
    (tmp_path / "composer.lock").write_text("{}", encoding="utf-8")
    original = scanner_mod.parser_for

    def boom(*a):
        raise AttributeError("formato inesperado")

    monkeypatch.setattr(scanner_mod, "parser_for", lambda name: boom if name == "composer.lock" else original(name))
    osv = FakeOSV()
    result = scan(tmp_path, Settings(), osv, FakeEOL())
    assert [n for _, n, _ in osv.queried] == ["lodash"]
    assert any("composer.lock" in e and "formato inesperado" in e for e in result.stats["errors"])


@pytest.mark.parametrize("name, text", [
    ("uv.lock", 'version = 1\n[[package]]\nname = "a"\nversion = "1.0"\ndev-dependencies = ["x"]\n'),
    ("uv.lock", 'version = 1\n[[package]]\nname = "a"\nversion = "1.0"\ndependencies = ["x"]\n'),
    ("poetry.lock", '[[package]]\nname = "a"\nversion = "1.0"\nsource = "x"\n'),
    ("Pipfile.lock", json.dumps({"_meta": {"sources": []}, "default": {"a": {"version": "==1", "index": ["x"]}}})),
])
def test_wrong_types_never_raise(tmp_path, name, text):
    (tmp_path / name).write_text(text, encoding="utf-8")
    scan(tmp_path, Settings(), FakeOSV(), FakeEOL())      # não lança


# 4 — localização de linha linear ----------------------------------------------------------
def test_large_package_lock_parses_in_linear_time(tmp_path):
    n = 20_000
    lock = {"lockfileVersion": 3, "packages": {
        f"node_modules/p{i}": {"version": "1.0.0", "resolved": f"https://registry.npmjs.org/p{i}/-/x.tgz"}
        for i in range(n)}}
    path = tmp_path / "package-lock.json"
    path.write_text(json.dumps(lock, indent=2), encoding="utf-8")
    start = time.perf_counter()
    deps = npm.parse_package_lock(path, "package-lock.json", tmp_path).dependencies
    assert len(deps) == n and time.perf_counter() - start < 3.0
    lines = path.read_text(encoding="utf-8").splitlines()
    last = deps[-1]
    assert lines[last.line - 1].strip() == '"version": "1.0.0",' and f'"node_modules/p{n - 1}"' in lines[last.line - 2]


# 7 — mesmo pacote em várias versões (poetry/uv) cita a linha da própria versão -------------------
@pytest.mark.parametrize("name, parse", [("poetry.lock", py.parse_poetry_lock), ("uv.lock", py.parse_uv_lock)])
def test_duplicate_package_versions_cite_own_line(tmp_path, name, parse):
    src = 'source = { registry = "https://pypi.org/simple" }\n' if name == "uv.lock" else ""
    text = (f'[[package]]\nname = "numpy"\nversion = "1.24.4"\n{src}\n'
            f'[[package]]\nname = "numpy"\nversion = "2.0.1"\n{src}')
    (tmp_path / name).write_text(text, encoding="utf-8")
    deps = parse(tmp_path / name, name, tmp_path).dependencies
    lines = text.splitlines()
    assert {d.version: lines[d.line - 1] for d in deps} == \
        {"1.24.4": 'version = "1.24.4"', "2.0.1": 'version = "2.0.1"'}


def test_pipfile_same_name_in_default_and_develop(tmp_path):
    data = {"_meta": {"sources": [{"name": "pypi", "url": "https://pypi.org/simple"}]},
            "default": {"requests": {"index": "pypi", "version": "==2.0.0"}},
            "develop": {"requests": {"index": "pypi", "version": "==2.1.0"}}}
    text = json.dumps(data, indent=4)
    (tmp_path / "Pipfile.lock").write_text(text, encoding="utf-8")
    deps = py.parse_pipfile_lock(tmp_path / "Pipfile.lock", "Pipfile.lock", tmp_path).dependencies
    lines = text.splitlines()
    assert {d.version: lines[d.line - 1].strip() for d in deps} == \
        {"2.0.0": '"version": "==2.0.0"', "2.1.0": '"version": "==2.1.0"'}


# 10 — uma única regra de precedência ------------------------------------------------------------
@pytest.mark.parametrize("flag, env, expected", [(None, "true", True), (None, "false", False),
                                                 (False, "true", False), (True, "false", True)])
def test_resolve_vuln_scan(monkeypatch, flag, env, expected):
    monkeypatch.setenv("AUDITOR_VULN_SCAN", env)
    get_settings.cache_clear()
    assert node.resolve_vuln_scan(flag) is expected
    get_settings.cache_clear()


def test_entry_points_use_the_shared_rule():
    for rel in ("src/auditor/cli.py", "src/auditor/api/routes.py"):
        text = (Path(__file__).resolve().parents[2] / rel).read_text(encoding="utf-8")
        assert "resolve_vuln_scan(" in text and "settings.vuln_scan if" not in text, rel


# 1/9 — padrão do servidor e status para o frontend ----------------------------------------------
def _client():
    from fastapi.testclient import TestClient

    from auditor.api.main import app
    return TestClient(app, base_url="http://localhost")


@pytest.mark.parametrize("env, expected", [("true", True), ("false", False)])
def test_defaults_endpoint_exposes_vuln_scan_default(monkeypatch, env, expected):
    monkeypatch.setenv("AUDITOR_VULN_SCAN", env)
    get_settings.cache_clear()
    r = _client().get("/defaults")
    get_settings.cache_clear()
    assert r.status_code == 200 and r.json() == {"vuln_scan": expected}


def test_findings_include_rendered_scan_status(monkeypatch):
    from auditor.api import routes

    stats = {"enabled": True, "queried": 4, "vulnerable": 0, "skipped_private": 0,
             "errors": ["querybatch: timeout"], "truncated": False}

    class _Store:
        def get(self, audit_id):
            return object()

    class _Graph:
        def get_state(self, config):
            return type("S", (), {"values": {"dependency_scan": stats}})()

    monkeypatch.setattr(routes, "get_store", lambda: _Store())
    monkeypatch.setattr(routes, "get_graph", lambda: _Graph())
    body = _client().get("/audits/x/findings").json()
    assert body["dependency_scan_status"] == {"headline": "Varredura de dependências incompleta",
                                              "incomplete": True, "reasons": ["querybatch: timeout"]}
