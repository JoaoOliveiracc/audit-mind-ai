"""Configuração de CI/qualidade (spec: .specs/features/ci-quality-gates — CI-01..04, GATE-01,
TYPE-02, TOOL-01, PKG-01). O workflow só roda no GitHub; aqui travamos sua estrutura."""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
JOBS = WORKFLOW["jobs"]


def _runs(job: str) -> str:
    return "\n".join(step.get("run", "") for step in JOBS[job]["steps"])


def _uses(job: str, action: str) -> dict:
    return next(s for s in JOBS[job]["steps"] if s.get("uses", "").startswith(action))


def test_ci01_triggers():
    on = WORKFLOW[True]  # YAML 1.1: a chave `on` é lida como True
    assert set(on) == {"push", "pull_request", "workflow_dispatch"}
    assert on["push"]["branches"] == ["main", "develop"]
    assert on["pull_request"]["branches"] == ["main", "develop"]


def test_ci02_backend_matrix_and_steps():
    assert JOBS["backend"]["strategy"]["matrix"]["python-version"] == ["3.10", "3.12"]
    runs = _runs("backend")
    for cmd in ('pip install -e ".[dev,api]"', "ruff check src tests", "mypy src", "pytest -q"):
        assert cmd in runs
    assert _uses("backend", "actions/setup-python")["with"]["python-version"] == \
        "${{ matrix.python-version }}"


def test_ci03_frontend_job():
    job = JOBS["frontend"]
    assert job["defaults"]["run"]["working-directory"] == "frontend"
    node = _uses("frontend", "actions/setup-node")["with"]
    assert node["node-version"] == "22"          # Node 20 é EOL desde 2026-04
    assert node["cache"] == "npm"
    assert node["cache-dependency-path"] == "frontend/package-lock.json"
    runs = _runs("frontend")
    for cmd in ("npm ci", "npm test", "npm run build"):
        assert cmd in runs


def test_ci04_least_privilege_and_concurrency():
    assert WORKFLOW["permissions"] == {"contents": "read"}
    assert WORKFLOW["concurrency"]["cancel-in-progress"] is True
    assert "github.ref" in WORKFLOW["concurrency"]["group"]


def test_gate01_make_ci_mirrors_the_pipeline():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert re.search(r"^ci: lint typecheck test frontend-ci$", makefile, re.M)
    assert re.search(r"^typecheck:\n\t.*mypy src$", makefile, re.M)                    # TYPE-02
    assert re.search(r"^frontend-ci:\n(?:\t@#.*\n)?\t.*npm ci.*npm test.*npm run build", makefile, re.M)
    assert re.search(r"^lint:\n\t.*ruff check src tests$", makefile, re.M)


def test_frontend_build_script_includes_typecheck():
    scripts = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))["scripts"]
    assert scripts["build"] == "tsc --noEmit && vite build"
    assert scripts["test"] == "vitest run"


def test_tool01_explicit_rules_and_bounded_dev_tools():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'^\[tool\.ruff\.lint\]\n(?:#.*\n)*select = \["E4", "E7", "E9", "F"\]',
                     pyproject, re.M)
    assert '"ruff>=0.15,<0.18"' in pyproject
    assert '"mypy>=2.1,<3"' in pyproject
    assert '"httpx>=0.27"' in pyproject


def test_pkg01_npm_only():
    assert not (ROOT / "frontend/pnpm-lock.yaml").exists()
    assert not (ROOT / "frontend/pnpm-workspace.yaml").exists()
    assert (ROOT / "frontend/package-lock.json").is_file()


# --- CI-03/CI-04 (fix loop 1): actions na geração de runtime Node 24 -------------------
_MIN_MAJOR = {"actions/checkout": 5, "actions/setup-python": 6, "actions/setup-node": 6}


def test_actions_use_node24_runtime_majors():
    for job in JOBS.values():
        for step in job["steps"]:
            name, _, ref = step.get("uses", "").partition("@")
            if name in _MIN_MAJOR:
                assert int(ref.lstrip("v").split(".")[0]) >= _MIN_MAJOR[name], step["uses"]


# --- CI-06: nenhum gate desligado "por baixo" ----------------------------------------
_GATE_RUNS = {
    "backend": {"Lint (ruff)": "ruff check src tests", "Tipos (mypy)": "mypy src",
                "Testes (pytest)": "pytest -q"},
    "frontend": {"Testes (vitest)": "npm test", "Tipos + build (tsc + vite build)": "npm run build"},
}


def test_ci06_jobs_and_gate_steps_cannot_be_silently_disabled():
    for name, job in JOBS.items():
        assert "if" not in job and "continue-on-error" not in job, name
        steps = {s.get("name"): s for s in job["steps"]}
        for step in job["steps"]:
            assert "continue-on-error" not in step and "if" not in step, step
        for step_name, command in _GATE_RUNS[name].items():
            assert steps[step_name]["run"].strip() == command      # exato: sem "|| true"


def test_ci06_make_gate_recipes_do_not_ignore_errors():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    for target in ("lint", "typecheck", "test", "frontend-ci"):
        body = re.search(rf"^{target}:\n((?:\t.*\n)+)", makefile, re.M)
        assert body, target
        for line in body.group(1).splitlines():
            assert not line.startswith("\t-"), (target, line)
            assert "|| true" not in line, (target, line)


def test_ci06_lint_rules_not_widened_implicitly():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "extend-select" not in pyproject
