# Investigator Budget Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement with the `tlc-spec-driven` skill (Execute flow + Critical Rules). If it cannot be activated, STOP and tell the user.

**Design**: `.specs/features/investigator-budget/design.md` · **Status**: Done

## Test Coverage Matrix

> Same as `api-hardening/tasks.md` (guidelines: none — strong defaults).

| Code Layer | Test Type | Coverage Expectation | Location | Run |
| ---------- | --------- | -------------------- | -------- | --- |
| Graph nodes / helpers | unit (fake chat models; real prebuilt agent) | 1:1 ACs + edge cases | `tests/test_audit.py`, `tests/test_synthesis.py` | `.venv/bin/pytest -q` |
| Frontend components | unit (Vitest) | UI ACs | `frontend/src/components/*.test.tsx` | `./node_modules/.bin/vitest run` |
| Prompts / docs | none | build gate | — | — |

## Gate Check Commands

| Gate | Command |
| ---- | ------- |
| Quick | `.venv/bin/pytest -q` |
| Full | `cd frontend && ./node_modules/.bin/vitest run && ./node_modules/.bin/tsc --noEmit -p .` |
| Build | quick + `.venv/bin/ruff check src tests` + full |

## Execution Plan

Phase 1 (backend): `T1 → T2 → T3 → T4` · Phase 2: `T5 → T6`

## Task Breakdown

### T1: Shared text extraction + G33
**Where**: `nodes/_messages.py` (new), `nodes/synthesis.py`, `nodes/audit.py` (`_final_report` reuses it), `tests/test_synthesis.py` (new) · **Req**: SYN-01..02
**Done when**: synthesis tests with block/string content · quick gate · **Commit**: `fix(synthesis): extract plain text from content blocks`

### T2: Wrap-up notice via callable prompt
**Where**: `nodes/audit.py`, `prompts/templates.py`, `tests/test_audit.py` · **Depends on**: T1 · **Req**: BUD-01
**Done when**: test with an input-recording fake model through the real prebuilt agent asserts notice present only when `remaining_steps ≤ 5`, system prompt first · quick gate · **Commit**: `feat(audit): warn investigators before the step budget runs out`

### T3: Salvage report + partial prefix
**Where**: `nodes/audit.py`, `prompts/templates.py`, `tests/test_audit.py` · **Depends on**: T2 · **Req**: BUD-02..04
**Done when**: always-tool-calling fake → salvage call receives tool results (bounded), report structured, prefix; obedient fake → no salvage, no prefix; truncation bounds asserted · quick gate · **Commit**: `feat(audit): salvage a partial report when the step budget is exhausted`

### T4: `partial` status in audit_node
**Where**: `nodes/audit.py`, `tests/test_audit.py` · **Depends on**: T3 · **Req**: BUD-05
**Done when**: event status `partial` with findings_count, findings kept, console warning · build gate (end of phase 1) · **Commit**: `feat(audit): report partial dimensions as their own status`

### T5: Partial status in the timeline
**Where**: `frontend/src/types.ts`, `frontend/src/components/Timeline.tsx`, `Timeline.test.tsx` (new) · **Depends on**: T4 · **Req**: UI-01
**Done when**: Vitest renders a partial dimension (label + count, finished icon) · full gate · **Commit**: `feat(frontend): show partial investigator status`

### T6: Docs
**Where**: `DOCUMENTACAO.md`, `docs/USAGE.md`, `docs/ARCHITECTURE.md`, `.env.example` · **Depends on**: T5 · build gate · **Commit**: `docs: document step budget, partial dimensions (G32/G33)`

## Validation
Granularity ✅ (T1 helper+its 2 call sites cohesive ⚠️ OK). Diagram ↔ deps ✅ (linear). Co-location: T1–T4 unit ✅, T5 unit ✅, T6 none ✅.

## Fix loop 1 (after Verifier FAIL minor)

| Gap | Fix | Tests (`tests/test_audit.py`) |
| --- | --- | ----------------------------- |
| 1 BUD-02 "without tools" unasserted (mutant r) | fake records `bound` variant per call | `SALVAGE_VARIANTS == [False]` in the salvage test |
| 2 BUD-03 literal (mutant s) | assert spec literal | same test |
| 3 Edge cases only indirect | EDGE-01 salvage raises; EDGE-02 agent obeys notice | `test_salvage_failure_propagates_for_isolation`, `test_agent_obeying_the_notice_needs_no_salvage` |
| 4 Docs priority line duplicated | fixed | — |
| 5 Empty transcript → provider error | BUD-07: no salvage call, dimension `empty` | `test_exhausted_with_empty_transcript_makes_no_salvage_call` |
| Injection hardening (assessment) | BUD-06: `<historico>` delimiters, untrusted-data line in `SALVAGE_PROMPT`, inner delimiters neutralized | `test_salvage_transcript_is_delimited_untrusted_and_cannot_close_the_block` |

Note: the 60 000-char cap applies to the transcript inside the delimiters (+26 chars of wrapper).
