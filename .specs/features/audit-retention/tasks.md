# Audit Retention Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path.

**If the skill cannot be activated, STOP and tell the user — do not proceed without it.**

---

**Design**: `.specs/features/audit-retention/design.md`
**Status**: Done (T6+T7 gated and to be committed together — compile dependency)

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec. Guidelines found: none (no AGENTS.md/CONTRIBUTING; `pyproject.toml` [tool.pytest], `frontend/package.json` scripts, `Makefile` test/lint) — strong defaults applied. Floor sampled from `tests/test_api.py`, `tests/test_audit.py`, `tests/test_verify.py`, `frontend/src/state/*.test.ts`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Graph nodes (`nodes/*`) | unit (fake LLM / real in-memory saver) | 1:1 to spec ACs | `tests/test_*.py` | `.venv/bin/pytest -q` |
| Domain/service (`api/retention.py`, `api/store.py`) | unit (tmp sqlite + tmp files) | All branches; 1:1 to ACs; every edge case | `tests/test_retention.py` | `.venv/bin/pytest -q` |
| API routes | integration (TestClient, injected deps) | Happy + every status code path (204/404/409/500) | `tests/test_api.py` | `.venv/bin/pytest -q` |
| CLI commands | integration (Typer CliRunner) | Happy + each documented exit path | `tests/test_cli.py` | `.venv/bin/pytest -q` |
| Frontend components | unit (Vitest + Testing Library) | Every UI AC for the component | `frontend/src/components/*.test.tsx` | `cd frontend && npx vitest run` |
| Frontend App wiring / API client | none (no existing App/client tests) | build gate only | — | `cd frontend && npx tsc --noEmit` |

## Gate Check Commands

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Backend tasks with unit/integration tests | `.venv/bin/pytest -q` |
| Full | Frontend component tasks | `cd frontend && npx vitest run && npx tsc --noEmit` |
| Build | End of each phase | `.venv/bin/pytest -q && .venv/bin/ruff check src tests && (cd frontend && npx vitest run && npx tsc --noEmit)` |

---

## Execution Plan

### Phase 1: Backend

```
T1 → T2 → T3 → T4 → T5
```

### Phase 2: Frontend + docs

```
T6 → T7 → T8
```

---

## Task Breakdown

### T1: Disable sub-agent checkpointing
**What**: `create_react_agent(..., checkpointer=False)` in `_investigate_dimension`.
**Where**: `src/auditor/nodes/audit.py`, test in `tests/test_audit.py`
**Depends on**: None · **Requirement**: SUB-01
**Done when**:
- [ ] Test runs `_investigate_dimension` with a tool-calling fake LLM inside a parent graph node (same thread) compiled with `MemorySaver`, and asserts no checkpoint/write with `checkpoint_ns != ''` for the thread (fails before the change)
- [ ] Quick gate passes; test count 38 → 39
**Tests**: unit · **Gate**: quick · **Commit**: `fix(audit): never checkpoint investigator sub-agents`

### T2: Retention service — delete_audit + AuditStore.delete
**What**: `retention.delete_audit` (+ errors) and `AuditStore.delete`.
**Where**: `src/auditor/api/retention.py` (new), `src/auditor/api/store.py`, `tests/test_retention.py`
**Depends on**: T1 · **Requirement**: RET-01..08 (service layer)
**Done when**:
- [ ] Tests with tmp `AuditStore`, tmp `SqliteSaver` and tmp report files cover RET-01, 02, 03, 04, 05, 06, 07, 08
- [ ] Quick gate passes
**Tests**: unit · **Gate**: quick · **Commit**: `feat(api): add audit deletion service`

### T3: DELETE /audits/{id} route
**What**: Route mapping service errors to 204/404/409/500; `deps.get_checkpointer()` shared with `get_graph()`.
**Where**: `src/auditor/api/routes.py`, `src/auditor/api/deps.py`, `tests/test_api.py`
**Depends on**: T2 · **Requirement**: RET-01..04, RET-07 (route layer)
**Done when**:
- [ ] TestClient tests (deps monkeypatched to tmp store/saver) assert 204 + subsequent 404, 404, 409, 500
- [ ] Quick gate passes
**Tests**: integration · **Gate**: quick · **Commit**: `feat(api): add DELETE /audits/{id}`

### T4: compact_checkpoints
**What**: Delete subgraph rows + VACUUM, return `CompactStats`.
**Where**: `src/auditor/api/retention.py`, `tests/test_retention.py`
**Depends on**: T3 · **Requirement**: CMP-01..03
**Done when**:
- [ ] Test builds real subgraph checkpoints (parent graph with an inheriting sub-graph) in a tmp `SqliteSaver`, compacts, asserts CMP-01 counts, CMP-02 stats, CMP-03 equal `get_state().values`
- [ ] Quick gate passes
**Tests**: unit · **Gate**: quick · **Commit**: `feat(api): add checkpoint database compaction`

### T5: `auditor db compact` CLI
**What**: Typer `db` sub-app with `compact` (optional `--db PATH`, default `CHECKPOINT_DB`).
**Where**: `src/auditor/cli.py`, `tests/test_cli.py` (new)
**Depends on**: T4 · **Requirement**: CMP-04
**Done when**:
- [ ] CliRunner tests: success (exit 0 + counts printed), missing DB (exit 0, "nada a compactar"), locked DB (exit 1, message mentions stopping the API)
- [ ] Build gate passes (end of phase 1)
**Tests**: integration · **Gate**: build · **Commit**: `feat(cli): add db compact command`

### T6: History delete control
**What**: `onDelete` prop, inline two-step confirmation, delete never triggers open; `deleteAudit` client.
**Where**: `frontend/src/components/History.tsx`, `frontend/src/api/client.ts`, `frontend/src/components/History.test.tsx` (new)
**Depends on**: T5 · **Requirement**: UI-01, UI-02
**Done when**:
- [ ] Vitest: delete shows confirm without calling `onOpen`/`onDelete`; confirm calls `onDelete` with the audit; cancel restores
- [ ] Full gate passes
**Tests**: unit · **Gate**: full · **Commit**: `feat(frontend): add delete action to audit history`

### T7: Wire deletion in App
**What**: `handleDeleteAudit`: call `deleteAudit`, refresh history; on error show message in `startError`.
**Where**: `frontend/src/App.tsx`
**Depends on**: T6 · **Requirement**: UI-03
**Done when**:
- [ ] Full gate passes (tsc + vitest)
**Tests**: none (App layer: build gate only per matrix) · **Gate**: full · **Commit**: `feat(frontend): wire audit deletion`

### T8: Documentation
**What**: Document DELETE endpoint, `auditor db compact`, retention model; mark G28/G29 resolved.
**Where**: `DOCUMENTACAO.md`, `README.md`, `docs/USAGE.md`, `docs/ARCHITECTURE.md`, `SECURITY.md`, `docs/ROADMAP.md`
**Depends on**: T7 · **Requirement**: — (docs)
**Done when**:
- [ ] Build gate passes
**Tests**: none · **Gate**: build · **Commit**: `docs: document audit deletion and db compaction (G28/G29)`

---

## Validation

**Granularity**

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1 | 1 call change | ✅ |
| T2 | 1 function + 1 method (cohesive) | ⚠️ OK cohesive |
| T3 | 1 endpoint (+ singleton it needs) | ✅ |
| T4 | 1 function | ✅ |
| T5 | 1 command | ✅ |
| T6 | 1 component (+ its client call) | ⚠️ OK cohesive |
| T7 | 1 handler | ✅ |
| T8 | docs | ✅ |

**Diagram-definition cross-check**: T1 (None) · T2←T1 · T3←T2 · T4←T3 · T5←T4 · T6←T5 · T7←T6 · T8←T7 — all ✅ match the diagrams; no backward-phase dependency.

**Test co-location**

| Task | Layer | Matrix requires | Task says | Status |
| ---- | ----- | --------------- | --------- | ------ |
| T1 | node | unit | unit | ✅ |
| T2 | service | unit | unit | ✅ |
| T3 | route | integration | integration | ✅ |
| T4 | service | unit | unit | ✅ |
| T5 | CLI | integration | integration | ✅ |
| T6 | component (+client) | unit | unit | ✅ |
| T7 | App wiring | none | none | ✅ |
| T8 | docs | none | none | ✅ |
