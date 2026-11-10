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

- **Feature**: `.specs/features/api-hardening/` — verified PASS after fix loop 1 (previous: `search-code-scoping`, `audit-retention`, both verified)
- **Phase / Task**: all three features complete
- **Completed**: search-code-scoping (G25/G26/G30), audit-retention (G28/G29), api-hardening (G27/G31)
- **In-progress**: none
- **Next step**: user commits; next backlog per DOCUMENTACAO.md §10.3 — (4) G32+G33, then G44 (create_agent migration), G37/G38 (CI, mypy)
- **Blockers**: none
- **Uncommitted files**: all three features (code, tests, docs, .specs/) — user runs git
- **Branch**: develop
