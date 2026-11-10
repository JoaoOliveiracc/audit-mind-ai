# Coverage & E2E (G39) Validation

**Date**: 2026-11-10
**Spec**: `.specs/features/coverage-and-e2e/spec.md`
**Diff range**: uncommitted working tree on `develop` vs `HEAD` (`f47755a`)
**Verifier**: independent sub-agent (author ≠ verifier)

**Verdict**: ✅ **PASS** (16/16 ACs, 0 spec-precision gaps; 21/21 mutants killed; minor gaps below)

---

## Diff surface

| File | Change |
| ---- | ------ |
| `tests/test_nodes.py` (new) | 6 test functions / 10 cases: DISC-01..02, PQ-01..02, CL-01..02, PL-01..02 |
| `tests/fake_llm.py` (new) | deterministic `FakeLLM` (structured outputs by schema, one `read_file` tool call, then a text report) |
| `tests/test_e2e.py` (new) | E2E-01 (graph), E2E-02 (HTTP + SSE), E2E-03 (CLI) |
| `tests/test_ci_config.py` | `test_cov01_coverage_step_reports_without_threshold` |
| `pyproject.toml` | `pytest-cov>=5` in `[dev]` |
| `Makefile` | `coverage` target (+ `.PHONY`) |
| `.github/workflows/ci.yml` | step "Cobertura (só reporta)" |
| `README.md`, `DOCUMENTACAO.md` | docs (G39 ✅, `make coverage`) |
| `src/` | **no changes** (`git diff --stat -- src/` is empty) ✅ |
| `.coverage` | untracked artifact, **not gitignored** (see gap 1) |

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 node unit tests | ✅ Done | `tests/test_nodes.py` |
| T2 fake LLM + E2E-01 | ✅ Done | fake lives at `tests/fake_llm.py` (not `tests/e2e/fake_llm.py` as tasks.md T2 says; execution notes match the real path) |
| T3 E2E-02 | ✅ Done | - |
| T4 E2E-03 | ✅ Done | - |
| T5 COV-01 | ✅ Done | 91% recorded |
| T6 docs | ✅ Done | - |

---

## Spec-Anchored Acceptance Criteria

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| DISC-01 | `stack_profile` languages incl. Python, `has_tests`, non-empty inventory listing files, `status=="discovered"` | `tests/test_nodes.py:41-44`: `out["status"] == "discovered"`, `languages["Python"] == 2`, `has_tests is True`, `"app.py" in out["inventory"] and "test_app.py" in ...` | ✅ |
| DISC-02 | invalid path → `ValueError` | `tests/test_nodes.py:48`: `pytest.raises(ValueError)` | ✅ |
| PQ-01 | `skip_questions` → `[]`, no LLM call | `tests/test_nodes.py:57-58`: `get_llm` patched to raise; `== {"clarifying_questions": []}` | ✅ |
| PQ-02 | LLM questions as dicts (`question`,`rationale`); prompt has at most first 6 000 chars of inventory | `tests/test_nodes.py:69-72`: `out == {"clarifying_questions": [{"question": "Produção?", "rationale": "foco"}]}`; `"X"*6_000 in prompt and "X"*6_001 not in prompt` | ✅ |
| CL-01 | no questions → no interrupt, existing `user_context`, `status=="clarified"` | `tests/test_nodes.py:88-89`: `out == {"user_context": {"a": "b"}, "status": "clarified"}` (called outside a graph, so an `interrupt()` would raise — no-interrupt is implicitly proven) | ✅ |
| CL-02 | interrupt payload `{"type": "clarifying_questions", "questions": [...]}`; dict → stringified; list → by position, extras ignored; other → `{}` | `tests/test_nodes.py:92-108` (real `StateGraph` + `MemorySaver`): `interrupt == {"type": "clarifying_questions", "questions": QS}`; `values["user_context"] == expected` for `{"Q2?": 3}→"3"`, `["sim","não","extra"]→{Q1,Q2}`, `"texto solto"→{}`; `status == "clarified"` | ✅ |
| PL-01 | keep only valid dims, LLM order, `focus_notes` passthrough, `status=="planned"` | `tests/test_nodes.py:118`: `out == {"plan": {"dimensions": ["testing", "security"], "focus_notes": "foco X"}, "status": "planned"}` | ✅ |
| PL-02 | none valid → default set (security, quality, architecture, testing, documentation) | `tests/test_nodes.py:128`: exact list equality | ✅ |
| E2E-01 | pause at interrupt with fake question; plan `["security"]`; 1 finding `verified`/`judged=="confirmed"`; `health_score==80`; fake summary; 3 report files; MD has title; SARIF 1 result | `tests/test_e2e.py:54-55` (question), `:61` plan, `:62-66` finding + counters, `:67` `== 80`, `:68` `== SUMMARY`, `:69` status, `:38-44` files exist in output dir, title in MD, `len(results) == 1` | ✅ |
| E2E-02 | HTTP flow; summary `health_score==80`, `counts=={"high":1}`; SSE `phase, clarification, investigator, verification, adversarial, completed` in relative order; `/findings` 1; `/report` html/md/sarif 200, SARIF `application/sarif+json` | `tests/test_e2e.py:100-108` (201, waits, answers 200, `== 80`, `== {"high": 1}`), `:112-115` (`events.index(name)` for all six, `first == sorted(first)`), `:118` `== [FINDING_TITLE]`, `:123-126` (200×3, title in html/md, content-type, 1 result) | ✅ |
| E2E-03 | exit 0, completion panel with `80/100`, printed report paths exist | `tests/test_e2e.py:141-150`: `exit_code == 0`, `"Auditoria concluída"`, `"80/100" in output`, regex extracts Markdown/HTML/SARIF paths, `p.is_file() and p.parent == reports` | ✅ |
| COV-01 | `make coverage` runs `--cov=auditor --cov-report=term-missing`; separate CI "Cobertura" step with the same report; no failure on % | `tests/test_ci_config.py:135-141`: step `run == "pytest -q --cov=auditor --cov-report=term-missing"`, `"fail-under" not in _runs("backend")`, Makefile regex, `"pytest-cov>=5"` in pyproject | ✅ |

**Status**: ✅ All ACs covered; no spec-precision gaps.

---

## Gate Check

| Gate | Python 3.12 (`.venv`) | Python 3.10 (scratch venv) |
| ---- | --------------------- | -------------------------- |
| `pytest -q` | **193 passed**, 0 failed, 0 skipped (6.5 s) | **193 passed**, 0 failed (6.6 s) |
| `ruff check src tests` | All checks passed | n/a |
| `mypy src` | no issues (36 files) | n/a |
| `make coverage` | 193 passed, **TOTAL 1690 stmts, 144 missed, 91%** | pytest-cov not installed in the scratch venv (it predates the new dep; CI installs `[dev]` fresh) |

- Tests before: 179 → after: 193 (+14 = 10 node cases + 3 e2e + 1 config). No tests removed or weakened.
- Coverage of the target nodes: `discovery.py`, `clarify.py`, `planning.py` all 100%. Lowest: `cli.py` 80%, `api/routes.py` 82%, `tools/filesystem.py` 83%.

---

## Discrimination Sensor

Scratch copy at `scratchpad/verifier18/` (src, tests, pyproject, Makefile, .github, frontend/package*.json); repo `.venv/bin/pytest` run from inside the copy with `PYTHONPATH=<copy>/src`; `auditor.__file__` confirmed under the copy for each mutant. Full suite per mutant. Script: `scratchpad/mut18.py`, `scratchpad/cov_mut.sh`.

| # | File:line | Mutation | Killed? | Killed by |
| - | --------- | -------- | ------- | --------- |
| w1 | `graph.py:59` | `verify→adversarial` ⇒ `verify→synthesis` (judge skipped) | ✅ | `test_e2e01` (`judged`/`adversarial`), `test_e2e02` (SSE `adversarial` missing) |
| w2 | `nodes/audit.py:263` | returns `finding` instead of `findings` | ✅ | e2e01/02/03 + 4 × `test_audit.py` |
| w3 | `graph.py:61` | `synthesis→END` (report skipped) | ✅ | e2e01/02/03 |
| w4 | `nodes/synthesis.py:20` | `score = 100` | ✅ | e2e01/02/03, `test_synthesis.py` |
| w5 | `api/runner.py:25` | `include_zero=True` | ✅ | `test_e2e02` (`counts == {"high": 1}`), `test_api::test_counts_helper`, `test_shared::test_dup03` |
| w6 | `nodes/clarify.py:66` | returns `user_ctx` | ✅ | `test_e2e01`, `test_cl02` ×3 |
| w7 | `nodes/audit.py:197` | reads `plan["dims"]` | ✅ | e2e01/02/03 + 4 × `test_audit.py` |
| w8 | `cli.py:193-195` | report paths not printed | ✅ | `test_e2e03` only |
| w9 | `api/routes.py:101` | `skip_questions = req.interactive` | ✅ | `test_e2e02` only (timeout waiting `waiting_input`) |
| u1 | `nodes/discovery.py:16` | no raise on invalid path | ✅ | `test_disc02` |
| u2 | `nodes/clarify.py:22` | `skip_questions` ignored | ✅ | `test_pq01` |
| u3a | `nodes/clarify.py:29` | `[:6000]` ⇒ `[:600]` | ✅ | `test_pq02` |
| u3b | `nodes/clarify.py:29` | truncation removed | ✅ | `test_pq02` |
| u4a | `nodes/clarify.py:60` | `enumerate(answers, start=1)` | ✅ | `test_cl02[list]` |
| u4b | `nodes/clarify.py:61` | `i < len` ⇒ `i <= len` | ✅ | `test_cl02[list]` |
| u5 | `nodes/planning.py:36` | no dimension filter | ✅ | `test_pl01`, `test_pl02` |
| u6 | `nodes/planning.py:19` | default set loses `documentation` | ✅ | `test_pl02` |
| c1 | `ci.yml:45` | add `--cov-fail-under=95` | ✅ | `test_cov01` |
| c2 | `Makefile:21` | `coverage` target drops `--cov` | ✅ | `test_cov01` |
| c3 | `pyproject.toml:33` | `pytest-cov` dep removed | ✅ | `test_cov01` |
| c4 | `ci.yml` | `continue-on-error` on the step (probe) | ✅ | pre-existing `test_ci06` (forbids it) |

**Sensor depth**: expanded (21 mutants). **Result**: 21/21 killed — ✅ PASS.
Wiring mutants w8 and w9 are killed **only** by the new E2E tests, and w1/w3 only by E2E, which is the G39 goal.

---

## Flakiness

- `tests/test_e2e.py` × 20 sequential runs (3.12): **20/20 pass**; call times 0.05 s (graph), 0.21 s (API), 0.07 s (CLI).
- 6 concurrent processes × 3 rounds (load): **18/18 pass**.
- 3.10: `test_e2e.py` + `test_nodes.py` × 5: **5/5 pass**.
- Determinism reasoning: the fake is stateless and returns deep copies, so it is safe across the investigator thread pool. API polling has a 15 s timeout with 50 ms steps and fails fast on `error`. The SSE replay is race-free: the runner sets the store to `completed` *before* emitting `completed`, but the SSE generator only stops at `__end__` (emitted after `done.set()`), so a stream opened after `completed` always replays every event. The CLI sets `COLUMNS=400` so Rich does not wrap paths.

## Fake LLM faithfulness (assessment)

- **Adequate for wiring**: it is injected at `_build_llm`, the real `get_llm`, the `create_agent` ReAct loop, the real `read_file` tool, the `verify` disk check and the adversarial node all run for real. `bind_tools` returns a `model_copy(bound=True)`. That is a `BaseChatModel` (a Runnable that emits `AIMessage` with `tool_calls`), which is what `create_agent` needs; extra kwargs are accepted. An unknown schema raises `KeyError`, which fails loudly.
- **Bypasses**: (a) `with_structured_output` returns a `RunnableLambda` with a canned object. It never goes through the provider's tool-calling or JSON parsing, never returns `None`, never raises a parse failure, and ignores `method`/`include_raw` kwargs. (b) It ignores its inputs entirely, so E2E would **not** catch broken prompt/context wiring *into* LLM calls (e.g. the structurer not getting the report text, `user_context` dropped from the planning prompt, or the inventory missing from the clarify prompt; PQ-02 covers that last one at unit level). (c) `bind_tools` ignores the tool list: if the tool were renamed, the agent would return an error `ToolMessage`, and the fake would still write its report because it only checks `isinstance(messages[-1], ToolMessage)`. (d) The budget-exhaustion and salvage paths are not exercised (they are covered in `test_audit.py`).

## COV-01 CI step

Correct: a separate step after the exact `pytest -q` gate (CI-06 untouched), same `--cov=auditor --cov-report=term-missing` report as Makefile, no `--cov-fail-under` and no `fail_under` in pyproject (no `.coveragerc`/`setup.cfg`). It is non-blocking **on percentage**. It still fails if a test fails, which is redundant with the step before it and is consistent with CI-06, which forbids `continue-on-error`. Cost: it runs the suite a second time (about 7 s).

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / surgical (tests + config only; src untouched) | ✅ |
| No scope creep | ✅ |
| Matches patterns (Portuguese docstrings, `test_<ac-id>_` naming, monkeypatch of `get_llm` like other node tests) | ✅ |
| Spec-anchored outcomes (exact values) | ✅ |
| Every test maps to an AC (E2E-03's extra `QUESTION in output` supports "answer on stdin") | ✅ |
| Guidelines: none documented beyond `tests/conftest.py` isolation (ISO-03), which is respected (no `~/.config/auditor` access) | ✅ |
| Minor style: mid-file imports with `# noqa: E402` in `test_e2e.py` (lines 74-78, 130-134) instead of a top-level import block | ⚠️ cosmetic |

---

## Ranked gaps (none blocking)

1. **Minor**: `.coverage` is generated in the repo root, is untracked, and is **not in `.gitignore`**, so it could be committed by accident. Fix: add `.coverage` (and `htmlcov/`) to `.gitignore`.
2. **Minor**: the fake LLM is input-blind (see the faithfulness section). E2E cannot catch broken prompt or context wiring into the LLM, or a tool-name mismatch. Optional fix: have the fake assert that the structurer input contains the `read_file` output (`EVIDENCE`), and that `read_file` is among the bound tools.
3. **Cosmetic**: in `tests/test_e2e.py`, the imports are spread mid-file (E402 noqa). In `_wait_status`, `summary` is unbound if `timeout <= 0`. If an E2E-02 assertion fails, the daemon runner thread can outlive the monkeypatch.
4. **Doc nit**: tasks.md T2 names `tests/e2e/fake_llm.py`, but the actual file is `tests/fake_llm.py`.
5. **Info**: the scratch 3.10 venv lacks `pytest-cov`, so `make coverage` was not exercised on 3.10 locally. CI installs `[dev]` fresh, so this does not affect CI.

## Requirement Traceability Update

| Requirement | Previous | New |
| ----------- | -------- | --- |
| DISC-01..02, PQ-01..02, CL-01..02, PL-01..02 | Implementing | ✅ Verified |
| E2E-01, E2E-02, E2E-03 | Implementing | ✅ Verified |
| COV-01 | Implementing | ✅ Verified |

## Summary

**Overall**: ✅ Ready. 16/16 ACs matched spec outcomes. 21/21 mutants killed. Gates green on 3.12 and 3.10 (193 passed). Coverage 91%. E2E has 0 flakes in 41 runs.
