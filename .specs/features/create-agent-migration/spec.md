# create_agent Migration Specification (G44)

## Problem Statement

`langgraph.prebuilt.create_react_agent` is deprecated since LangGraph 1.0 and will be removed in
2.0 (warning in every investigator run). Its replacement, `langchain.agents.create_agent`, has no
callable `prompt`, no `remaining_steps` and no "need more steps" sentinel — the three hooks the
G32 step-budget logic relies on — and **raises `GraphRecursionError` when `recursion_limit` is
hit, discarding every message** (verified). A naïve swap would silently break G32's salvage.

## Goals
- [ ] Investigators run on `create_agent`, with no deprecation warning.
- [ ] The G32 behavior (wrap-up notice → salvage → partial flag) is preserved, now without depending on upstream strings.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Other middleware (retry, summarization, PII) | Not requested; can be added later on the same middleware list. |
| Changing the `[dev]`/core version floors (rest of G40) | Separate. |

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Budget mechanism | Own `AgentMiddleware`: counts model calls via `AIMessage`s in history; `wrap_model_call` adds the notice; `before_model` ends with **our** marker (`jump_to="end"`) | `create_agent` raises on `recursion_limit` (messages lost); own marker removes the upstream-string dependency (`ModelCallLimitMiddleware` injects its own English text). Prototype verified. | pending approval |
| Budget unit | `max_model_calls = max(2, AUDITOR_MAX_INVESTIGATOR_STEPS // 2)` (80 → 40, same ≈ tool calls as before) | User previously chose to keep the variable name/semantics "≈ 2 steps per tool call". | y |
| Notice window | last 2 model calls of the budget (revises G32 BUD-01 `remaining_steps ≤ 5`, which ≈ the same window) | `remaining_steps` doesn't exist in `create_agent`. | pending approval |
| Safety net | `recursion_limit = 4 × max_model_calls + 10` | Each loop is model + tools + middleware nodes; never reached before our stop (asserted). | y (agent) |
| AD-001 | `create_agent(..., checkpointer=False)` | Same decision, same API. | y |

**Open questions:** none.

## User Stories

### P1: Investigators on create_agent ⭐ MVP
1. **MIG-01** WHEN an investigator runs THEN it SHALL be built with `langchain.agents.create_agent` and SHALL NOT emit `LangGraphDeprecatedSinceV10`.
2. **MIG-02** WHEN it runs inside a checkpointed parent graph THEN no sub-graph checkpoints SHALL be written (AD-001; existing SUB-01 test must keep passing).
3. **MIG-03** WHEN the investigator always requests tools THEN it SHALL make exactly `max_model_calls` model calls, SHALL NOT raise `GraphRecursionError`, and all tool results SHALL be in the returned history.

### P1: G32 behavior preserved (revised BUD-01)
1. **BUD-01r** WHEN a model call is one of the last 2 of the budget THEN its input SHALL end with `WRAP_UP_NOTICE`; earlier calls SHALL NOT contain it; the investigator system prompt SHALL be the first message of every call.
2. **BUD-02..07, EDGE-01..02** (from `investigator-budget`) SHALL keep holding; exhaustion is detected by our own marker (`BUDGET_EXHAUSTED_MARKER`), which SHALL NOT appear in the salvage transcript.

## Requirement Traceability

| ID | Task | Status |
| -- | ---- | ------ |
| MIG-01..03, BUD-01r, BUD-02..07, EDGE-01..02 | T1 | Verified |
| — (docs) | T2 | Verified |

## Success Criteria
- [ ] Full suite green with zero `LangGraphDeprecatedSinceV10` warnings; `make ci` green.
