# Deduplication & Test Isolation Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement with the `tlc-spec-driven` skill (Execute flow + Critical Rules). If it cannot be activated, STOP and tell the user.

**Spec**: `.specs/features/dedup-and-test-isolation/spec.md` · **Status**: Done

## Tests
New `tests/test_shared.py` (DUP-01..03 + a guard that no node module defines its own `_emit`), `tests/test_data_dir.py` (ISO-01..02, subprocess with tmp `HOME` for ISO-01), `tests/conftest.py` (autouse isolation). ISO-03 verified by running the whole suite with `HOME=<tmp>` (recorded in validation). Existing tests: untouched.

## Gate
Quick `.venv/bin/pytest -q` · Build `make ci`

## Tasks
- **T1** `auditor/events.py` (`emit`, `NODE_LABELS`, CLI icons) + use in nodes/runner/cli (DUP-01, DUP-02) · `refactor: single emit and node labels (G41)`
- **T2** `auditor/scoring.py` + use in synthesis/runner/cli/renderer (DUP-03) · `refactor: single severity counting (G41)`
- **T3** lazy data dir + `AUDITOR_DATA_DIR` + conftest isolation (ISO-01..03) · `fix(tests): never touch the real ~/.config/auditor; add AUDITOR_DATA_DIR`
- **T4** docs (`.env.example`, USAGE, DOCUMENTACAO G41 ✅, SECURITY data-at-rest note) · `docs: AUDITOR_DATA_DIR and shared helpers (G41)`

## Execution notes
- DUP-04 kept literally: no existing test file modified (`git diff -- tests/` only shows new files). Nodes import `emit as _emit` so the existing monkeypatch points (`audit._emit`, `adv._emit`) keep working without a second implementation.
- Own test fixes before implementation: removed a pointless `time.sleep(0)`; narrowed the "no copies" guard to module-level definitions (`AuditRunner._emit` is a different concept — appends to the SSE log).
- Minor behavior change: a finding with `severity: None` now counts as `info` (before: a `None` key).
- ISO-03: full suite with a fresh `HOME` → 174 passed, `$HOME/.config/auditor` not created; normal run leaves the real `~/.config/auditor/*.sqlite` mtimes unchanged.

## Fix loop 1 (after Verifier FAIL — test gaps only)

| Gap | Fix | Test (`tests/test_shared.py` unless noted) |
| --- | --- | ---- |
| 1 CLI not proven to use NODE_LABELS (l) | capture `cli._run` output | `test_dup02_cli_phase_lines_use_shared_labels` |
| 2 Report/CLI counts untested (m, n) | behavior tests at each call site; guard also flags `Counter(` | `test_dup03_report_context_counts_use_shared_counting`, `test_dup03_cli_summary_table_uses_shared_counting` |
| 3 None→info untested (k); `""` | both → info (spec updated) | `test_dup03_none_or_empty_severity_counts_as_info` |
| 4 ISO-03 manual only (h) | `tests/conftest.py`: `HOME` → temp dir at import + session-end failure if `$HOME/.config/auditor` appears (also keeps the real `~/.config/auditor/.env` out of tests) | session fixture `_no_leak_into_home` |
| 5 Guards brittle | regex also catches annotated `NODE_LABELS: dict = {` | `test_dup01_dup02_no_copies_left_outside_events` |
| (i) `cache_clear` removal survives | accepted: no leak (data dir still per test); consequence is singletons shared across tests — documented | — |
