# Search & Judge Performance Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement with the `tlc-spec-driven` skill (Execute flow + Critical Rules). If it cannot be activated, STOP and tell the user.

**Spec**: `.specs/features/search-and-judge-perf/spec.md` · **Status**: Done

## Design (inline)
- `tools/filesystem.py`: `_glob_segments(glob) -> list[str]` (split on `/`, drop `.`/empty); `_matches(parts, segs)` recursive (`**` = 0..n parts); `_max_depth(segs)` (None if `**`); `search_code` walks `os.walk(root, followlinks=False)` with `dirnames[:] = sorted(d for d in dirnames if d not in ignore_dirs and depth ok)`, `filenames` sorted; keeps the existing guards (absolute/`..` rejection, `_safe_resolve` per file, binary/size filters, result cap).
- `nodes/adversarial.py`: extract `_judge_finding(finding, root, settings, llm, votes) -> (verdicts, rationale)`; pool over eligible findings (`submit` in input order, `results[idx]`); aggregation loop unchanged over input order.

## Tests
| Layer | Test | Location |
| ----- | ---- | -------- |
| search tool | unit (fixture tree, `os.scandir` spy) | `tests/test_tools_scoping.py` (append) |
| adversarial node | unit (fake judge with sleep + concurrency counter, as `test_audit.test_runs_concurrently`) | `tests/test_adversarial.py` (append) |

## Gate
Quick `.venv/bin/pytest -q` · Build `make ci`

## Tasks
- **T1** pruned search (SRCH-01..07) · `fix(tools): prune ignored dirs and match globs per segment in search_code (G34)`
- **T2** parallel judge (ADV-01..03) · `perf(adversarial): judge findings concurrently (G35)`
- **T3** docs + benchmark numbers (DOCUMENTACAO G34/G35 ✅, ARCHITECTURE tool safety, USAGE env var note) · `docs: search pruning and parallel judge (G34/G35)`

## Execution notes
- Benchmark (50 src + 20 000 files in `node_modules`, best of 3): `**/*` 2 403 ms → 6.8 ms; `**/*.py` 26 → 6.8 ms; `src/*.py` 6 → 6.9 ms.
- SRCH-07 forced collecting names then sorting (os.walk yields root files before subdirs); listing names is cheap — the old cost was `is_file`/`_safe_resolve` on ignored files.
- Test fixture change (no assertion): `_Settings.max_concurrent_investigators = 4` in `tests/test_adversarial.py`.
- Own test fix before implementation: the SRCH-04 spy first recorded `realpath`, which made one assertion tautological; it now records literal paths.

## Fix loop 1 (after Verifier FAIL minor)

| Gap | Fix | Test |
| --- | --- | ---- |
| 1 ADV-03 untested with votes>1 (mutants q, r) | votes=2, lens 0 raises, lens 1 still asked | `test_adv03_failed_lens_does_not_stop_the_other_lenses` (expected `uncertain`: existing aggregation needs a majority of the *requested* votes — my first draft expected `confirmed`, corrected) |
| 2 Relative ignore check not dead (mutant m) | decided: only directories are ignored; files named `build`/`env`/… are searched (SRCH-08, behavior change) | `test_srch08_files_named_like_ignored_dirs_are_searched` |
| 3 Main-thread console/SSE untested (mutant o) | ADV-04 | `test_adv04_console_and_sse_only_from_main_thread` |
| 4 ADV-01 timing-sensitive | `threading.Barrier(4)`; first version also asserted `peak == 4`, which was flaky (12/15 fails: counter increments after the barrier) — replaced by verdict assertions; 20/20 stable | `test_adv01_judges_concurrently_up_to_the_limit` |
