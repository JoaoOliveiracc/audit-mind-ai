# STATE

## Decisions

### AD-001
- **Decision**: ReAct sub-agents (and any graph invoked inside a node) are compiled with `checkpointer=False`; only the top-level audit graph is checkpointed.
- **Reason**: Inherited checkpointing persisted every investigator step (≈ 60 MB/audit, ~99% of the DB) and stored code excerpts needlessly; resumption only happens at the `clarify` interrupt.
- **Trade-off**: An audit interrupted mid-`audit` node cannot resume a sub-agent halfway; the node re-runs.
- **Scope**: `src/auditor/nodes/*`, any future sub-graph.
- **Date**: 2026-11-10
- **Status**: active

### AD-002
- **Decision**: The local API answers only loopback `Host` headers (`localhost`, `127.0.0.1`, `[::1]`); any non-local exposure is explicit opt-in (`auditor serve --allow-remote` + `AUDITOR_ALLOWED_HOSTS`).
- **Reason**: The API has no authentication and can read the host filesystem; DNS rebinding bypasses CORS.
- **Trade-off**: Remote/LAN use needs two explicit settings.
- **Scope**: `src/auditor/api/*`, `auditor serve`.
- **Date**: 2026-11-10
- **Status**: active

## Handoff

- **Feature**: `.specs/features/report-chat-and-sarif/` (G42) — verified PASS after fix loop 1
- **Phase / Task**: complete — **all gaps of the 2026-11-10 analysis (G25–G47) resolved**
- **Completed**: G25–G47 across 13 features in `.specs/features/`
- **In-progress**: none
- **Next step**: user commits + pushes; optional follow-ups: tests still read the repo-root `.env` (load_dotenv from cwd); choose a coverage floor (measured 91%); real smoke run against Gemini 3 (wrap-up notice as HumanMessage, medium confidence); `_BudgetMiddleware` is sync-only (needs `awrap_model_call` if moving to `ainvoke`)
- **Blockers**: none
- **Uncommitted files**: report-chat-and-sarif (chat.py, templates, schemas, routes, frontend ChatDock/ResultsPanel/client/App + tests, tests/test_chat.py, tests/test_e2e.py, tests/fake_llm.py, docs, .specs/)
- **Branch**: develop
