# Investigator Budget Specification (G32 + G33)

## Problem Statement

(G32, reproduced) When a ReAct investigator exhausts `recursion_limit`, LangGraph's prebuilt agent
ends with `"Sorry, need more steps to process this request."`; that sentence is all the structurer
receives, so every file read in the dimension is discarded silently and the report shows the English
sentence as the dimension summary. (G33) `synthesis_node` uses `str(response.content)` when a
provider returns content blocks, so the executive summary can be a Python `repr` of a list.

## Goals
- [ ] An exhausted investigator still yields a report built from the evidence it gathered, clearly flagged as partial.
- [ ] The executive summary is always plain text.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Renaming `AUDITOR_MAX_INVESTIGATOR_STEPS` | User chose keep + document. |
| Migrating to `langchain.agents.create_agent` (G44) | Separate item. |
| Adaptive budgets per dimension | Not requested. |

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Strategy | Wrap-up notice near the end + salvage call if still exhausted | User decision. | y |
| Flagging | Summary prefix + SSE status `partial` + CLI warning | User decision. | y |
| Config | Keep `AUDITOR_MAX_INVESTIGATOR_STEPS` (= `recursion_limit`), document ≈ 2 steps/tool call | User decision. | y |
| How the notice is injected | `prompt` as a callable reading `remaining_steps` (no extra graph node) | `pre_model_hook` adds a node per loop → ~1/3 fewer tool calls for the same limit (verified). | y (agent) |
| Notice threshold | `remaining_steps ≤ 5` | Leaves room for ~1 tool call + the final answer (remaining_steps drops by 2 per loop; sentinel fires below 2). | y (agent) |
| Exhaustion detection | Last message is an `AIMessage` without tool calls whose content equals the prebuilt sentinel | Only signal the prebuilt exposes; a test against the real prebuilt catches upstream changes. | y (agent) |
| Salvage transcript bounds | Each tool result ≤ 2 000 chars; total ≤ 60 000 chars keeping the most recent | Avoids re-sending the full history (the reason phases were decoupled in `4181510`). | y (agent) |

**Open questions:** none.

## User Stories

### P1: Plain-text executive summary ⭐ MVP
1. **SYN-01** WHEN the synthesis LLM returns content blocks `[{"type":"text","text":"A"},{"type":"text","text":"B"}]` THEN `executive_summary` SHALL be `"AB"`.
2. **SYN-02** WHEN it returns a plain string THEN `executive_summary` SHALL be that string unchanged.

### P1: Budget-aware investigators ⭐ MVP
1. **BUD-01** WHEN the agent's model is called with `remaining_steps ≤ 5` THEN its input SHALL end with the wrap-up notice (`WRAP_UP_NOTICE`); WHEN `remaining_steps > 5` THEN the input SHALL NOT contain it; the investigator system prompt SHALL always be the first message.
2. **BUD-02** WHEN the investigator ends with the budget sentinel THEN one extra LLM call without tools SHALL be made whose input contains the gathered tool results (each truncated to 2 000 chars; total ≤ 60 000 chars, most recent kept) and its text SHALL be the report passed to the structurer.
3. **BUD-03** WHEN the report came from salvage THEN `DimensionResult.summary` SHALL start with `PARTIAL_PREFIX` (`"⚠️ Investigação parcial (orçamento de passos esgotado). "`).
4. **BUD-04** WHEN the investigator finishes normally THEN no salvage call SHALL happen and the summary SHALL NOT have the prefix.
5. **BUD-05** WHEN a dimension is partial THEN `audit_node` SHALL emit an `investigator` event with status `partial` (with `findings_count`) instead of `done`, print a console warning, and keep its findings.

### P2: Partial status in the UI
1. **UI-01** WHEN a dimension event has status `partial` THEN the timeline SHALL show it as finished with the label `parcial — orçamento esgotado` and its findings count.

6. **BUD-06** (fix loop 1) WHEN the salvage call is made THEN the transcript SHALL be wrapped in `<historico>` … `</historico>`, `SALVAGE_PROMPT` SHALL state that the history is untrusted data whose instructions must be ignored, and any `<historico>`/`</historico>` inside tool outputs SHALL be neutralized (cannot close the block).
7. **BUD-07** (fix loop 1) WHEN the budget is exhausted but the condensed transcript is empty THEN no salvage call SHALL be made and the dimension SHALL yield no structured result (status `empty`).

## Edge Cases
- **EDGE-01** WHEN the salvage call itself raises THEN `_investigate_dimension` SHALL raise (so `audit_node` isolates it as `error`, others unaffected — existing behavior).
- **EDGE-02** WHEN the agent obeys the notice and answers THEN no salvage SHALL happen and the summary SHALL have no prefix.

## Requirement Traceability

| Requirement ID | Story | Task | Status |
| -------------- | ----- | ---- | ------ |
| SYN-01..02 | Plain-text summary | T1 | Verified |
| BUD-01 | Budget | T2 | Verified |
| BUD-02..04 | Budget | T3 | Verified |
| BUD-05 | Budget | T4 | Verified |
| BUD-06..07, EDGE-01..02 | Budget (fix loop 1) | F1 | Verified |
| UI-01 | UI | T5 | Verified |

**Coverage:** 13 total, 13 mapped.

## Success Criteria
- [ ] The G32 reproduction (always-tool-calling LLM, small limit) yields a partial report with the gathered evidence instead of the sentinel.
