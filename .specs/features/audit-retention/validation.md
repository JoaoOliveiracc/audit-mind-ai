# Audit Retention Validation

**Date**: 2026-11-10
**Spec**: `.specs/features/audit-retention/spec.md`
**Diff range**: uncommitted working tree on `develop` (HEAD `78dc680`); scoped to the files below
**Verifier**: independent sub-agent (author ≠ verifier)

**Verdict**: ✅ PASS (with advisories — no blocking gap; see "Gaps / advisories")

---

## Diff Surface (in scope)

| File | Change |
| ---- | ------ |
| `src/auditor/nodes/audit.py:77` | `create_react_agent(..., checkpointer=False)` |
| `src/auditor/api/retention.py` (new) | `delete_audit`, `AuditNotFoundError`, `AuditBusyError`, `CompactStats`, `compact_checkpoints` |
| `src/auditor/api/store.py` | `AuditStore.delete` |
| `src/auditor/api/deps.py` | `get_checkpointer()` singleton, reused by `get_graph()` |
| `src/auditor/api/routes.py:128-139` | `DELETE /audits/{audit_id}` → 204/404/409/500 |
| `src/auditor/cli.py` | `db` sub-app, `auditor db compact [--db PATH]` |
| `frontend/src/components/History.tsx` | `onDelete` prop, inline two-step confirm, sibling buttons |
| `frontend/src/api/client.ts` | `deleteAudit(id)` |
| `frontend/src/App.tsx` | `handleDeleteAudit` → `startError` + `refreshHistory()` |
| Tests | `tests/test_audit.py` (+1), `tests/test_retention.py` (new, 11), `tests/test_api.py` (+4), `tests/test_cli.py` (new, 3), `frontend/src/components/History.test.tsx` (new, 4) |

Excluded per instructions: `src/auditor/tools/*`, `tests/test_tools_scoping.py`, doc-only files.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 | ✅ Done | SUB-01 test present, mutant (a) killed |
| T2 | ✅ Done | RET-01..08 service tests present |
| T3 | ✅ Done | 204/404/409/500 route tests present |
| T4 | ✅ Done | CMP-01..03 in one test |
| T5 | ✅ Done | 3 CliRunner tests (success / missing / locked) |
| T6 | ✅ Done | 4 Vitest tests |
| T7 | ✅ Done | build gate only (per approved matrix) |
| T8 | n/a | docs — not verified here (out of scope of this check) |

---

## Spec-Anchored Acceptance Criteria

| ID | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| SUB-01 | No checkpoint/write with non-empty `checkpoint_ns` for the thread when the investigator runs in a checkpointed parent node | `tests/test_audit.py:152` — `assert namespaces == {""}`; `:153` — `assert write_namespaces <= {""}`; `:149` — `assert out["summary"] == "ok"` (investigator actually ran, with a tool call) | ✅ PASS |
| RET-01 | 204; GET → 404; absent from list; no checkpoints/writes; `.md/.html/.sarif` gone | Route: `tests/test_api.py:144` `r.status_code == 204`, `:145` GET `== 404`, `:146` `"d1" not in [...]`, `:147` `not report.exists()`. Service (completed + error): `tests/test_retention.py:78` `store.get("a1") is None`, `:79` list == `["keep"]`, `:80-81` checkpoints/writes count `== 0`, `:82` `not any(f.exists() ...)`, `:84-85` other audit intact | ✅ PASS (checkpoint removal asserted at service layer only) |
| RET-02 | 404 | `tests/test_api.py:151` — `client.delete("/audits/nao-existe").status_code == 404`; `tests/test_retention.py:91` — `pytest.raises(AuditNotFoundError)` | ✅ PASS |
| RET-03 | 409; metadata, checkpoints, files kept | `tests/test_api.py:162` `== 409`, `:163` `store.get("d1") is not None and report.exists()`; `tests/test_retention.py:101` `raises(AuditBusyError)`, `:104` status `== "running"`, `:105` checkpoints `> 0`, `:106` `all(f.exists())`, `:107` `"live" in registry` | ✅ PASS |
| RET-04 | Orphan `running`/`waiting_input` deleted as RET-01 | `tests/test_retention.py:111-120` (parametrized) — `store.get("orf") is None`, checkpoints `== 0`, files gone | ✅ PASS (service layer; route 204 path shared with RET-01) |
| RET-05 | Finished runner removed from registry (`/stream` → 404) | `tests/test_retention.py:131` `"fin" not in registry`, `:132` `"other" in registry` | ✅ PASS (stream 404 inferred from `routes.py:145-147` `registry.get` → 404; not asserted over HTTP) |
| RET-06 | Missing report file → still succeeds | `tests/test_retention.py:139-144` — first file pre-unlinked; `store.get("gone") is None` | ✅ PASS (service; no HTTP-level 204 assertion) |
| RET-07 | Non-ENOENT `OSError` → 500, metadata **and** checkpoints kept | `tests/test_api.py:174` `== 500`, `:175` `store.get("d1") is not None`; `tests/test_retention.py:156` `raises(OSError)`, `:159` metadata kept, `:160` checkpoints `> 0` | ✅ PASS |
| RET-08 | Suffix ∉ {.md,.html,.sarif} not deleted; audit still deleted | `tests/test_retention.py:170` `store.get("suf") is None`, `:171` `files[0].exists()` (.txt), `:172` others gone | ✅ PASS |
| CMP-01 | All `ns != ''` rows deleted; all `ns == ''` kept | `tests/test_retention.py:223` sub counts `== 0`; `:224-225` root counts equal before | ✅ PASS |
| CMP-02 | Returns removed checkpoints, removed writes, size before/after (after ≤ before) | `tests/test_retention.py:227-229` — exact counts; `0 < size_after <= size_before` | ✅ PASS (matches spec wording; see mutant k5) |
| CMP-03 | `get_state(thread).values` unchanged | `tests/test_retention.py:233-235` — values equal before, `{"n": 11}` | ✅ PASS |
| CMP-04 | success: counts+sizes, exit 0; no DB: "nothing to compact", exit 0; locked: "stop the API", exit 1 | `tests/test_cli.py:46-48` exit 0, `"Checkpoints de sub-agentes removidos: {expected}"`, `"Tamanho:"`; `:54-55` exit 0, `"Nada a compactar"`; `:69-70` exit 1, `"pare a API"` | ✅ PASS (writes count line not asserted) |
| UI-01 | Each row has delete control that does not open the audit | `History.test.tsx:28` `onOpen not called`; `:57-63` row click still opens | ✅ PASS |
| UI-02 | Inline confirm; only second click calls delete with the id | `History.test.tsx:29-30` first click: no `onDelete`, confirm visible; `:39-40` `toHaveBeenCalledTimes(1)`, `toHaveBeenCalledWith(audit)`; `:44-55` cancel restores | ✅ PASS |
| UI-03 | Success → history refreshed; failure → API message displayed | **no test** — `App.tsx` `handleDeleteAudit` (build gate only per approved matrix) | ⚠️ Accepted residual (see Gap 3) |

**Status**: 16/17 ACs evidenced by an assertion targeting the spec outcome; UI-03 is build-gate-only by the approved matrix.

### Design error table vs implementation

| Scenario | Design | `routes.py` | Asserted? |
| -------- | ------ | ----------- | --------- |
| Unknown id | 404 `Auditoria não encontrada.` | `:134` identical | status only |
| Live audit | 409 `Auditoria em execução; aguarde a conclusão para excluir.` | `:136` identical | status only |
| Unlink fails | 500 with detail | `:138` `Falha ao apagar arquivos da auditoria: {exc}` | status only |
| DB locked (CLI) | exit 1, "pare a API (auditor serve) e tente novamente" | `cli.py` identical | `"pare a API"` |

Messages match the design; tests do not assert `detail` strings (minor).

---

## Discrimination Sensor

Scratch copy: `…/scratchpad/verifier2/` (src, tests, pyproject.toml, frontend w/o node_modules + symlink). Confirmed pytest imports the copy's `src/auditor/__init__.py`. Real tree untouched (`git status` unchanged).

| # | File | Mutation | Killed? | Killed by |
| - | ---- | -------- | ------- | --------- |
| a | `nodes/audit.py:77` | drop `checkpointer=False` | ✅ | `test_investigator_never_writes_subgraph_checkpoints` |
| b | `retention.py:47-49` | skip live-runner check | ✅ | `test_delete_live_audit_returns_409` (+ service test) |
| c | `retention.py` | `store.delete` before files | ✅ | `test_delete_io_failure_returns_500_and_keeps_audit` / RET-07 service |
| c2 | `retention.py` | `delete_thread` before files | ✅ | `test_unlink_failure_keeps_metadata_and_checkpoints` (RET-07 checkpoint clause) |
| d | `retention.py` | suffix guard removed | ✅ | `test_only_report_suffixes_are_deleted` |
| e | `retention.py:59` | `unlink()` without `missing_ok` | ✅ | `test_missing_report_file_is_tolerated` |
| f | `retention.py:63` | `registry.pop` removed | ✅ | `test_finished_runner_is_removed_from_registry` |
| g | `retention.py:92` | checkpoints DELETE without ns filter | ✅ | `test_db_compact_success…` / CMP-01 |
| g2 | `retention.py:93` | writes DELETE without ns filter | ✅ | `test_compact_removes_only_subgraph_rows_and_preserves_state` |
| h | `cli.py` | `return` (exit 0) on locked DB | ✅ | `test_db_compact_locked_db_exits_1_and_asks_to_stop_api` |
| i | `History.tsx` | delete button calls `onDelete` on first click | ✅ | 3 Vitest tests |
| j | `History.tsx` | delete click also calls `onOpen` | ✅ | UI-01 / UI-02 tests |
| j3 | `History.tsx` | `onClick={onOpen}` on the `<li>` (real event propagation) | ✅ | UI-01 / UI-02 tests |
| j2 | `History.tsx` | confirm passes wrong audit | ✅ | `toHaveBeenCalledWith(audit)` |
| k1 | `routes.py:136` | 409 → 400 | ✅ | route 409 test |
| k2 | `routes.py` | OSError → 204 | ✅ | route 500 test |
| k3 | `retention.py:61` | `delete_thread` removed | ✅ | RET-01 service test |
| k4 | `cli.py` | missing-DB guard removed | ✅ | missing-DB CLI test |
| k5 | `retention.py:95` | `VACUUM` removed | ❌ Survived | `after ≤ before` still holds |

**Sensor depth**: P0-style (data-integrity path) — 19 mutants.
**Result**: 18/19 killed; all 10 requested mutants (a–j) killed. k5 survives because CMP-02 only requires `after ≤ before`; spec-faithful, flagged as spec-precision advisory.

---

## Gate Check

- **Backend**: `.venv/bin/pytest -q` → **57 passed**, 0 failed, 0 skipped (2 deprecation warnings: `create_react_agent` moved to `langchain.agents`)
- **Lint**: `.venv/bin/ruff check src tests` → All checks passed
- **Frontend**: `vitest run` → **16 passed** (3 files); `tsc --noEmit -p .` → exit 0
- **Test count before feature**: 38 backend (tasks.md T1 baseline) → **after**: 57 (+19: 1 audit, 11 retention, 4 api, 3 cli); frontend +4.
- **~/.config/auditor**: file mtimes unchanged across a full pytest run (the only recent writes come from a running `auditor serve --reload`). Importing `auditor.api.store` still `mkdir(exist_ok=True)`s the dir — pre-existing side effect, noted in design as out of scope.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / surgical changes | ✅ |
| No scope creep | ✅ |
| Matches patterns (lock pattern in store, Portuguese `detail`, Typer sub-app) | ✅ |
| Spec-anchored outcome check | ✅ (UI-03 accepted residual; messages not asserted) |
| Per-layer coverage (service 1:1; route 204/404/409/500; CLI 3 exits) | ✅ |
| Every test maps to an AC | ✅ |
| Documented guidelines | none — strong defaults applied |

---

## Edge Cases / Safety Review

- [x] RET-06 missing file tolerated
- [x] RET-07 failure order leaves metadata + checkpoints (both order mutants killed)
- [x] RET-08 suffix guard
- [x] `audit_id` is only used as SQL parameter / dict key — no path is built from it; no traversal via the route.
- [x] Symlinked report path: `unlink` removes the link, not the target.
- [ ] Deletable files are any recorded path with an allowed suffix **anywhere on disk** (not confined to the output dir). Accepted by the spec's defense-in-depth decision; a tampered meta DB could still remove arbitrary `.md` files.
- [ ] Report filenames use a 1-second timestamp (`report/renderer.py:177-182`, pre-existing). Two audits finishing in the same second share paths; deleting one removes the other's reports.

---

## Gaps / advisories (ranked)

1. ✅ **RESOLVED (fix loop 1)** — ~~**TOCTOU: record read before liveness check**~~ — `retention.py:43` reads the record, then `:47-49` checks `runner.done`. If the runner finishes in between (it writes reports, `store.update(... report_*)`, then `done.set()`), the delete proceeds with the stale record (no report paths) → `.md/.html/.sarif` files containing code excerpts are orphaned, violating the goal "leaves no report behind". Fix: check the registry first, then `store.get`, (or re-read the record after the check). Low probability (needs DELETE in the last ms of a run), Minor/Major for privacy.
2. **Create/delete window** — `routes.create_audit` does `store.create` before `registry[audit_id] = runner`; a DELETE in that window treats the new audit as an orphan and deletes the row while the runner then starts writing checkpoints (row-less). Practically unreachable (id is returned only after registration), Minor.
3. **UI-03 untested** — accepted per the approved matrix (App layer build-gate only). The handler is 8 lines over the already-used `jsonOrThrow`; residual risk is low but neither "refresh on success" nor "show API detail on 409" is verified automatically. Recommend a manual UAT step (delete a running audit → 409 message shown) or a future `App`/`client` test. Not blocking.
4. ✅ **RESOLVED (fix loop 1)** — ~~**k5 survives (VACUUM)**~~ — CMP-02 asserts only `after ≤ before`; removing VACUUM goes undetected. Spec-precision advisory: if freeing disk is a requirement (Success Criteria "frees ≈ 850 MB"), assert `size_after < size_before` on a DB with enough subgraph data. Minor.
5. **Error `detail` strings not asserted** in route tests (404/409/500); messages match the design today. Minor.
6. **HTTP-level gaps**: RET-05 (`/stream` → 404 after delete), RET-06 (204 with missing file), RET-04 orphan via route, and checkpoint removal via route are asserted only at the service layer. Acceptable given the thin route; Cosmetic.
7. Same-second report filename collision (pre-existing, amplified by delete). Out of scope; Minor.

**Thread-safety notes**: `AuditStore` ops are lock-guarded; `SqliteSaver.delete_thread` uses the saver's internal lock and the shared singleton connection (`check_same_thread=False`); concurrent duplicate DELETEs are idempotent (second is 204 or 404). The only real race is Gap 1.

---

## Requirement Traceability Update

| Requirement | Previous | New |
| ----------- | -------- | --- |
| SUB-01 | Implementing | ✅ Verified |
| RET-01..08 | Implementing | ✅ Verified (Gap 1 resolved in fix loop 1) |
| CMP-01..04 | Implementing | ✅ Verified (advisory: Gap 4) |
| UI-01..02 | Implementing | ✅ Verified |
| UI-03 | Implementing | ⚠️ Build-gate only (accepted by matrix) |

---

## Summary

**Overall**: ✅ Ready (Gap 1 and k5 resolved in fix loop 1 — see Re-verification)
**Spec-anchored check**: 16/17 ACs asserted on spec outcome; UI-03 build-gate-only by design
**Sensor**: 18/19 killed initially; after fix loop 1, 19/19 + race mutant killed
**Gate**: backend 57 passed, ruff clean, vitest 16 passed, tsc 0

## Re-verification (fix loop 1)

**Gate (real repo)**: `pytest -q` → 58 passed, 0 failed; `ruff check src tests` → All checks passed.

**Discrimination** (scratch copy, copy's `src` confirmed imported):

| Mutant | Change | Target test | Result |
|---|---|---|---|
| A | restore old order (`store.get` + not-found before runner check) | `test_delete_sees_reports_written_by_a_runner_finishing_concurrently` | ✅ Killed (only this test failed) |
| B | remove `conn.execute("VACUUM")` | `test_compact_removes_only_subgraph_rows_and_preserves_state` | ✅ Killed (only this test failed) |

**Race test quality**: the runner's `done` check triggers the finish (report file written + `report_html` recorded) between liveness check and record read; asserts the RET-01 outcome (`store.get` is None and the report file no longer exists). Not shallow.

**Verdict**: ✅ PASS — Gap 1 and k5 resolved; no new failures.
