"""Regressões do code review da fase 1 (vuln-scan)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from auditor.vulnscan.lockfiles import npm
from auditor.vulnscan.lockfiles import python as py
from auditor.vulnscan.lockfiles.registry_config import load_registry_config
from auditor.vulnscan.runtime import classify
from auditor.vulnscan.versions import in_range, version_key

ROOT = Path(__file__).resolve().parents[2]


def _w(root: Path, name: str, text, binary: bool = False) -> Path:
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text) if binary else p.write_text(text, encoding="utf-8")
    return p


def _deps(result):
    return {d.name: d for d in result.dependencies}


# 1 — dependências de runtime declaradas (não só no [dev]) -------------------------------
def test_runtime_dependencies_are_declared_in_core():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    core = re.search(r"^dependencies = \[\n(.*?)^\]", text, re.M | re.S).group(1)
    for req in ('"pyyaml>=6"', '"packaging>=23"', "\"tomli>=2; python_version < '3.11'\""):
        assert req in core, req


# 2 — alias npm: consulta o pacote REAL, nunca o nome do alias ----------------------------
def test_package_lock_alias_uses_real_name(tmp_path):
    lock = {"lockfileVersion": 3, "packages": {"node_modules/my-lodash": {
        "name": "lodash", "version": "4.17.15",
        "resolved": "https://registry.npmjs.org/lodash/-/lodash-4.17.15.tgz"}}}
    deps = _deps(npm.parse_package_lock(_w(tmp_path, "package-lock.json", json.dumps(lock)),
                                        "package-lock.json", tmp_path))
    assert set(deps) == {"lodash"} and not deps["lodash"].private


def test_yarn_v1_alias_uses_real_name(tmp_path):
    text = ('# yarn lockfile v1\n\n\n"my-lodash@npm:lodash@^4.17.15":\n  version "4.17.15"\n'
            '  resolved "https://registry.yarnpkg.com/lodash/-/lodash-4.17.15.tgz#a"\n')
    deps = _deps(npm.parse_yarn_lock(_w(tmp_path, "yarn.lock", text), "yarn.lock", tmp_path))
    assert set(deps) == {"lodash"}


# 3 — índice desconhecido no Pipfile.lock ⇒ privado ---------------------------------------
def test_pipfile_unknown_index_is_private(tmp_path):
    lock = {"_meta": {"sources": [{"name": "pypi", "url": "https://pypi.org/simple"}]},
            "default": {"acme-internal": {"index": "internal", "version": "==2.0.0"}}}
    deps = _deps(py.parse_pipfile_lock(_w(tmp_path, "Pipfile.lock", json.dumps(lock)),
                                       "Pipfile.lock", tmp_path))
    assert deps["acme-internal"].private is True


# 4 — load_registry_config nunca lança ---------------------------------------------------
@pytest.mark.parametrize("name, content, binary", [
    (".yarnrc.yml", "npmRegistryServer: \"https://x\"\n# \xe9\n".encode("latin-1"), True),
    (".yarnrc.yml", "npmScopes: [foo]\n", False),
    (".yarnrc.yml", "- só\n- lista\n", False),
    (".npmrc", b"registry=https://nexus.corp/\n\xff\xfe", True),
])
def test_registry_config_never_raises(tmp_path, name, content, binary):
    _w(tmp_path, name, content, binary)
    load_registry_config(tmp_path)          # não pode lançar


def test_unreadable_npmrc_does_not_break_parsers(tmp_path):
    (tmp_path / ".npmrc").mkdir()            # "arquivo" que é diretório → OSError ao ler
    lock = {"lockfileVersion": 3, "packages": {"node_modules/a": {
        "version": "1.0.0", "resolved": "https://registry.npmjs.org/a/-/a-1.0.0.tgz"}}}
    result = npm.parse_package_lock(_w(tmp_path, "package-lock.json", json.dumps(lock)),
                                    "package-lock.json", tmp_path)
    assert [d.name for d in result.dependencies] == ["a"]


# 5/6 — classificação de faixas ----------------------------------------------------------
@pytest.mark.parametrize("product, value, kind, cycle", [
    ("python", "3.x", "unknown", None), ("php", "8.x", "unknown", None),     # minor curinga
    ("nodejs", "18.x", "range", "18"),                                        # Node: ciclo = major
    ("python", ">=3.6, !=3.7.*", "range", "3.6"),                              # != não é limite inferior
    ("python", ">=3.8,!=3.9.0", "range", "3.8"),
])
def test_range_wildcards_and_not_equal(product, value, kind, cycle):
    got = classify(product, value)
    assert (got.kind, got.cycle) == (kind, cycle)


# 7 — ordem de pré-release do Composer ----------------------------------------------------
@pytest.mark.parametrize("older, newer", [
    ("1.0.0-beta9", "1.0.0-beta10"), ("1.0.0-beta2", "1.0.0-RC1"), ("1.0.0-alpha3", "1.0.0-beta1"),
    ("1.0.0-dev", "1.0.0-alpha1"), ("1.0.0-RC2", "1.0.0"), ("1.0.0-rc1", "1.0.0-RC2"),
])
def test_packagist_prerelease_order(older, newer):
    assert version_key("Packagist", older) < version_key("Packagist", newer)


def test_packagist_in_range_beta10_after_fix_beta9():
    assert in_range("Packagist", "1.0.0-beta10", "0", "1.0.0-beta9") is False


# 8 — pnpm v5 e entradas não reconhecidas -------------------------------------------------
def test_pnpm_v5_keys(tmp_path):
    text = ("lockfileVersion: 5.4\n\npackages:\n\n  /lodash/4.17.21:\n    resolution: {integrity: sha512-x}\n"
            "    dev: false\n\n  /@types/node/18.0.0:\n    resolution: {integrity: sha512-y}\n    dev: true\n")
    deps = _deps(npm.parse_pnpm_lock(_w(tmp_path, "pnpm-lock.yaml", text), "pnpm-lock.yaml", tmp_path))
    assert (deps["lodash"].version, deps["@types/node"].version, deps["@types/node"].dev) == \
        ("4.17.21", "18.0.0", True)


def test_pnpm_unrecognized_entries_are_reported(tmp_path):
    text = "lockfileVersion: '9.0'\n\npackages:\n\n  semnada:\n    resolution: {integrity: sha512-x}\n"
    result = npm.parse_pnpm_lock(_w(tmp_path, "pnpm-lock.yaml", text), "pnpm-lock.yaml", tmp_path)
    assert result.dependencies == [] and len(result.errors) == 1 and "não reconhecida" in result.errors[0]


# 9 — requirements: ===, --find-links e includes -r/-c ------------------------------------
def test_requirements_triple_equals(tmp_path):
    deps = _deps(py.parse_requirements(_w(tmp_path, "requirements.txt", "foo===1.0\n"),
                                       "requirements.txt", tmp_path))
    assert deps["foo"].version == "1.0"


@pytest.mark.parametrize("opt", ["--find-links https://internal/wheels", "-f https://internal/wheels",
                                 "--find-links=./wheels"])
def test_requirements_find_links_skips_file(tmp_path, opt):
    result = py.parse_requirements(_w(tmp_path, "requirements.txt", f"{opt}\nacme==2.0\n"),
                                   "requirements.txt", tmp_path)
    assert result.dependencies == [] and result.skipped_files == ["requirements.txt"]


@pytest.mark.parametrize("include", ["-r base.txt", "--requirement base.txt", "-c base.txt",
                                     "--constraint=base.txt"])
def test_requirements_private_index_in_included_file_skips(tmp_path, include):
    _w(tmp_path, "base.txt", "--extra-index-url https://nexus.corp/simple\n")
    result = py.parse_requirements(_w(tmp_path, "requirements.txt", f"{include}\nacme==2.0\n"),
                                   "requirements.txt", tmp_path)
    assert result.dependencies == [] and result.skipped_files == ["requirements.txt"]


def test_requirements_include_outside_root_or_cyclic_is_safe(tmp_path):
    _w(tmp_path, "a.txt", "-r requirements.txt\n")
    result = py.parse_requirements(_w(tmp_path, "requirements.txt", "-r a.txt\n-r ../../etc/x.txt\nok==1.0\n"),
                                   "requirements.txt", tmp_path)
    assert [d.name for d in result.dependencies] == ["ok"]
