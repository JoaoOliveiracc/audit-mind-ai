# create_agent Migration (G44) Validation

**Date**: 2026-11-10
**Spec**: `.specs/features/create-agent-migration/spec.md` (+ BUD-02..07 / EDGE-01..02 from `.specs/features/investigator-budget/spec.md`)
**Diff range**: uncommitted working tree vs `HEAD` (6f440e6) — `src/auditor/nodes/audit.py`, `tests/test_audit.py`, `pyproject.toml`, `requirements.txt` (G44 hunks only; ci-quality-gates hunks, e.g. the `get_stream_writer` annotation and `[dev]`/ruff config, were verified separately)
**Verifier**: independent sub-agent (author ≠ verifier)

**Verdict: ❌ FAIL (one minor gap, fix is a single test)**. Every AC traces to a test, and all 15 mutants the brief asked for (plus 4 of my own) were killed. Two extra mutants survived: the BUD-07 rewrite dropped its "dimension yields no structured result" assertion.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 migrate investigators + budget middleware | ✅ Done (impl) / ⚠️ test gap | BUD-07 second clause lost coverage (see Fix 1) |
| T2 docs | not in this verification's diff surface | — |

---

## Spec-Anchored Acceptance Criteria

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| MIG-01 built with `create_agent`, no `LangGraphDeprecatedSinceV10` | no warning of that class | `tests/test_audit.py:390` — `"LangGraphDeprecatedSinceV10" not in names`; `:391` no `create_react_agent` text; impl `src/auditor/nodes/audit.py:9,174` | ✅ PASS (mutant k killed) |
| MIG-02 no sub-graph checkpoints (AD-001) | only root namespace `""` written | `tests/test_audit.py:152` — `namespaces == {""}`; `:153` `write_namespaces <= {""}` | ✅ PASS (mutant h killed) |
| MIG-03 always-tool agent: exactly `max_model_calls` calls, no `GraphRecursionError`, all tool results kept | 12 steps → 6 calls; no raise; 6 results | `tests/test_audit.py:395-400` — `except GraphRecursionError: raise AssertionError`, `len(_agent_calls(...)) == 6`; `:273` `transcript.count("[resultado read_file]") == 6` | ✅ PASS (mutants c, d, g, i, m killed) |
| BUD-01r notice on last 2 calls only; system prompt first on every call | `[F,F,F,F,T,T]`; first 4 calls contain no notice; `m[0]` = investigator prompt | `tests/test_audit.py:250` — `notice == [False]*4 + [True]*2`; `:252` no notice in `calls[:4]`; `:248` `len(calls) == 6` with `_agent_calls` filtering on `m[0] == SystemMessage(system)` (`:240-241`) | ✅ PASS (mutants a1, a3, b, j, l killed) |
| BUD-02 one extra no-tools call with gathered results; text → structurer | 1 salvage call, unbound, transcript has tool output, ≤ 60 000 | `tests/test_audit.py:269,271,274,275,276` | ✅ PASS |
| BUD-02 bounds (2 000 / 60 000, most recent kept) | exact sizes | `tests/test_audit.py:300,305,306` | ✅ PASS (unchanged) |
| BUD-03 partial summary prefix | `PARTIAL_PREFIX + summary` | `tests/test_audit.py:277-279` | ✅ PASS (mutant e, n killed) |
| BUD-04 normal finish: no salvage, no prefix | `_salvage_calls()==[]`, plain summary | `tests/test_audit.py:290-293` | ✅ PASS |
| BUD-05 `partial` event + console + findings kept | status `partial`, `findings_count==1` | `tests/test_audit.py:330-334` (audit_node unchanged in diff) | ✅ PASS |
| BUD-06 delimited/untrusted/neutralized transcript | exactly one `<historico>` pair; untrusted wording | `tests/test_audit.py:344-347` | ✅ PASS |
| BUD-07 (a) exhausted + empty transcript → no salvage call | no salvage call | `tests/test_audit.py:359-360` — `report == ""`, `_salvage_calls() == [] and SALVAGE_VARIANTS == []` (unit level on `_salvage_report`) | ✅ PASS (mutant o killed) |
| BUD-07 (b) … and the dimension yields no structured result (`empty`) | `_investigate_dimension` returns `None`, structurer not called | **no evidence.** The old `assert dr is None` was dropped in the rewrite | ❌ GAP (mutants p, q survived) |
| EDGE-01 salvage raises → `_investigate_dimension` raises | `RuntimeError("falha no resgate")` | `tests/test_audit.py:366-367` — `pytest.raises(RuntimeError, match=...)` | ✅ PASS |
| EDGE-02 agent obeys notice → no salvage, no prefix | report = obeyed text | `tests/test_audit.py:373-375` | ✅ PASS |
| Marker never in salvage transcript | marker absent | `tests/test_audit.py:272` — `BUDGET_EXHAUSTED_MARKER not in transcript` | ✅ PASS (mutant f killed) |

**Status**: ❌ 1 gap (BUD-07 b). No spec-precision gaps.

---

## Discrimination Sensor

Scratch copy: `/tmp/claude-1000/-home-joao-Documentos-auditor-IA/3a865784-2fa5-4436-aa9a-ec628bd6b1d6/scratchpad/verifier10/` (src, tests, pyproject). I confirmed the copy's `auditor.nodes.audit` was the module imported, and the copy's baseline was 114 passed. The tests ran under the repo's `.venv/bin/pytest` with `PYTHONPATH=<copy>/src` and `--ignore=tests/test_ci_config.py`, because that test needs `.github/`, which is not part of G44. Script: `/tmp/claude-1000/-home-joao-Documentos-auditor-IA/3a865784-2fa5-4436-aa9a-ec628bd6b1d6/scratchpad/mut10.py`.

| # | File:line | Mutation | Killed? (by) |
| - | --------- | -------- | ------------ |
| a1 | `audit.py:40` | `_WRAP_UP_CALLS = 1` | ✅ notice test |
| a3 | `audit.py:40` | `_WRAP_UP_CALLS = 3` | ✅ notice test |
| b | `audit.py:147` | notice prepended | ✅ notice + EDGE-02 |
| c | `audit.py:140` | `>=` → `>` | ✅ notice, salvage, MIG-03 |
| d | `audit.py:141` | `before_model` never stops | ✅ 5 tests (GraphRecursionError → MIG-03 AssertionError) |
| e | `audit.py:80` | marker mismatch in `_budget_exhausted` | ✅ 4 tests |
| f | `audit.py:89` | marker not filtered from transcript | ✅ salvage test (`:272`) + BUD-07 |
| g | `audit.py:171` | `max_calls = steps` (no `//2`) | ✅ 3 tests |
| h | `audit.py:175` | `checkpointer=False` removed | ✅ SUB-01 (`:152`) |
| i | `audit.py:180` | `recursion_limit = max_calls` | ✅ 7 tests |
| j | `audit.py:174,177` | system prompt passed as a HumanMessage | ✅ notice + MIG-03 |
| k | `audit.py:9,174` | back to `create_react_agent` | ✅ 7 tests incl. MIG-01 |
| l (extra) | `audit.py:145` | `<=` → `<` in notice window | ✅ notice test |
| m (extra) | `audit.py:122` | count ToolMessages too | ✅ 3 tests |
| n (extra) | `audit.py:141` | marker emitted with a trailing space (exact `==` vs old `.strip()`) | ✅ 4 tests |
| o (extra) | `audit.py:110-111` | empty-transcript guard removed | ✅ BUD-07 unit test |
| p (extra) | `audit.py:187` | `if not report.strip() and not partial: return None` | ❌ **Survived** |
| q (extra) | `audit.py:187-188` | empty-report → `None` guard removed entirely | ❌ **Survived** |

**Sensor depth**: expanded (19 mutants).
**Result**: 17/19 killed. All 15 mutants from the brief were killed; extra mutants p and q survived, which means a fix task is needed.

---

## Gate Check

| Gate | Python 3.12 (.venv: langchain 1.3.11, langchain-core 1.4.8, langgraph 1.2.7) | Python 3.10 (scratch venv: langchain 1.4.9, langchain-core 1.7.7, langgraph 1.2.20) |
| ---- | --- | --- |
| `pytest -q` | 126 passed, 0 failed, 0 skipped (1 unrelated Starlette warning) | 126 passed |
| `ruff check src tests` | All checks passed | All checks passed |
| `mypy src` | 0 issues (34 files) | 0 issues (34 files) |
| `LangGraphDeprecatedSinceV10` in `tests/test_audit.py -W always` | 0 | — |

- `make ci`: not run in full, because its `frontend-ci` target touches npm and the brief allows no downloads. Its Python parts (lint, typecheck, test) are the gates above.
- Test count: `tests/test_audit.py` went from 15 to 17 (+2: MIG-01 and MIG-03; BUD-07 was rewritten). No tests were deleted.

---

## Assessments

1. **Changed tests.**
   - The BUD-01r pattern change and the salvage test's new assertions are legitimate spec revisions, and some of them are stronger than before (marker absent, 6 results kept).
   - The BUD-07 rewrite is only partly legitimate. Its premise holds: exhaustion needs ≥ 2 AIMessages that all carry tool_calls, so the condensed transcript always holds `[chamada]` lines and an empty transcript can't come through the agent. But the rewrite also dropped `dr is None`.
   - The `report.strip()` → `None` guard is still reachable on the partial path, whenever the salvage LLM returns empty text. Nothing tests it now (mutants p and q), so this is a weakening.
2. **`_model_calls` correctness.**
   - `request.messages` is `state["messages"]`. The system prompt travels separately as `request.system_message` (`langchain/agents/factory.py:1438-1440`), so it is not counted.
   - Without `response_format` there is no structured-response AIMessage.
   - Tool errors come back as ToolMessages.
   - The wrap-up notice is applied through `request.override`, so it is never stored in state and does not pile up.
   - Our marker AIMessage is only added on the jump to `end`, so it can't miscount a later call.
   - The run input is a single HumanMessage.
   - The count stays correct as long as no future middleware (retry or fallback) injects AIMessages. That is a latent assumption, documented in the docstring.
3. **Thread safety.** A new `_BudgetMiddleware(max_calls)` is built for each `_investigate_dimension` call. Its only attribute is an immutable int, and the counting is stateless (derived from messages). Nothing mutable is shared across the ThreadPoolExecutor workers.
4. **Dependency floors.**
   - `langgraph>=1.2`, `langchain>=1.3` and `langchain-core>=1.4` match between `pyproject.toml` and `requirements.txt`. They are justified, since `create_agent` and middleware need langchain 1.x, and they agree with the transitive constraints (langchain 1.3.11 requires core ≥ 1.4.7 and langgraph ≥ 1.2.5, < 1.3).
   - Side note: `langchain-anthropic>=0.3.0` is now a stale floor, because 0.3.x pins core < 1. The resolver still picks 1.x, so nothing breaks, but the floor is misleading. This belongs to G40 and is out of scope here.
5. **Regression in audit_node / SSE.**
   - `audit_node` and `_emit` are unchanged by G44.
   - The SSE `investigator` events (start, done, partial, empty, error) are still driven by `is_partial`, which BUD-05 covers.
   - The API streams `["updates", "custom"]` with no `subgraphs`, so the sub-agent's internal events never reached the client before either.
   - The middleware implements only the sync `wrap_model_call`. That is fine, because the code calls `agent.invoke`, but an `ainvoke` path would need `awrap_model_call`. This is latent, not a regression.

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / surgical | ✅ (one middleware class, removed `_make_prompt`, `_WRAP_UP_AT`, `_BUDGET_SENTINEL`) |
| No scope creep | ✅ |
| Matches patterns | ✅ |
| Spec-anchored asserted values | ✅ except BUD-07 (b) |
| Every test maps to an AC | ✅ |

---

## Fix Plans

### Fix 1: restore BUD-07 (b) coverage (Minor)
- **Root cause**: when BUD-07 was moved to unit level, the "no structured result" clause was dropped.
- **Fix task**: add a test that runs `_run_investigator(tmp_path, _always_tool_calls(), ...)` with the salvage returning empty text. Either add a `salvage_empty` flag to `_RecordingLLM` or monkeypatch `audit._salvage_report` to return `""`. Assert `dr is None` and `_structurer_inputs() == []`.
- **Done when**: mutants p and q are killed.

## Requirement Traceability Update

| Requirement | New Status |
| ----------- | ---------- |
| MIG-01, MIG-02, MIG-03, BUD-01r | ✅ Verified |
| BUD-02..06, EDGE-01..02 | ✅ Verified |
| BUD-07 | ❌ Needs Fix (clause b) |

## Re-verification (fix loop 1)

- Gates (real repo): pytest 127 passed; ruff check src tests: all checks passed; mypy src: no issues (34 files).
- New test `test_bud07_empty_salvage_report_yields_no_structured_result` runs the real investigator path with `salvage_empty=True` and asserts salvage called once, `dr is None`, structurer never invoked — matches BUD-07 second clause; not shallow.
- Mutants (scratch copies, copy's src confirmed imported, mutation confirmed by grep):
  - p (guard only when not partial): KILLED by the new test.
  - q (guard removed): KILLED by the new test.
- Gap 1: RESOLVED.
- Final verdict: PASS.
