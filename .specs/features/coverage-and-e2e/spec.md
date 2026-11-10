# Coverage & End-to-End Specification (G39)

## Problem Statement

`discovery`, `plan_questions`, `clarify` and `planning` have no tests, and nothing runs the
**whole graph**: each node is tested in isolation, so a break in the wiring between them (a renamed
state field, a node returning the wrong key) only shows up in a real, paid audit. Coverage is not
measured.

## Goals
- [ ] Every graph node has unit tests for its spec'd behavior.
- [ ] The three entry points (graph, API, CLI) run end to end offline with a fake LLM.
- [ ] Coverage is measured locally and shown in CI (no threshold yet).

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Coverage threshold | User: measure first, decide the floor later. |
| Frontend coverage | Not requested. |
| Real-provider smoke tests | Need keys/tokens. |

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| E2E scope | graph + API + CLI | User decision. | y |
| Coverage | `pytest-cov` in `[dev]`, `make coverage`, separate CI step that reports (never fails on %) | User decision; separate step keeps the existing exact `pytest -q` gate (CI-06) untouched. | y |
| Fake LLM injection | monkeypatch `auditor.llm._build_llm` (the single factory behind every `get_llm`) | One patch point; no node changes. | y (agent) |
| Fake LLM behavior | structured outputs by schema (`ClarifyingQuestions` → 1 question, `AuditPlan` → `["security"]`, `DimensionResult` → 1 high finding with **real** evidence, `Verdict` → confirmed); agent: 1 `read_file` call then a text report; plain calls (synthesis) → fixed text | Exercises verify (evidence on disk) and the adversarial judge (enabled in e2e). | y (agent) |
| Settings in e2e | `AUDITOR_OUTPUT_DIR`, `AUDITOR_ADVERSARIAL_VERIFY=true` via env + `get_settings.cache_clear()` | Same path real users take. | y (agent) |

**Open questions:** none.

## User Stories

### P1: Node unit tests ⭐ MVP
1. **DISC-01** WHEN `discovery_node` gets a valid project THEN it SHALL return `stack_profile` (languages incl. Python, `has_tests`), a non-empty `inventory` listing the files, and `status == "discovered"`.
2. **DISC-02** WHEN the path is not a directory THEN it SHALL raise `ValueError`.
3. **PQ-01** WHEN `skip_questions` is true THEN `plan_questions_node` SHALL return `clarifying_questions == []` without calling the LLM.
4. **PQ-02** OTHERWISE it SHALL return the LLM's questions as dicts (`question`, `rationale`) and the prompt SHALL contain at most the first 6 000 chars of the inventory.
5. **CL-01** WHEN there are no questions THEN `clarify_node` SHALL NOT interrupt and SHALL return the existing `user_context` with `status == "clarified"`.
6. **CL-02** WHEN there are questions THEN it SHALL interrupt with `{"type": "clarifying_questions", "questions": [...]}`; resuming with a dict SHALL map it (stringified) to `user_context`; with a list SHALL map answers to questions by position (extras ignored); with anything else SHALL yield `{}`.
7. **PL-01** `planning_node` SHALL keep only dimensions in `AuditDimension`, in the LLM's order, and pass `focus_notes` through (`status == "planned"`).
8. **PL-02** WHEN no valid dimension remains THEN it SHALL use the default set (security, quality, architecture, testing, documentation).

### P1: End-to-end offline ⭐ MVP
1. **E2E-01 (graph)** WHEN the compiled graph runs on a fixture project THEN it SHALL pause at the clarification interrupt with the fake question; after resuming, the final state SHALL have plan `["security"]`, exactly 1 finding (`verified == True`, `judged == "confirmed"`), `health_score == 80`, the fake executive summary, and the 3 report files on disk (Markdown contains the finding title; SARIF has 1 result).
2. **E2E-02 (API)** WHEN driven through HTTP (`POST /audits` → wait `waiting_input` → `POST /answers` → wait `completed`) THEN the stored summary SHALL have `health_score == 80` and counts `{"high": 1}`; the SSE stream SHALL replay `phase`, `clarification`, `investigator`, `verification`, `adversarial` and `completed` events in that relative order; `/findings` SHALL return 1 finding; `/report?format=html|md|sarif` SHALL return 200 (SARIF as `application/sarif+json`).
3. **E2E-03 (CLI)** WHEN `auditor audit <dir>` runs with an answer on stdin THEN it SHALL exit 0, print the completion panel with `80/100`, and the printed report paths SHALL exist.

### P2: Coverage
1. **COV-01** `make coverage` SHALL run the suite with `--cov=auditor --cov-report=term-missing`; CI SHALL run a separate "Cobertura" step with the same report and SHALL NOT fail on the percentage.

## Requirement Traceability

| ID | Task | Status |
| -- | ---- | ------ |
| DISC-01..02, PQ-01..02, CL-01..02, PL-01..02 | T1 | Verified |
| E2E-01 | T2 | Verified |
| E2E-02 | T3 | Verified |
| E2E-03 | T4 | Verified |
| COV-01 | T5 | Verified |
