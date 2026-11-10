# Search & Judge Performance Validation (G34 + G35)

**Date**: 2026-11-10
**Spec**: `.specs/features/search-and-judge-perf/spec.md`
**Diff range**: uncommitted working tree on `develop` vs `HEAD` (3995839)
**Verifier**: independent sub-agent (author ≠ verifier). Read-only on the real tree; all mutations in
`/tmp/claude-1000/-home-joao-Documentos-auditor-IA/3a865784-2fa5-4436-aa9a-ec628bd6b1d6/scratchpad/verifier14/`.

**Verdict: ❌ FAIL (minor)**. All 10 ACs have tests that check the outcome the spec defines, and the gates pass
on 3.12 and 3.10. The benchmark meets the success criterion. One mutant that does not behave the same as the real code survived on ADV-03 ("only that verdict
missing"), because the multi-vote path is never tested. Adding one test fixes it. No production defect was found.

---

## Diff surface

| File | Change |
| ---- | ------ |
| `src/auditor/tools/filesystem.py` | +`_glob_segments` (l.24), `_glob_matches` (l.29), `_iter_glob_files` (l.39, `os.walk(followlinks=False)` l.47, depth prune l.49, ignore prune l.52, sort l.55); `search_code` empty-glob guard l.128, walker swap l.135 |
| `src/auditor/nodes/adversarial.py` | +`_judge_votes` (l.101); `adversarial_node` pool (l.152–162), input-order aggregation (l.164–191), console only in main thread (l.171) |
| `tests/test_tools_scoping.py` | G34 block l.105–179 (+12 tests) |
| `tests/test_adversarial.py` | fixture `max_concurrent_investigators = 4` (l.32); G35 block l.84–179 (+5 tests) |
| `DOCUMENTACAO.md`, `docs/ARCHITECTURE.md`, `docs/USAGE.md` | G34/G35 marked resolved; walker + benchmark note; env var also limits judge |

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 pruned search | ✅ Done | — |
| T2 parallel judge | ✅ Done | multi-vote isolation untested (gap 1) |
| T3 docs + benchmark | ✅ Done | numbers re-measured below, they match |

---

## Spec-Anchored Acceptance Criteria

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| SRCH-01 ignored dirs never listed | no `os.scandir` on any path in/under `ignore_dirs` | `tests/test_tools_scoping.py:159` — `assert not any(p == join(root, ignored) or p.startswith(... + os.sep) for p in scanned)` for `node_modules`, `.venv` (spy l.147 records literal paths) | ✅ PASS (mutant a killed: removing the prune is caught even though the relative check still drops the files) |
| SRCH-02 glob semantics | exact file lists for 7 globs | `tests/test_tools_scoping.py:139` — `assert _found(tree, glob) == expected`, params l.128–136 (`**/*`, `*.py`, `src/*.py`, `**/*.py`, `src/**/*.py`, `**/test_*.py`, `src/**`) | ✅ PASS |
| SRCH-03 no `**` → no deeper listing | `src/deep` never scanned for `src/*.py` | `tests/test_tools_scoping.py:164-165` — `== ["src/a.py"]` and `join(tree,"src","deep") not in scanned` | ✅ PASS |
| SRCH-04 symlinked dir not descended | no `linkdir/` results, `linkdir` never scanned | `tests/test_tools_scoping.py:170-173` — no `linkdir/` prefix; no scanned path under link; `found.count("src/deep/c.py") == 1` | ✅ PASS |
| SRCH-05 G25/G26/G30 keep holding | earlier scoping tests stay green | `tests/test_tools_scoping.py:38-102` (SCOPE-01..08, unchanged) — all pass; mutant l (guard removed) killed by l.41/l.54 | ✅ PASS |
| SRCH-06 empty / `.` glob | string starting with `ERRO:` | `tests/test_tools_scoping.py:178` — `.startswith("ERRO:")`, params `""`, `"."` | ✅ PASS |
| SRCH-07 sorted by relative path | ordered list | `tests/test_tools_scoping.py:139` — list equality (not set) with sorted `expected` | ✅ PASS |
| ADV-01 concurrency up to limit; 1 → sequential | peak = limit (when ≥ eligible); peak 1 for limit 1 | `tests/test_adversarial.py:151` — `judge.peak == 4`; l.152 wall time `< sum(DELAYS)`; l.157 — `judge.peak == 1` | ✅ PASS |
| ADV-02 same order + stats as sequential | kept in input order; judged/confirmed/refuted/uncertain/refuted_titles equal | `tests/test_adversarial.py:164-168` — titles `== ["A CONFIRMAR-ME","low-sev","C neutro"]`, judged tags, `(4,1,2,1)`, `refuted_titles == ["B REFUTAR-ME","D REFUTAR-ME"]`; for limit 1 and 4, with delays chosen so findings finish out of input order | ✅ PASS |
| ADV-03 judge raises → only that verdict missing, others unaffected | failing finding kept and not judged; others judged normally; other lens verdicts of the same finding kept | `tests/test_adversarial.py:175-179` — order, `A judged == "confirmed"`, `B.get("judged") is None`, `refuted_titles == ["C REFUTAR-ME"]` | ⚠️ PARTIAL. "Others unaffected" is covered. "Only that verdict" is not covered when `votes > 1`: `_Settings.adversarial_votes = 1` (l.30), so mutant r (`continue`→`break`) survives |

**Status**: 9/10 ACs fully covered; ADV-03 half-covered (gap 1).

---

## Gate Check

| Gate | Python 3.12.3 (`.venv`) | Python 3.10.21 (scratch venv) |
| ---- | ----------------------- | ----------------------------- |
| `pytest -q` | **154 passed**, 0 failed, 0 skipped (1 warning) | **154 passed**, 0 failed, 0 skipped |
| `ruff check src tests` | All checks passed | All checks passed |
| `mypy src` | no issues (34 files) | no issues (34 files) |

- Test count before the feature (HEAD src + HEAD tests in scratch): **137**. After: **154**. Delta **+17** (12 G34, 5 G35). No tests were removed, and no existing assertions were changed. The only fixture change is the added `max_concurrent_investigators` attribute.
- New tests run against the **old** code: 9 fail (SRCH-01, SRCH-02 ×5, SRCH-06 ×2, ADV-01 concurrency). They test new behaviour. SRCH-03 and SRCH-04 also passed on the old `root.glob`, so they act as regression guards.
- `make ci` also runs `frontend-ci` (npm). It was not run, because no frontend files changed and npm was out of scope for this run.

---

## Benchmark (scratch `bigproj`: 50 `src/*.py` + 20 000 files in `node_modules`; best of 3, pattern with no match)

| glob | before (HEAD, 3.12) | after (3.12) | after (3.10) | claim |
| ---- | ------------------- | ------------ | ------------ | ----- |
| `**/*` | **2 423.8 ms** | **6.6 ms** | 4.9 ms | 2 403 → 6.8 ms ✅ |
| `**/*.py` | 25.2 ms | 6.5 ms | 4.7 ms | 26 → 6.8 ms ✅ |
| `src/*.py` | 6.3 ms | 6.5 ms | 4.7 ms | 6 → 6.9 ms ✅ |

Hit counts were the same before and after (51 lines for every glob). Success criterion (< 0.1 s): ✅ met.

---

## Discrimination Sensor (P1, expanded: 18 manual mutants; each diffed, and the copy's `src` was confirmed imported via pyproject `pythonpath=["src"]`; full suite run)

| # | Mutation | File:line | Killed? |
| - | -------- | --------- | ------- |
| a | no `ignore_dirs` pruning (`dirnames[:] = list(dirnames)`) | filesystem.py:52 | ✅ by SRCH-01 (3.12 + 3.10) |
| b | `followlinks=True` | filesystem.py:47 | ✅ SRCH-02 ×3, SRCH-04 (3.12 + 3.10) |
| c | depth prune `>=` → `>` | filesystem.py:49 | ✅ SRCH-03 (3.12 + 3.10) |
| d | `**` = one or more dirs only | filesystem.py:35 | ✅ SRCH-02 ×3, SCOPE-05 ×3, SCOPE-06 |
| e | `fnmatchcase` → `fnmatch` | filesystem.py:36 | ➖ Survived; **behaves the same on Linux** (`normcase` is identity on POSIX) |
| f | results not sorted | filesystem.py:55 | ✅ SRCH-02/07 ×5 |
| g | empty-glob guard removed | filesystem.py:128 | ✅ SRCH-06 ×2 |
| h | `max_workers` fixed at 1 | adversarial.py:157 | ✅ ADV-01 (3.12 + 3.10) |
| i | aggregation in completion order | adversarial.py:164 | ✅ ADV-02 ×2, ADV-03 (3.12 + 3.10) |
| j | finding dropped when no verdict | adversarial.py:175 | ✅ ADV-03 |
| k | `_code_context` computed inside the worker | adversarial.py:159 | ➖ Survived; **harmless / behaves the same** (pure file read, no shared state, no console/SSE) |
| l | `..`/absolute guard removed | filesystem.py:125 | ✅ SCOPE-01 ×3, SCOPE-02 |
| m | relative `ignore_dirs` check removed from the loop | filesystem.py:143 | ❌ Survived (see gap 2) |
| n | at the depth limit, keep descending into non-ignored dirs | filesystem.py:50 | ✅ SRCH-03 |
| o | `_console.print` inside the worker thread | adversarial.py:114 | ❌ Survived (design rule, not an AC; gap 4) |
| p | workers = `len(to_judge)` (limit ignored) | adversarial.py:157 | ✅ ADV-01 limit 1 |
| q | always use lens 0 | adversarial.py:112 | ❌ Survived (votes > 1 never tested; earlier gap, gap 3) |
| r | `continue` → `break` after a lens error | adversarial.py:115 | ❌ **Survived: ADV-03 "only that verdict"** (gap 1) |

**Result**: 12 killed, 2 survived but behave the same as the real code (e, k), 4 survived with different behaviour (m, o, q, r). Only r is tied to an AC.

---

## Semantics vs old `root.glob` (same fixture, old vs new `search_code`, 3.12 and 3.10)

The new code is **SAME** as the old for: `**/*`, `./src/*.py`, `src//*.py`, `src/`, `src/*.[pt][ys]`, `[!t]*.py`,
`src/[[]x].py`, `.github/**/*.yml`, `**/.*`, `*`, `**/**/*.py`, `SRC/*.py` (case-sensitive), `**/*.PY`,
`**/node_modules/**` (empty), `**/env` / `build` (files named after ignored dirs are excluded in both).
Hidden files match `*` in both.

Where the new code **differs** (all deliberate or improvements):
- `src/**`, `src/**/`, `.github/**`, `**`: old gave 0 results (pathlib yields dirs), new gives the files below. This is the spec-intended change.
- `src\*.py`: old gave 0 on POSIX, new normalises `\` → `/`. Improvement.
- `*/` (3.12 only): old gave 0 (dirs only), new gives the top-level files, because the trailing slash is dropped. Harmless.
- `linkdir/*.py` (pattern explicitly through a symlinked dir that points inside the root): old found `linkdir/c.py`, new finds nothing. This follows SRCH-04 and the out-of-scope decision. The real target is still searched.
- Windows (reasoning, not executed): old pathlib glob was case-insensitive there; `fnmatchcase` is case-sensitive everywhere.
- Patterns with many `**` cost O(n^k) in `_glob_matches`, which is fine for realistic patterns. A prompt-injected `**/**/…` is bounded by path depth.

**Is the relative ignore check (filesystem.py:143) now dead code?** Not completely. Pruning stops it from ever seeing an ignored *ancestor* directory. It still excludes **files** whose name equals an ignored dir name (`build`, `env`, `bin`, `out`, `target`, …). That is the old behaviour, now untested (mutant m).

**Thread safety**: `_judge_votes` shares one `with_structured_output` runnable across threads. That is the same pattern `audit_node` already uses (one `llm` shared across investigator threads, audit.py:212/234). LangChain runnables do not keep per-invoke state, and the provider HTTP clients are thread-safe. Threads write nothing shared, and results come back through futures. All `_console.print` and `_emit` calls run on the main thread (adversarial.py:171, 193, 200). This matters because `ThreadPoolExecutor` does not carry over contextvars, so `get_stream_writer()` would silently do nothing inside a worker.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / surgical | ✅ (+42 / +41 lines, follows the inline design) |
| No scope creep | ✅ |
| Matches patterns (`audit_node` pool, `ERRO:` convention) | ✅ |
| Spec-anchored asserted values | ✅ (ADV-03 partial) |
| Every new test maps to an AC | ✅ (each test name carries its AC id) |
| Guidelines | none project-specific; strong defaults applied |
| Flakiness | ⚠️ `test_adv01` `peak == 4` needs all 4 threads to start within ~10 ms (D's delay). This is low risk, but it could flake on a loaded CI runner |

---

## Fix Plans

1. **ADV-03 multi-vote isolation (Minor, blocking for PASS)**. Add a test with `adversarial_votes = 2` (or 3) where one lens raises for a finding and another lens returns `confirmed`/`refuted`. Assert that the finding is still judged by the surviving lens (e.g. `refuted` → it lands in `refuted_titles`, or `judged == "uncertain"` per `_aggregate`). Assert also that the lens prompts differ (this kills r and q). Location: `tests/test_adversarial.py`.
2. **Files named like ignored dirs (Minor, non-blocking)**. Pin the current behaviour with a test, e.g. a root file `build` containing the needle is not returned. Alternatively, decide to search such files and drop filesystem.py:143. Either way, mutant m gets killed.
3. **Votes/lens path (Minor, existing gap)**. This is covered by fix 1.
4. **Console/SSE main-thread rule (Cosmetic)**. Optional test: patch `adv._console.print` to record `threading.current_thread()` and assert it is the main thread. This kills mutant o.

## Requirement Traceability Update (recommendation; spec.md left untouched by verifier)

| Requirement | Previous | New |
| ----------- | -------- | --- |
| SRCH-01..07 | Implementing | ✅ Verified |
| ADV-01, ADV-02 | Implementing | ✅ Verified |
| ADV-03 | Implementing | ⚠️ Needs test (fix 1) |

## Summary

**Overall**: ⚠️ one test is missing, and the code is correct.
**Spec-anchored check**: 9/10 full, 1 partial (ADV-03).
**Sensor**: 18 injected, 12 killed, 2 survived but behave the same as the real code, 4 survived (1 tied to an AC).
**Gate**: 154/154 on 3.12 and 3.10; ruff and mypy clean.
**Benchmark**: `**/*` 2 424 ms → 6.6 ms.

## Re-verification (fix loop 1)

**Gates:** pytest 160 passed; ruff clean; mypy 0 errors (34 files); py3.10 venv 160 passed.
**Flakiness:** `tests/test_adversarial.py` x20 (`-p no:cacheprovider`): 20/20 passed.

**Mutants** (scratch copies in `scratchpad/verifier15/`, `PYTHONPATH=src` so the copy's `auditor` was imported (checked via `auditor.__file__`), diff checked for each; `test_ci_config.py` skipped because it reads repo files that aren't in the copy):

| Mutant | Change | Result | Killing test(s) |
|---|---|---|---|
| r | `continue`→`break` after a lens error | KILLED | test_adv03 |
| q | always `JUDGE_LENSES[0]` | KILLED | test_adv03, test_adv04 |
| m' | re-add relative-path ignore check | KILLED | test_srch08 [build/env/bin/out] |
| o | warning print inside the `_judge_votes` worker | KILLED | test_adv04 |
| h | `max_workers=1` | KILLED | test_adv01 (barrier timeout, ~10 s run) |

**ADV-03 expectation:** `uncertain` matches `_aggregate`, which takes the majority over the votes requested: votes=2 with 1 confirmed gives 1 > 1 = false, so the result is uncertain. This fits the spec wording ("only that verdict SHALL be missing").
**SRCH-08:** spec.md says it is a behavior change. DOCUMENTACAO.md (~l.313) documents that files named build/env/bin/out are searched.

**Verdict: PASS.** All the gaps from the previous report (r, q, m', o, h) are resolved.
