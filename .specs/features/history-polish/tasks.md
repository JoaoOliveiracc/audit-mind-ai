# Report Names & History Polish Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement with the `tlc-spec-driven` skill (Execute flow + Critical Rules). If it cannot be activated, STOP and tell the user.

**Spec**: `.specs/features/history-polish/spec.md` · **Status**: Done

## Design (inline)
- `report/renderer.write_reports(state, output_dir, run_id=None)`: `_id8(run_id)` (alnum filter → `[:8]`, else `secrets.token_hex(4)`); base `auditoria-{stamp}-{id8}`; pick first `base`, `base-2`, … where none of the 3 files exist; write each with `open(path, "x")`.
- `nodes/report.report_node(state, config)`: `thread_id = config["configurable"]["thread_id"]` (LangGraph injects `config` by parameter name).
- Frontend: `App.handleOpenAudit` branches on `interrupted` / `error` before touching `auditId`/stream; `resumingId` state passed to `History` as `busyId`; `History` disables + relabels; handler returns early while busy.

## Test Coverage Matrix
| Layer | Test | Location | Run |
| ----- | ---- | -------- | --- |
| renderer / report node | unit | `tests/test_report_names.py` (new) | `.venv/bin/pytest -q` |
| App / History | unit (Vitest, client/SSE mocked) | `frontend/src/App.test.tsx`, `History.test.tsx` | `./node_modules/.bin/vitest run` |

## Gate
Quick: `.venv/bin/pytest -q` · Full: vitest + tsc · Build: `make ci`

## Tasks
- **T1** unique names + exclusive write (REP-01..04) · `report/renderer.py`, `tests/test_report_names.py` · quick · `fix(report): unique, non-overwriting report file names (G45)`
- **T2** `report_node` passes `thread_id` (REP-05) · `nodes/report.py`, same test file · quick · (same commit as T1 is acceptable; atomic: `fix(report): name reports after the audit id`)
- **T3** history: interrupted/error messages + in-flight Retomar (HIS-01..03) · `App.tsx`, `History.tsx`, tests · full · `fix(frontend): clear messages for interrupted/error audits; block double resume (G46)`
- **T4** docs (README/USAGE/DOCUMENTACAO: name format; G45/G46 ✅) · build (`make ci`) · `docs: report naming and history behavior (G45/G46)`

## Fix loop 1 (after Verifier FAIL)

| Gap | Fix | Test |
| --- | --- | ---- |
| 1 Button stuck after failed resume (mutant l) | test recovery: enabled + `Retomar` + second click resumes | `App.test.tsx` — "após falha…" |
| 2 Re-entry guard unexercised (k2) | kept: it blocks resuming ANOTHER audit while one is in flight (that button isn't disabled) — now tested | `App.test.tsx` — "OUTRA auditoria…" |
| 3 Exclusive create untested alone (d2) | `_free_base` forced wrong → `FileExistsError`, original intact | `test_exclusive_create_never_overwrites_even_if_free_base_is_wrong` |
| 4 Cosmetic | README wording (id is the API `id`, not shown in history); stale comment in `App.tsx` | — |
