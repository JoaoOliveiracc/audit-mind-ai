# Deduplication & Test Isolation Specification (G41 + home-dir test leak)

## Problem Statement

(G41) The same logic is copied in several places: `_emit` + the `get_stream_writer` fallback in 3
nodes; node labels in `cli.py` and `api/runner.py` (with drifting texts); severity counting in 4
places with two semantics (with zeros: report/synthesis/CLI; without zeros: API `counts`). A fix in
one copy silently misses the others. (Test leak) `api/store.py` creates `~/.config/auditor` **at
import**, and `test_get_missing_audit_404` opens the real `audits.sqlite` — running the tests
touches the developer's real data directory.

## Goals
- [ ] One implementation per concern; behavior unchanged (existing tests untouched and green).
- [ ] The test suite never touches the real `~/.config/auditor`.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Other refactors (e.g. splitting `audit.py`) | Not requested. |
| Changing the API `counts` shape | Keeps the existing contract (`_counts` test unchanged). |

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Shared modules | `auditor/events.py` (`emit`, `NODE_LABELS`), `auditor/scoring.py` (`severity_counts`, `compute_health_score`) | Small, dependency-free homes; nodes/api/cli/report import from them. | pending approval |
| Label texts | one canonical text per node (runner's texts); the CLI keeps its emoji as a separate icon map keyed by the same nodes | Single source of truth; CLI output text changes slightly (e.g. "Planejando dimensões"). | pending approval |
| Counting semantics | `severity_counts(findings, include_zero=True)`; API uses `include_zero=False` | Preserves both existing contracts. | y (agent) |
| Backward compat | `synthesis.compute_health_score/severity_counts` and `runner._counts` remain importable (re-export / thin wrapper) | Existing tests import them; no test edits. | y (agent) |
| Data directory | new `AUDITOR_DATA_DIR` (default `~/.config/auditor`), resolved **at use** (not import); created only when a store/checkpointer is opened | Lets tests (and users) isolate data; removes the import side effect. | pending approval |
| Test isolation | `tests/conftest.py` autouse fixture: `AUDITOR_DATA_DIR=<tmp>` + clear the API singletons' caches | Every test, current and future, is isolated by default. | y (agent) |

**Open questions:** none.

## User Stories

### P1: One implementation per concern ⭐ MVP
1. **DUP-01** `emit` and the `get_stream_writer` fallback SHALL exist only in `auditor/events.py`; `audit`, `verify` and `adversarial` SHALL use it. Outside a LangGraph run it SHALL be a silent no-op; inside a run with `stream_mode="custom"` the payload SHALL reach the stream.
2. **DUP-02** `NODE_LABELS` SHALL exist only in `auditor/events.py` and SHALL have a label for **every node of the compiled graph**; the API phase events and the CLI SHALL use it.
3. **DUP-03** Severity counting SHALL exist only in `auditor/scoring.py`: `include_zero=True` returns all 5 severities (zeros included); `include_zero=False` returns only present ones. Report, synthesis, CLI and API SHALL use it. A missing, `None` or empty (`""`) severity SHALL count as `info` (fix loop 1: `""` made explicit).
4. **DUP-04** Behavior SHALL be unchanged: the full existing suite passes with no test modified.

### P1: Tests never touch the real data dir ⭐ MVP
1. **ISO-01** Importing `auditor.api.store` (or the API app) SHALL NOT create any directory.
2. **ISO-02** WHEN `AUDITOR_DATA_DIR` is set THEN the metadata DB, the checkpoint DB and `auditor db compact`'s default SHALL be under it; otherwise under `~/.config/auditor`.
3. **ISO-03** WHEN the full test suite runs with a fresh `HOME` THEN `$HOME/.config/auditor` SHALL NOT exist afterwards. (fix loop 1: automated — `tests/conftest.py` points `HOME` to a temp dir at import, before `auditor` modules load, and fails the session if `$HOME/.config/auditor` appears; this also keeps the developer's real `~/.config/auditor/.env` out of the tests.)

## Requirement Traceability

| ID | Task | Status |
| -- | ---- | ------ |
| DUP-01..02 | T1 | Verified |
| DUP-03 | T2 | Verified |
| ISO-01..03 | T3 | Verified |
| DUP-04 | all | Verified |
| — docs | T4 | Verified |
