# Search & Judge Performance Specification (G34 + G35)

## Problem Statement

(G34, measured) `search_code` enumerates the whole tree with `root.glob(...)` and only then drops
files under ignored dirs: with 50 source files + 20 000 files in `node_modules`, the investigators'
default `glob="**/*"` takes **2.4 s per call** (the cost is `is_file` + `_safe_resolve` on every
ignored file). Investigators call it many times per dimension. (G35) The adversarial judge evaluates
findings one at a time (`findings × votes` LLM calls in series), while investigators already run in
parallel.

## Goals
- [ ] Ignored directories are never traversed; default-glob searches on the benchmark tree drop from ~2.4 s to < 0.1 s.
- [ ] Judge calls run concurrently (same limit as investigators) with identical results/ordering.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Following symlinked directories | User decision: not followed. |
| A separate judge concurrency setting | User decision: reuse `AUDITOR_MAX_CONCURRENT_INVESTIGATORS`. |
| Caching file reads across tools/dimensions | Separate optimization (ROADMAP v0.2). |

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Traversal | `os.walk(followlinks=False)`, pruning `ignore_dirs` in place; symlinked dirs not descended | User decision; also prevents loops. | y |
| Glob semantics | own per-segment matcher: `fnmatchcase` per segment, `**` = zero or more directories, a trailing `**` matches any file below | Same as pathlib for the patterns agents use, except `src/**` now yields files (pathlib 3.12 yields only dirs → 0 results today). | y (agent) |
| Depth pruning | patterns without `**` stop descending past their depth | Large win for `src/*.py`-style patterns. | y (agent) |
| Result order | sorted by relative path | Deterministic output for the LLM and tests (pathlib order was arbitrary). | y (agent) |
| Empty / `.` glob | `ERRO:` message (today they raise `ValueError`/`IndexError`) | Tool error convention. | y (agent) |
| Judge concurrency | `ThreadPoolExecutor(max_workers=min(limit, eligible))`; votes of one finding stay sequential inside its worker; aggregation in input order; SSE/console from the main thread | Mirrors `audit_node`. | y |

**Open questions:** none.

## User Stories

### P1: Pruned code search ⭐ MVP
1. **SRCH-01** WHEN `search_code` runs THEN no directory inside an `ignore_dirs` directory (relative to the root) SHALL be listed (no `os.scandir` call on it).
2. **SRCH-02** WHEN given these globs on a fixture tree THEN it SHALL return exactly the matching files: `**/*` (all non-ignored), `*.py` (top level only), `src/*.py`, `**/*.py` (incl. top level), `src/**/*.py` (direct + nested), `**/test_*.py`, `src/**` (every file under `src`).
3. **SRCH-03** WHEN the glob has no `**` THEN directories deeper than the pattern SHALL NOT be listed.
4. **SRCH-04** WHEN a directory inside the root is a symlink THEN it SHALL NOT be descended into.
5. **SRCH-05** All existing scoping guarantees (G25/G26/G30 tests) SHALL keep holding.
6. **SRCH-06** WHEN `glob` is empty or `.` THEN the tool SHALL return a string starting with `ERRO:` (no exception).
7. **SRCH-07** Results SHALL be ordered by relative path.
8. **SRCH-08** (fix loop 1) WHEN a *file* is named like an ignored dir (`build`, `env`, `bin`, `out`…) THEN it SHALL still be searched (only directories are ignored). *Behavior change: previously such files were skipped — wrong for an auditor (e.g. a `build` script).*

### P1: Parallel adversarial judge ⭐ MVP
1. **ADV-01** WHEN several findings are eligible THEN up to `AUDITOR_MAX_CONCURRENT_INVESTIGATORS` of them SHALL be judged concurrently (1 → sequential).
2. **ADV-02** The kept findings SHALL be in the same order as the input, and `stats` (judged/confirmed/refuted/uncertain/refuted_titles) SHALL equal the sequential result.
3. **ADV-03** WHEN a judge call raises THEN only that verdict SHALL be missing (existing isolation): with `votes > 1` the other lenses of the same finding SHALL still be asked (each with its own lens text), and other findings SHALL be unaffected.
4. **ADV-04** (fix loop 1) Console warnings and the SSE `adversarial` event SHALL be produced from the calling (main) thread, never from pool workers (the LangGraph stream writer is not available in workers).

## Requirement Traceability

| ID | Task | Status |
| -- | ---- | ------ |
| SRCH-01..08 | T1 (+ fix loop 1) | Verified |
| ADV-01..04 | T2 (+ fix loop 1) | Verified |
| — docs + benchmark | T3 | Verified |

**Coverage:** 12 total, 12 mapped.

## Success Criteria
- [ ] Benchmark tree (50 src + 20 000 ignored files), `glob="**/*"`: ~2.4 s → < 0.1 s (recorded in validation).
