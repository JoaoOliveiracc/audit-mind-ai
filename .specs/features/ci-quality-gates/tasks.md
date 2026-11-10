# CI & Quality Gates Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement with the `tlc-spec-driven` skill (Execute flow + Critical Rules). If it cannot be activated, STOP and tell the user.

**Spec**: `.specs/features/ci-quality-gates/spec.md` · **Design**: inline below (no new architecture; config + type fixes) · **Status**: Done

## Design (inline)

- **mypy fixes** (no behavior change): `get_stream_writer = None` fallback → `Optional[Callable]` annotation; verify/adversarial stats → typed counters (`dict[str, int]` + separate `list[str]`) merged at return, or a `TypedDict`; `with_structured_output(...).invoke` results → `cast(Model, ...)`; `routes._summary(store.get(...))` → guard/assert; `AuditStore.list` shadowing builtin `list` in annotations → `builtins.list`.
- **Makefile**: `typecheck`, `frontend-ci`, `ci` (`lint typecheck test frontend-ci`, Make stops on first failure).
- **Workflow**: one file, two jobs (`backend` matrix 3.10/3.12, `frontend` Node 20); `actions/checkout@v4`, `actions/setup-python@v5` (pip cache), `actions/setup-node@v4` (npm cache, `cache-dependency-path: frontend/package-lock.json`).
- **Risk**: workflow can't run locally → validate YAML structure with a parse + key assertions, and run the same commands locally (`make ci`, Python 3.10 venv via `uv`). Real proof = first Actions run after the user pushes.

## Test Coverage Matrix

| Layer | Test Type | Expectation | Run |
| ----- | --------- | ----------- | --- |
| Type fixes in `src/` | existing suite (behavior unchanged) + mypy | 0 mypy errors; same pytest count | `.venv/bin/mypy src && .venv/bin/pytest -q` |
| Makefile / workflow / lockfiles | config — structural check + executing the commands | per AC | `make ci`; YAML parse script |

## Gate Check Commands

| Gate | Command |
| ---- | ------- |
| Build | `make ci` (after T3); before T3: `.venv/bin/ruff check src tests && .venv/bin/mypy src && .venv/bin/pytest -q` |

## Execution Plan
`T1 → T2 → T3 → T4 → T5 → T6`

## Task Breakdown

### T1: Zero mypy errors — `src/auditor/**` (7 files) · Req TYPE-01, TYPE-03 · Gate: mypy 0 + pytest 112 · Commit `fix(types): make mypy pass with zero errors`
### T2: npm only — delete `frontend/pnpm-lock.yaml`, `frontend/pnpm-workspace.yaml`; `httpx` in `[dev]` · Req PKG-01 · Gate: `npm ci` in a scratch copy + vitest · Commit `build: standardize on npm and declare httpx for tests`
### T3: Makefile `typecheck`/`frontend-ci`/`ci` · Req GATE-01, TYPE-02 · Gate: `make ci` · Commit `build: add make ci mirroring the CI pipeline`
### T4: `.github/workflows/ci.yml` · Req CI-01..04 · Gate: YAML structural check (triggers, matrix, steps, permissions, concurrency) · Commit `ci: add GitHub Actions workflow for backend and frontend`
### T5: Python 3.10 check — `uv` venv in scratchpad, install `.[dev,api]`, run ruff/mypy/pytest · Req CI-05 · Gate: green on 3.10 · Commit: none (verification only; fixes, if any, become their own commit)
### T6: Docs — README (CI badge, `make ci`), DOCUMENTACAO §10.3 (G36/G37/G38 ✅, G40 partial), USAGE · Commit `docs: document CI and quality gates (G36/G37/G38)`

## Validation
Granularity ✅ · deps linear ✅ · co-location: T1 uses existing suite (no behavior change) + mypy gate; T2–T4 config with executable checks ✅.
