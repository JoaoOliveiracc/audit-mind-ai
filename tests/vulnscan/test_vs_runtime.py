"""Runtime declarado (spec: .specs/features/vuln-scan — RT-01, RT-02 classificação, RT-05)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from auditor.vulnscan.runtime import classify, detect_in_file


def _write(root: Path, name: str, text: str) -> Path:
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _decls(root, name, text):
    path = _write(root, name, text)
    return detect_in_file(path, name)


# --- RT-01: fontes ----------------------------------------------------------------------
def test_nvmrc_and_node_version(tmp_path):
    (d,) = _decls(tmp_path, ".nvmrc", "# comentário\nv20.11.1\n")
    assert (d.product, d.value, d.file, d.line, d.evidence) == ("nodejs", "20.11.1", ".nvmrc", 2, "v20.11.1")
    (d2,) = _decls(tmp_path, ".node-version", "18\n")
    assert (d2.product, d2.value, d2.line) == ("nodejs", "18", 1)


def test_package_json_engines(tmp_path):
    text = json.dumps({"name": "x", "engines": {"node": ">=18", "npm": ">=9"}}, indent=2)
    (d,) = _decls(tmp_path, "package.json", text)
    assert (d.product, d.value, d.evidence) == ("nodejs", ">=18", '"node": ">=18",')
    assert text.splitlines()[d.line - 1].strip() == '"node": ">=18",'


def test_composer_require_php(tmp_path):
    text = json.dumps({"require": {"php": "^8.1", "guzzlehttp/guzzle": "^7"}}, indent=4)
    (d,) = _decls(tmp_path, "composer.json", text)
    assert (d.product, d.value) == ("php", "^8.1") and '"php": "^8.1"' in d.evidence


def test_python_version_and_requires_python(tmp_path):
    (d,) = _decls(tmp_path, ".python-version", "3.11.4\n")
    assert (d.product, d.value) == ("python", "3.11.4")
    (d2,) = _decls(tmp_path, "pyproject.toml", '[project]\nname = "x"\nrequires-python = ">=3.9"\n')
    assert (d2.product, d2.value, d2.line) == ("python", ">=3.9", 3)


def test_dockerfile_multistage_flags_registry_and_args(tmp_path):
    text = ("ARG NODE_VERSION=20\n"
            "FROM --platform=linux/amd64 docker.io/library/node:20.11-alpine AS build\n"
            "FROM php:8.1-fpm\n"
            "FROM python:3.12.4-slim-bookworm@sha256:abc AS py\n"
            "FROM node:${NODE_VERSION}\n"
            "FROM nginx:1.25\n")
    decls = _decls(tmp_path, "Dockerfile", text)
    assert [(d.product, d.value, d.line) for d in decls] == [
        ("nodejs", "20.11", 2), ("php", "8.1", 3), ("python", "3.12.4", 4), ("nodejs", "${NODE_VERSION}", 5)]


def test_dockerfile_variants_are_detected(tmp_path):
    assert _decls(tmp_path, "docker/Dockerfile.prod", "FROM node:18\n")[0].value == "18"
    assert _decls(tmp_path, "api.Dockerfile", "FROM python:3.10\n")[0].value == "3.10"


def test_unrelated_files_yield_nothing(tmp_path):
    assert _decls(tmp_path, "README.md", "node 20\n") == []
    assert _decls(tmp_path, "package.json", '{"name": "x"}') == []
    assert _decls(tmp_path, "package.json", "{ não é json") == []      # nunca lança


# --- RT-02: classificação por runtime ---------------------------------------------------
@pytest.mark.parametrize("product, value, kind, cycle, exact", [
    # Node: ciclo = major; exato = major.minor[.patch]
    ("nodejs", "20", "cycle", "20", None),
    ("nodejs", "20.11", "exact", "20", "20.11"),
    ("nodejs", "20.11.1", "exact", "20", "20.11.1"),
    # PHP/Python: ciclo = major.minor; exato = major.minor.patch
    ("php", "8.1", "cycle", "8.1", None),
    ("php", "8.1.27", "exact", "8.1", "8.1.27"),
    ("python", "3.11", "cycle", "3.11", None),
    ("python", "3.11.4", "exact", "3.11", "3.11.4"),
    # faixas → ciclo mínimo
    ("nodejs", ">=18", "range", "18", None),
    ("nodejs", "18.x || 20.x", "range", "18", None),
    ("nodejs", "^20.11.0", "range", "20", None),
    ("php", "^8.1", "range", "8.1", None),
    ("php", ">=8.1 <8.4", "range", "8.1", None),
    ("php", ">=8", "range", "8.0", None),
    ("python", ">=3.9", "range", "3.9", None),
    ("python", "~=3.10", "range", "3.10", None),
    # desconhecidos (RT-04)
    ("nodejs", "lts/*", "unknown", None, None),
    ("nodejs", "lts", "unknown", None, None),
    ("nodejs", "${NODE_VERSION}", "unknown", None, None),
    ("nodejs", "*", "unknown", None, None),
    ("python", "pypy3.10", "unknown", None, None),
])
def test_classify(product, value, kind, cycle, exact):
    got = classify(product, value)
    assert (got.kind, got.cycle, got.exact) == (kind, cycle, exact)


# --- RT-05: cada declaração é independente ---------------------------------------------
def test_each_declaration_is_returned_separately(tmp_path):
    text = json.dumps({"engines": {"node": ">=20"}}, indent=2)
    a = _decls(tmp_path, ".nvmrc", "18\n")
    b = _decls(tmp_path, "package.json", text)
    assert [d.value for d in a + b] == ["18", ">=20"]
