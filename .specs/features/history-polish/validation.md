# Report Names & History Polish Validation (G45 + G46)

**Date**: 2026-11-10
**Spec**: `.specs/features/history-polish/spec.md`
**Diff range**: uncommitted working tree on `develop` vs `HEAD` (8a33083)
**Verifier**: independent sub-agent (author ≠ verifier)

**Verdict: ❌ FAIL.** Every AC is covered and the gates are green, but one mutant that matters
survived: if the `finally` that clears `resumingId` is removed, no test fails, so a failed resume
would leave Retomar stuck. Two lower-priority mutants also survived.

---

## Diff surface

| File | Change |
| ---- | ------ |
| `src/auditor/report/renderer.py` | `_id8`, `_free_base`, `_write_new` (`open("x")`), `write_reports(..., run_id=None)` |
| `src/auditor/nodes/report.py` | `report_node(state, config)` passes `configurable.thread_id` as `run_id` |
| `tests/test_report_names.py` (new) | 9 tests (REP-01..05) |
| `frontend/src/App.tsx` | `resumingId` state + re-entry guard + `finally`; `handleOpenAudit` branches for `interrupted`/`error` |
| `frontend/src/components/History.tsx` | `busyId` prop → `disabled` + label `Retomando…` |
| `frontend/src/App.test.tsx` | 4 new tests (HIS-01..03) |
| README.md, docs/USAGE.md, docs/SPEC.md, DOCUMENTACAO.md | name format; G45/G46 marked done |

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 (REP-01..04) | ✅ Done | — |
| T2 (REP-05) | ✅ Done | checked against the real compiled graph (see below) |
| T3 (HIS-01..03) | ⚠️ Done, weak tests | the failure path that resets `resumingId` is untested (mutant l survived) |
| T4 docs | ✅ Done | one inaccurate phrase in README (see Gap 4) |

---

## Spec-Anchored Acceptance Criteria

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| REP-01 | `auditoria-<stamp>-<id8(T)>.{md,html,sarif}` inside output dir | `tests/test_report_names.py:33` — `_names(paths) == [f"auditoria-{STAMP}-abcdef12.md", …html, …sarif]`; `:35` — `all(p.parent == tmp_path …)` | ✅ PASS |
| REP-02 | same second, different runs → distinct files, neither modified | `tests/test_report_names.py:45` — `set(_names(first)).isdisjoint(_names(second))`; `:46` — `[p.read_bytes() for p in first] == before` | ✅ PASS |
| REP-03 | existing name → not overwritten; next `-N` for all 3 files | `tests/test_report_names.py:56` — `_names(again) == […-samesame-2.md, -2.html, -2.sarif]`; `:59` — original content unchanged; `:65-66` — a partial collision (only `.sarif` exists) moves `.md` to `-2` and leaves the old `.sarif` intact | ✅ PASS |
| REP-04 (missing/empty/no-alnum) | 8 random hex chars | `tests/test_report_names.py:73` — `re.fullmatch(rf"auditoria-{STAMP}-[0-9a-f]{{8}}\.md", …)`, parametrized over `None`, `""`, `"../--//!!"` | ✅ PASS |
| REP-04 (other chars dropped, stays inside) | `../a/b-c_d.e/f9` → `abcdef9`, parent == output dir | `tests/test_report_names.py:78` — `== f"auditoria-{STAMP}-abcdef9.md"`; `:79` — `all(p.parent == tmp_path …)` | ✅ PASS |
| REP-05 | `report_node` takes `thread_id` from the run config | `tests/test_report_names.py:90-91` — `out["report_html_path"].endswith(f"…-1234abcd.html")` (`.sarif` too); also checked in the real graph (below) | ✅ PASS |
| HIS-01 | no stream; stays on history; exact message | `frontend/src/App.test.tsx:79` — alert `toHaveTextContent('Auditoria interrompida — use Retomar para continuar do último checkpoint.')`; `:82` — `connectAuditStream` not called; `:83` — the Retomar button is still rendered (still on the history) | ✅ PASS |
| HIS-02 (with error text) | `Auditoria falhou: <error>`; no stream; stays on history | `frontend/src/App.test.tsx:90` — `'Auditoria falhou: rate limit do provedor'`; `:91` — no stream; `:92` — row `/proj/err` still shown | ✅ PASS |
| HIS-02 (no error text) | `Auditoria falhou.` | `frontend/src/App.test.tsx:98` — `toHaveTextContent(/^Auditoria falhou\.$/)` (does not re-check no-stream/history, but those come from the same `return` branch already covered by `:91-92`) | ✅ PASS |
| HIS-03 | while in flight: disabled, label `Retomando…`, further clicks send nothing | `frontend/src/App.test.tsx:108` — `toBeDisabled()`; `:109` — `toHaveTextContent('Retomando…')`; `:111` — `resumeAudit` `toHaveBeenCalledTimes(1)` | ✅ PASS (see Gap 2: `:111` cannot fail independently) |

**Status**: 8/8 ACs map to an assertion on the exact outcome the spec defines. No spec-precision gaps.
Implied edge case **not** covered: after a resume fails, the button must work again ("only while in flight"). See Gap 1.

---

## Discrimination Sensor

Scratch copy: `…/scratchpad/verifier12/{be,fe}`. Each mutant was applied with an exact-match
replace script that aborts unless there is exactly one match, then checked with `diff` against
the real tree. Import sanity checks: a `raise` injected in the copy's `renderer.py` broke every
backend test module, and a `throw` injected in the copy's `App.tsx` failed `App.test.tsx`, so the
tests ran the copies. The unmutated copy passed 136/136.

| # | Mutation | File:line | Killed? | By |
| - | -------- | --------- | ------- | -- |
| a | no sanitizing (`cleaned = run_id or ""`) | `renderer.py:180` | ✅ Killed | test_report_names `[../--//!!]`, `unsafe_chars` |
| b6 | `cleaned[:6]` | `renderer.py:181` | ✅ Killed | 5 tests |
| b10 | `cleaned[:10]` | `renderer.py:181` | ✅ Killed | `:33`, `:90` |
| c | `_free_base` checks `.md` only | `renderer.py:187` | ✅ Killed | partial-collision test (FileExistsError) |
| d1 | `"w"` + `_free_base` bypassed | `renderer.py:186,194` | ✅ Killed | `:56`, `:65` (the overwrite is caught) |
| d2 | `"w"` only (`_free_base` intact) | `renderer.py:194` | ❌ Survived | no test covers the race window (see Gap 3) |
| d3 | `_free_base` bypassed only (`"x"` intact) | `renderer.py:186` | ✅ Killed | FileExistsError |
| e | no random fallback | `renderer.py:181` | ✅ Killed | 3 params of `:73` |
| f | `report_node` ignores config | `nodes/report.py:20` | ✅ Killed | `:90` |
| g | App: `interrupted` branch removed | `App.tsx:149-152` | ✅ Killed | HIS-01 |
| h | App: `error` branch removed | `App.tsx:153-156` | ✅ Killed | both HIS-02 tests |
| i | error message without `${a.error}` | `App.tsx:154` | ✅ Killed | HIS-02 `:90` |
| j | History: `disabled` removed | `History.tsx:66` | ✅ Killed | `:108` |
| k | re-entry guard + `disabled` both removed | `App.tsx:124`, `History.tsx:66` | ✅ Killed | `:108` (`toBeDisabled`), not `:111` |
| k2 | re-entry guard only removed | `App.tsx:124` | ❌ Survived | redundant with `disabled` (see Gap 2) |
| l | `finally { setResumingId(null) }` removed | `App.tsx:137-139` | ❌ **Survived** | nothing: the button stays stuck after a failure (see Gap 1) |
| m | label always `Retomar` | `History.tsx:69` | ✅ Killed | `:109` |

**Sensor depth**: expanded (17 mutants).
**Result**: 14/17 killed, 3 survived. **FAIL ❌** (l matters to users; d2 and k2 are minor).

---

## Additional assessments

- **`open(..., "x")` race.** Two writers can both pass `_free_base` with the same base name only if they have the same `id8` in the same second. That needs the same `thread_id`, which the API's 409 already prevents for one audit, or a 1 in 2³² collision of the random fallback. If it does happen, the losing writer's first `open("x")` raises `FileExistsError`. That error propagates out of `report_node`, so that audit ends in `error`. Nothing is overwritten. The loser gets no reports, and it leaves no orphans because it fails on the first file it hits. **Acceptable** given how unlikely it is, though a retry on `FileExistsError` (with the next `-N`) would be stronger. No test covers it (d2).
- **Real graph injection (REP-05).** Checked: `build_graph()` (`src/auditor/graph.py:51`), then `update_state(cfg, state, as_node="synthesis")`, then `invoke(None, {"configurable": {"thread_id": "deadbeef-1234-5678"}})`. This produced `auditoria-<stamp>-deadbeef.{md,html,sarif}`. LangGraph 1.2.7 injects `config` by parameter name and annotation. The ids come from `api/runner.py:51`, `api/routes.py:223` (uuid4 hex) and `cli.py:125` (uuid4 hex).
- **Existing callers of `write_reports`.** The only caller is `nodes/report.py`. The new `run_id` defaults to `None`, so the old signature still works. No code globs the old `auditoria-<stamp>.*` pattern. The full suite (136) is green.
- **UX after the messages.** The interrupted and error branches `return` before `setAuditId` and `dispatch`, so `state.status` stays `idle` and the history stays rendered and clickable. HIS-01 `:83` asserts that Retomar is present, and HIS-02 `:92` asserts the row is present. Opening another row clears the alert (`setStartError(null)`). **However**, after a *failed* resume the UI depends entirely on the `finally`, which no test protects (Gap 1). `resumingId` is a single global slot, so a stuck value would also block resuming *any* audit through the guard at `App.tsx:124`.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / surgical | ✅ |
| No scope creep | ✅ |
| Matches patterns | ✅ |
| Stale comment | ⚠️ `App.tsx:172` still says `// running / waiting_input / error:`, but `error` never reaches that branch now |
| Spec-anchored assertions | ✅ |
| Every test maps to an AC | ✅ |
| Guidelines | none project-specific beyond tasks.md; strong defaults applied |

---

## Gate Check

| Gate | Result |
| ---- | ------ |
| `.venv/bin/pytest -q` | 136 passed, 0 failed, 0 skipped (before: 127; delta +9) |
| `.venv/bin/ruff check src tests` | All checks passed |
| `.venv/bin/mypy src` | Success: no issues in 34 source files |
| `vitest run` | 31 passed, 5 files (before: 27; delta +4) |
| `tsc --noEmit -p .` | exit 0 |

---

## Ranked gaps / Fix plans

1. **(Major) Nothing tests that `resumingId` is reset after a failed resume.** Mutant l survived. Fix: in `App.test.tsx`, extend the UI-03 failure test (or add a HIS-03 test) so that after `resumeAudit` rejects it asserts the button is enabled again with label `Retomar`, and that a second click calls `resumeAudit` a second time.
2. **(Minor) The re-entry guard is never exercised on its own.** Mutant k2 survived. `:111` cannot fail while `disabled` is in place, because jsdom and React skip `onClick` on disabled buttons. Fix: either drop the guard as redundant, or test it directly, for example by firing two clicks in the same tick before re-render, or by triggering the handler while another audit's resume is in flight.
3. **(Minor) Nothing tests that `"x"` alone prevents an overwrite (race window).** Mutant d2 survived. Fix: monkeypatch `renderer._free_base` to return an existing base, then assert `FileExistsError` and that the original file is unchanged.
4. **(Cosmetic)** README.md:52 says the id is "as shown in the web history", but `History.tsx` never renders `a.id`. Also fix the stale comment at `App.tsx:172`.

## Requirement Traceability Update

| Requirement | New Status |
| ----------- | ---------- |
| REP-01..05 | ✅ Verified |
| HIS-01, HIS-02 | ✅ Verified |
| HIS-03 | ⚠️ Verified for the in-flight state; reset after failure is unprotected (Gap 1) |

## Re-verification (fix loop 1)

**Gates (real repo):** pytest 137 passed · ruff clean · vitest 33/33 · tsc --noEmit OK.

**Mutants (scratch: verifier13/, each applied and confirmed via diff):**

| Mutant | Change | Result | Killing test |
|---|---|---|---|
| d2 | `path.open("x")` -> `"w"` (`_free_base` intact) | KILLED | test_report_names.py::test_exclusive_create_never_overwrites_even_if_free_base_is_wrong |
| k2 | removed `if (resumingId) return` (App.tsx) | KILLED | App.test.tsx "com uma retomada em voo, Retomar de OUTRA auditoria não dispara outra requisição" |
| l | removed `setResumingId(null)` in `finally` | KILLED | App.test.tsx "após falha, o botão volta a \"Retomar\" habilitado e pode tentar de novo" |

**Test quality:** the new tests check outcomes from the spec (FileExistsError raised and the original file content kept; no second resume request; button re-enabled and a retry works). None of them are shallow.

**Gaps:** all 3 previous survivors are now RESOLVED.

**Verdict: PASS**
