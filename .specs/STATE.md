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

- **Feature**: `.specs/features/provider-extras/` (G47) — verified PASS
- **Phase / Task**: complete
- **Completed**: G25–G41, G44–G47 (all of the 2026-11-10 analysis except G42)
- **In-progress**: none
- **Next step**: user commits; remaining: G42 (frontend SARIF download, ChatDock — needs product decisions); optional: tests read repo-root `.env`; coverage floor (measured 91%)
- **Blockers**: none
- **Uncommitted files**: provider-extras (pyproject.toml, tests/test_ci_config.py, README.md, docs/USAGE.md, DOCUMENTACAO.md, .specs/)
- **Branch**: develop
