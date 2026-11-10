"""Lockfiles Python (spec: .specs/features/vuln-scan — LOCK-01..04, OSV-01 normalização)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from auditor.vulnscan.lockfiles import python as py


def _write(root: Path, name: str, text: str) -> Path:
    p = root / name
    p.write_text(text, encoding="utf-8")
    return p


def _deps(result):
    return {d.name: d for d in result.dependencies}


def _line(path: Path, needle: str, after: str) -> int:
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if after in ln)
    return next(i for i in range(start, len(lines)) if needle in lines[i]) + 1


# --- poetry.lock ----------------------------------------------------------------------
POETRY = '''[[package]]
name = "Django"
version = "3.2.0"
optional = false
groups = ["main"]

[[package]]
name = "pytest"
version = "7.0.0"
optional = false
category = "dev"

[[package]]
name = "corp_lib"
version = "1.0.0"
optional = false
groups = ["main"]

[package.source]
type = "legacy"
url = "https://nexus.corp/simple"
reference = "corp"

[[package]]
name = "from-git"
version = "0.1.0"
groups = ["main"]

[package.source]
type = "git"
url = "https://github.com/x/y.git"
reference = "main"

[metadata]
lock-version = "2.0"
'''


def test_poetry(tmp_path):
    path = _write(tmp_path, "poetry.lock", POETRY)
    deps = _deps(py.parse_poetry_lock(path, "poetry.lock", tmp_path))
    dj = deps["django"]                                                   # PEP 503
    assert (dj.ecosystem, dj.version, dj.dev, dj.private) == ("PyPI", "3.2.0", False, False)
    assert dj.line == _line(path, 'version = "3.2.0"', 'name = "Django"')
    assert deps["pytest"].dev is True
    assert deps["corp-lib"].private is True and deps["from-git"].private is True


# --- uv.lock --------------------------------------------------------------------------
UV = '''version = 1
requires-python = ">=3.10"

[[package]]
name = "app"
version = "0.1.0"
source = { editable = "." }
dependencies = [
    { name = "django" },
]

[package.dev-dependencies]
dev = [
    { name = "pytest" },
]

[[package]]
name = "django"
version = "3.2.0"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "pytest"
version = "7.0.0"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "internal"
version = "2.0.0"
source = { registry = "https://nexus.corp/simple" }
'''


def test_uv(tmp_path):
    path = _write(tmp_path, "uv.lock", UV)
    deps = _deps(py.parse_uv_lock(path, "uv.lock", tmp_path))
    assert deps["django"].private is False and deps["django"].dev is False
    assert deps["django"].line == _line(path, 'version = "3.2.0"', 'name = "django"')
    assert deps["pytest"].dev is True                                     # só em dev-dependencies
    assert deps["internal"].private is True
    assert "app" not in deps or deps["app"].private                       # o próprio projeto


# --- Pipfile.lock ---------------------------------------------------------------------
PIPFILE = {
    "_meta": {"sources": [{"name": "pypi", "url": "https://pypi.org/simple", "verify_ssl": True},
                          {"name": "corp", "url": "https://nexus.corp/simple", "verify_ssl": True}]},
    "default": {"requests": {"hashes": [], "index": "pypi", "version": "==2.19.0"},
                "corp-thing": {"index": "corp", "version": "==1.0.0"},
                "local": {"path": ".", "editable": True}},
    "develop": {"pytest": {"index": "pypi", "version": "==7.0.0"}},
}


def test_pipfile_lock(tmp_path):
    path = _write(tmp_path, "Pipfile.lock", json.dumps(PIPFILE, indent=4))
    deps = _deps(py.parse_pipfile_lock(path, "Pipfile.lock", tmp_path))
    req = deps["requests"]
    assert (req.version, req.private, req.dev) == ("2.19.0", False, False)
    assert req.line == _line(path, '"version"', '"requests"')
    assert deps["corp-thing"].private is True
    assert deps["pytest"].dev is True
    assert "local" not in deps or deps["local"].private


# --- requirements*.txt ----------------------------------------------------------------
REQS = """# comentário
Django==3.2.0
requests[security]==2.19.0 ; python_version >= "3.8"
flask>=2.0
urllib3==1.26.0 \\
    --hash=sha256:abc
git+https://github.com/x/y.git#egg=y
"""


def test_requirements_pins_only(tmp_path):
    path = _write(tmp_path, "requirements.txt", REQS)
    deps = _deps(py.parse_requirements(path, "requirements.txt", tmp_path))
    assert set(deps) == {"django", "requests", "urllib3"}                  # só pins exatos
    assert deps["django"].line == 2 and deps["requests"].line == 3
    assert deps["requests"].version == "2.19.0" and deps["urllib3"].version == "1.26.0"
    assert not any(d.dev or d.private for d in deps.values())


@pytest.mark.parametrize("fname", ["requirements-dev.txt", "requirements-test.txt",
                                   "dev-requirements.txt", "requirements-dev-extra.txt"])
def test_requirements_dev_filenames(tmp_path, fname):                     # LOCK-02
    path = _write(tmp_path, fname, "pytest==7.0.0\n")
    assert _deps(py.parse_requirements(path, fname, tmp_path))["pytest"].dev is True


@pytest.mark.parametrize("opt", ["--index-url https://nexus.corp/simple",
                                 "-i https://nexus.corp/simple",
                                 "--extra-index-url https://nexus.corp/simple"])
def test_requirements_private_index_skips_whole_file(tmp_path, opt):      # LOCK-03
    path = _write(tmp_path, "requirements.txt", f"{opt}\nDjango==3.2.0\n")
    result = py.parse_requirements(path, "requirements.txt", tmp_path)
    assert result.dependencies == [] and result.skipped_files == ["requirements.txt"]


def test_requirements_public_index_is_fine(tmp_path):
    path = _write(tmp_path, "requirements.txt", "--index-url https://pypi.org/simple\nDjango==3.2.0\n")
    assert _deps(py.parse_requirements(path, "requirements.txt", tmp_path))["django"].private is False


@pytest.mark.parametrize("parser, name, text", [
    (py.parse_poetry_lock, "poetry.lock", "[[package]\nname ="),
    (py.parse_uv_lock, "uv.lock", "= nada"),
    (py.parse_pipfile_lock, "Pipfile.lock", "{ não json"),
])
def test_python_malformed_never_raises(tmp_path, parser, name, text):    # LOCK-04
    path = _write(tmp_path, name, text)
    result = parser(path, name, tmp_path)
    assert result.dependencies == [] and len(result.errors) == 1
