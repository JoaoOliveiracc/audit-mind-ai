# API Hardening Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** If the skill cannot be activated, STOP and tell the user.

**Design**: `.specs/features/api-hardening/design.md`
**Status**: Done

## Test Coverage Matrix

> Same matrix as `audit-retention/tasks.md` (guidelines: none — strong defaults; floor from existing tests).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Middleware / service (`api/security.py`, `store`, `runner`) | unit | 1:1 to ACs, every edge case | `tests/test_*.py` | `.venv/bin/pytest -q` |
| API routes | integration (TestClient) | happy + every status path | `tests/test_api.py` | `.venv/bin/pytest -q` |
| CLI | integration (CliRunner) | each exit path | `tests/test_cli.py` | `.venv/bin/pytest -q` |
| Frontend components | unit (Vitest + Testing Library) | every UI AC of the component | `frontend/src/components/*.test.tsx` | `./node_modules/.bin/vitest run` |
| App wiring | unit (client/SSE mocked) — fix loop 1 | UI ACs wired in App | `frontend/src/App.test.tsx` | `./node_modules/.bin/vitest run` |

## Gate Check Commands

| Gate Level | When | Command |
| ---------- | ---- | ------- |
| Quick | backend tasks | `.venv/bin/pytest -q` |
| Full | frontend tasks | `cd frontend && ./node_modules/.bin/vitest run && ./node_modules/.bin/tsc --noEmit -p .` |
| Build | end of phase | quick + `ruff check src tests` + full |

## Execution Plan

### Phase 1: Backend
```
T1 → T2 → T3 → T4 → T5
```
### Phase 2: Frontend + docs
```
T6 → T7
```

## Task Breakdown

### T1: Host allowlist middleware
**Where**: `src/auditor/api/security.py` (new), `config.py`, `api/main.py`, `tests/test_security.py` (new), `tests/test_api.py` (base_url only) · **Depends on**: None · **Req**: HOST-01..04
**Done when**: tests for allowed hosts (incl. `[::1]:8020`, uppercase), rejected hosts (with port; route not executed), missing Host, extras via setting; existing API tests pass with `base_url` change · quick gate
**Tests**: unit + integration · **Gate**: quick · **Commit**: `feat(api): reject non-local Host headers (DNS rebinding)`

### T2: Non-local bind guard
**Where**: `src/auditor/cli.py`, `tests/test_cli.py` · **Depends on**: T1 · **Req**: BIND-01..03
**Done when**: CliRunner tests with `uvicorn.run` monkeypatched: local hosts start; non-local w/o flag exit 2 + no start; with flag warning + start · quick gate
**Tests**: integration · **Gate**: quick · **Commit**: `feat(cli): require --allow-remote for non-local bind`

### T3: Orphan reconciliation at startup
**Where**: `api/store.py`, `api/main.py` (lifespan), `tests/test_retention.py`→ no; `tests/test_lifecycle.py` (new) · **Depends on**: T2 · **Req**: ORPH-01
**Done when**: store test (each status → expected); lifespan test (TestClient context manager with tmp store) · quick gate
**Tests**: unit + integration · **Gate**: quick · **Commit**: `feat(api): mark orphaned audits as interrupted on startup`

### T4: Runner resume mode
**Where**: `api/runner.py`, `tests/test_lifecycle.py` · **Depends on**: T3 · **Req**: RES-01..03
**Done when**: fake-graph tests for pending interrupt (clarification re-emitted, waiting_input, answers → completed), pending nodes (`stream(None)` → completed), nothing pending (completed with state paths, no node run) · quick gate
**Tests**: unit · **Gate**: quick · **Commit**: `feat(api): resume audits from their last checkpoint`

### T5: POST /audits/{id}/resume
**Where**: `api/routes.py`, `tests/test_api.py` · **Depends on**: T4 · **Req**: RES-04..07
**Done when**: TestClient tests 200 (+ registry has runner), 404, 409 (completed, live), 400 (LLMConfigError, status unchanged) · build gate (end of phase 1)
**Tests**: integration · **Gate**: build · **Commit**: `feat(api): add POST /audits/{id}/resume`

### T6: Resume in the history UI
**Where**: `frontend/src/components/History.tsx`, `History.test.tsx`, `frontend/src/api/client.ts`, `frontend/src/App.tsx` · **Depends on**: T5 · **Req**: UI-01..03
(App wiring included here — required prop; avoids the compile split seen in audit-retention.)
**Done when**: Vitest for UI-01/UI-02; tsc clean (UI-03 wiring) · full gate
**Tests**: unit (component) + none (App) · **Gate**: full · **Commit**: `feat(frontend): resume interrupted audits from history`

### T7: Documentation
**Where**: `DOCUMENTACAO.md`, `README.md`, `docs/USAGE.md`, `docs/ARCHITECTURE.md`, `SECURITY.md`, `docs/ROADMAP.md`, `.env.example` · **Depends on**: T6
**Done when**: build gate · **Commit**: `docs: document Host allowlist, --allow-remote and resume (G27/G31)`

## Validation

Granularity: T1 (1 middleware + its wiring/setting, cohesive ⚠️ OK), T2–T5 (1 unit each ✅), T6 (1 component + its wiring ⚠️ OK cohesive), T7 docs ✅.
Diagram cross-check: T2←T1, T3←T2, T4←T3, T5←T4, T6←T5, T7←T6 — ✅; no backward-phase deps.
Test co-location: T1 unit+integration ✅ · T2 integration ✅ · T3 unit+integration ✅ · T4 unit ✅ · T5 integration ✅ · T6 unit (component) + none (App) ✅ · T7 none ✅.

## Fix loop 1 (after Verifier FAIL)

| Gap | Fix | Tests |
| --- | --- | ----- |
| 1 Double resume / resume×delete race | `_lifecycle_lock` in `routes.py`; state re-checked inside the lock after the (slow) LLM validation | `test_concurrent_double_resume_starts_only_one_runner`, `test_delete_during_resume_validation_does_not_500` |
| 2 HOST-04 wiring untested | subprocess test against the real app with `AUDITOR_ALLOWED_HOSTS` (+ tmp `HOME`) | `test_real_app_reads_allowed_hosts_from_env` |
| 6 Middleware order | preflight with foreign Host → 400 | `test_cors_preflight_with_foreign_host_is_rejected` |
| Hardening (Verifier review) | strict `Host` grammar; duplicate Host rejected; invalid extras never add `""` (found during fix) | `test_malformed_hosts_are_rejected`, `test_duplicate_host_headers_are_rejected`, `test_invalid_extra_does_not_allow_empty_or_malformed_host` |
| 4 UI-01 only vs `completed` | all non-interrupted statuses | `History.test.tsx` (`it.each`) |
| 5 RES-01 flake | wait for `waiting_input` status | `test_lifecycle.py` |
| 7 RES-05 weak | assert `detail` | `test_resume_unknown_returns_404` |
| 3 UI-03 untested | **Matrix change:** App layer now has a unit test (client/SSE mocked) | `frontend/src/App.test.tsx` |
