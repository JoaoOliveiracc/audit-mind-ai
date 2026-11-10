# STATE

## Decisions

### AD-001
- **Decision**: ReAct sub-agents (and any graph invoked inside a node) are compiled with `checkpointer=False`; only the top-level audit graph is checkpointed.
- **Reason**: Inherited checkpointing persisted every investigator step (≈ 60 MB/audit, ~99% of the DB) and stored code excerpts needlessly; resumption only happens at the `clarify` interrupt.
- **Trade-off**: An audit interrupted mid-`audit` node cannot resume a sub-agent halfway; the node re-runs.
- **Scope**: `src/auditor/nodes/*`, any future sub-graph.
- **Date**: 2026-11-10
- **Status**: active

## Handoff

- **Feature**: `.specs/features/audit-retention/` (previous: `search-code-scoping`, verified)
- **Phase / Task**: Execute done (T1–T8); fix loop 1 (race in delete_audit + CMP-02 tightened) under re-verification
- **Completed**: T1–T8, fix loop 1 implemented
- **In-progress**: none
- **Next step**: user commits both features; next backlog item per DOCUMENTACAO.md §10.3 (G31+G27)
- **Blockers**: none
- **Uncommitted files**: both features (code, tests, docs, .specs/) — user runs git
- **Branch**: develop
