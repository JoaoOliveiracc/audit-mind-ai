# CI & Quality Gates Specification (G37 + G38, closes G36, part of G40)

## Problem Statement

No CI exists (G37): lint, type-check, backend/frontend tests and the frontend build run only when
someone remembers. `mypy src` reports 17 errors (G38), so type-checking can't be enforced. The
frontend has two lockfiles and an invalid `pnpm-workspace.yaml` (placeholder value), which already
broke a local run (G40, partial). G36 (Vite cache committed) was fixed in `78dc680` but is still
listed as open.

## Goals
- [ ] Every push/PR to `main`/`develop` runs the same gates as `make ci` locally, on Python 3.10 and 3.12.
- [ ] `mypy src` reports 0 errors and is enforced.
- [ ] One JS package manager (npm).

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Dogfooding (auditor + SARIF upload in CI) | User: not now (needs LLM secret, costs tokens). Documented as next step. |
| Stricter mypy (`disallow_untyped_defs`) | User chose current config, zeroed. |
| Coverage thresholds | Not requested. |
| Removing `requirements.txt` (rest of G40) | Separate cleanup. |

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| JS package manager | npm (`npm ci`), remove `pnpm-lock.yaml` + `pnpm-workspace.yaml` | User decision; README/Makefile already use npm; lock verified in sync. | y |
| Python matrix | 3.10 and 3.12 | User decision. | y |
| mypy level | current defaults, 0 errors | User decision. | y |
| CI platform | GitHub Actions | Remote is GitHub. | y (agent) |
| Triggers | push + pull_request on `main`, `develop`; `workflow_dispatch` | Branches in use. | y (agent) |
| Node version | 22 LTS (fix loop 1; was 20, EOL since 2026-04) | Active LTS; the version used for the local build. | y (agent) |
| Action pinning | Node-24-runtime majors: `checkout@v5`, `setup-python@v6`, `setup-node@v6` (fix loop 1); `permissions: contents: read`, concurrency cancel | Runners force Node 24 for JS actions since 2026-06; node20-era majors are deprecated. SHA pinning optional later. | y (agent) |
| Test deps | add `httpx` to `[dev]` (TestClient needs it; today only transitive) | Explicit > accidental. | y (agent) |

**Open questions:** none.

## User Stories

### P1: Type-check is clean and enforceable ⭐ MVP
1. **TYPE-01** WHEN `mypy src` runs THEN it SHALL exit 0 with no errors.
2. **TYPE-02** WHEN `make typecheck` runs THEN it SHALL run `mypy src`.
3. **TYPE-03** The type fixes SHALL NOT change behavior: the full test suite SHALL pass with the same count.

### P1: Local gate mirrors CI ⭐ MVP
1. **GATE-01** WHEN `make ci` runs THEN it SHALL run, failing on the first error: `ruff check src tests`, `mypy src`, `pytest -q`, and in `frontend/`: `npm ci`, `vitest run`, `tsc --noEmit`, `vite build`.

### P1: GitHub Actions workflow ⭐ MVP
1. **CI-01** `.github/workflows/ci.yml` SHALL be valid workflow YAML triggered on push and pull_request to `main` and `develop`, and on `workflow_dispatch`.
2. **CI-02** A backend job SHALL run on Python 3.10 and 3.12 (matrix) and execute: install `.[dev,api]`, ruff, mypy, pytest.
3. **CI-03** A frontend job SHALL run on Node 22 (fix loop 1: Node 20 is EOL since 2026-04): `npm ci`, vitest, tsc, vite build, with `frontend/` as working directory and npm cache keyed on `frontend/package-lock.json`.
4. **CI-04** The workflow SHALL declare `permissions: contents: read` and a concurrency group that cancels superseded runs.
6. **CI-06** (fix loop 1) No gate SHALL be silently disabled: no `continue-on-error` and no `if:` on the jobs or gate steps, gate `run:` commands SHALL be exact (no `|| true`), Makefile gate recipes SHALL NOT use the `-` (ignore-error) prefix, and `pyproject` SHALL NOT `extend-select` lint rules.
5. **CI-05** The backend suite SHALL pass on Python 3.10 (verified locally in an isolated venv before relying on CI).

### P1: Reproducible tooling (added during T5) ⭐ MVP
1. **TOOL-01** The ruff rule set SHALL be declared explicitly in `pyproject.toml` and dev tools (ruff, mypy) SHALL have bounded version ranges, so a fresh install (CI) runs the same checks as the local venv. *(Found in T5: ruff 0.17 — a fresh install — expanded its default rules and reported 71 errors that ruff 0.15 does not.)*

### P1: Single package manager ⭐ MVP
1. **PKG-01** `frontend/pnpm-lock.yaml` and `frontend/pnpm-workspace.yaml` SHALL be removed and `npm ci` SHALL succeed from `package-lock.json`.

## Requirement Traceability

| ID | Task | Status |
| -- | ---- | ------ |
| TYPE-01..03 | T1 | Verified |
| PKG-01 | T2 | Verified |
| GATE-01, TYPE-02 | T3 | Verified |
| CI-01..04, CI-06 | T4 (+ fix loop 1) | Verified |
| CI-05, TOOL-01 | T5 | Verified |

**Coverage:** 13 total, 13 mapped.

## Success Criteria
- [ ] `make ci` green locally; backend green on a local Python 3.10 venv; first GitHub Actions run green after the user pushes.
