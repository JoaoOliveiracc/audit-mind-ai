# create_agent Migration Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement with the `tlc-spec-driven` skill (Execute flow + Critical Rules). If it cannot be activated, STOP and tell the user.

**Spec**: `.specs/features/create-agent-migration/spec.md` · **Status**: Done

## Design (inline)

Approaches considered: **(A, recommended)** own `_BudgetMiddleware` (`wrap_model_call` notice + `before_model` stop with our marker); (B) `ModelCallLimitMiddleware(exit_behavior="end")` + notice middleware — detection would depend on its English message; (C) keep `recursion_limit` as the budget — impossible: `create_agent` raises `GraphRecursionError` and loses the history.

- `nodes/audit.py`: `create_agent(llm, tools=tools, system_prompt=<investigator prompt>, middleware=[_BudgetMiddleware(max_calls)], checkpointer=False)`; `invoke(..., config={"recursion_limit": 4*max_calls+10})`.
- `_BudgetMiddleware(AgentMiddleware)`: `_model_calls(messages) = count(AIMessage)`; `before_model` (`@hook_config(can_jump_to=["end"])`): if calls ≥ max → `{"messages":[AIMessage(BUDGET_EXHAUSTED_MARKER)], "jump_to":"end"}`; `wrap_model_call`: if `max - calls ≤ _WRAP_UP_CALLS (2)` → `request.override(messages=[*request.messages, HumanMessage(WRAP_UP_NOTICE)])`.
- Remove `_make_prompt`, `_WRAP_UP_AT`, `_BUDGET_SENTINEL`; `_budget_exhausted` and `_condensed_transcript` use the marker.
- Risks: middleware API is new (langchain 1.x) — covered by tests against the real `create_agent`; `request.override` and `hook_config` verified in the installed version.

## Gate Check Commands

| Gate | Command |
| ---- | ------- |
| Quick | `.venv/bin/pytest -q -W error::DeprecationWarning:auditor` not used (other libs warn); instead `.venv/bin/pytest -q` + the MIG-01 test asserting no `LangGraphDeprecatedSinceV10` |
| Build | `make ci` |

## Task Breakdown

### T1: Migrate investigators + budget middleware
**Where**: `src/auditor/nodes/audit.py`, `tests/test_audit.py` · **Req**: MIG-01..03, BUD-01r, BUD-02..07, EDGE-01..02
**Tests changed by spec revision (BUD-01r)**: `test_wrap_up_notice_only_when_few_steps_remain` (expected pattern for a 12-step budget: 6 calls, notice on the last 2 → `[F,F,F,F,T,T]` instead of `[F,F,F,T,T,T]`); `_TinyBudget` (BUD-07) budget expressed via the new unit. No assertion weakened.
**New tests**: MIG-01 (no deprecation warning), MIG-03 (exact call count, no `GraphRecursionError`, all tool results kept), marker never in transcript.
**Gate**: build (`make ci`) · **Commit**: `refactor(audit): migrate investigators to create_agent with a step-budget middleware (G44)`

### T2: Docs — ARCHITECTURE §5, AGENT_DESIGN, DOCUMENTACAO (G44 ✅), USAGE · **Commit**: `docs: document create_agent migration (G44)`

## Execution notes

- **Test changes (spec revision, approved):** BUD-01r pattern `[F,F,F,F,T,T]`; the salvage test now asserts our marker is absent and that all 6 tool results reach the transcript (MIG-03); BUD-07 is exercised at `_salvage_report` level because with `create_agent` the budget only ends after ≥ 1 tool call (the empty-transcript case can no longer arise through the agent — the guard remains).
- **Required by the migration:** dependency floors raised to the tested versions (`langgraph>=1.2`, `langchain>=1.3`, `langchain-core>=1.4`) in `pyproject.toml` and `requirements.txt`; agent input uses `HumanMessage` (typed `InputAgentState`).
- **Verified:** 126 pytest on Python 3.12 (langchain 1.3.11/langgraph 1.2.7) and on Python 3.10 (langchain 1.4.9/langgraph 1.2.20); mypy 0; `make ci` green; `LangGraphDeprecatedSinceV10` warnings 8 → 0.
