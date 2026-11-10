# Coverage & End-to-End Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement with the `tlc-spec-driven` skill (Execute flow + Critical Rules). If it cannot be activated, STOP and tell the user.

**Spec**: `.specs/features/coverage-and-e2e/spec.md` · **Status**: Done

## Notes
This feature adds tests only (plus `pytest-cov`, a Makefile target and a CI step). Production code is
not expected to change; if a test exposes a real bug, it is surfaced to the user as a separate fix.

## Tasks
- **T1** `tests/test_nodes.py` — DISC/PQ/CL/PL unit tests (fake structured LLM; tiny graph + MemorySaver for the interrupt) · `test: unit tests for discovery, plan_questions, clarify and planning (G39)`
- **T2** `tests/fake_llm.py` + `tests/test_e2e.py::test_graph_end_to_end` (E2E-01) · `test: offline end-to-end run of the full graph`
- **T3** `tests/test_e2e.py::test_api_end_to_end` (E2E-02) · `test: offline end-to-end run through the HTTP API`
- **T4** `tests/test_e2e.py::test_cli_end_to_end` (E2E-03) · `test: offline end-to-end run through the CLI`
- **T5** `pytest-cov` in `[dev]`, `make coverage`, CI "Cobertura" step, `tests/test_ci_config.py` assertion for it (COV-01); record the measured % · `build: measure coverage locally and in CI`
- **T6** docs (README tests section, DOCUMENTACAO G39 ✅) · `docs: coverage and e2e tests (G39)`

## Gate
Quick `.venv/bin/pytest -q` · Build `make ci`

## Execution notes
- No production code changed; all new tests passed on first run (the Verifier's mutation pass is what proves they discriminate).
- E2E design: `tests/fake_llm.py` is stateless (decides from its input) → thread-safe for the investigator pool; adversarial judge enabled via env in e2e.
- Coverage after G39: **91%** total (1 690 stmts, 144 missed). Lowest: `cli.py` 80%, `api/routes.py` 82% (`/fs/browse` untested), `tools/filesystem.py` 83%.
- Suite: 179 → 193 tests (+10 node units, +3 e2e, +1 config); full run ~6.5 s.

## Post-PASS hardening (Verifier suggestions, no AC change)
- `.gitignore`: `.coverage`, `.coverage.*`, `htmlcov/`.
- `tests/fake_llm.py` now checks its input: `read_file` must be among the investigator's tools; the structurer input must contain the evidence. Self-check (mutation applied and confirmed): renaming the tool → 3 e2e fail; dropping the report before the structurer → 3 e2e fail (both survived before).
- `tests/test_e2e.py`: imports at top; `_wait_status` initializes `summary`.
