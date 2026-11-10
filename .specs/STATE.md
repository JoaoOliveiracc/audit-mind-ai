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

- **Feature**: `.specs/features/create-agent-migration/` (G44) — verified PASS after fix loop 1; `ci-quality-gates` also verified, both uncommitted
- **Phase / Task**: complete
- **Completed**: G25–G33, G36–G38, G44 (G40 partial)
- **In-progress**: none
- **Next step**: user commits + pushes and checks the first GitHub Actions run. Backlog (DOCUMENTACAO.md §10.3): G46, G45, G34/G35, G39, G40 rest, G41, G42, test writing ~/.config/auditor
- **Blockers**: none
- **Uncommitted files**: ci-quality-gates + create-agent-migration (shared: `src/auditor/nodes/audit.py`, `pyproject.toml`, docs)
- **Branch**: develop
