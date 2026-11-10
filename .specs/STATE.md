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

### AD-003
- **Decision**: Outbound network calls are opt-in per run and limited to a fixed allowlist of HTTPS hosts (today: `api.osv.dev`, `endoflife.date`); only public package coordinates (ecosystem, name, version) may leave the process — never code, file paths or private package names.
- **Reason**: The auditor handles untrusted, often proprietary code; users running local LLMs expect zero egress.
- **Trade-off**: Vulnerability scanning is off unless the user enables it.
- **Scope**: `src/auditor/vulnscan/*`, any future external integration.
- **Date**: 2026-11-10
- **Status**: active

## Handoff

- **Feature**: `.specs/features/vuln-scan/` (G48)
- **Phase / Task**: Phase 1 (T1–T5) **done** + `/code-review` fixes applied; Phase 2 not started (user runs phases on request; `/code-review` at the end of each phase)
- **Completed**: T1 models/versions/severity · T2 npm parsers + registry config · T3 composer · T4 Python parsers · T5 runtime detection/classification · 10 code-review fixes
- **In-progress**: none
- **Next step**: on the user's go-ahead, Phase 2 — T6 `OSVClient` (tests first, httpx MockTransport)
- **Blockers**: none
- **Uncommitted files**: `src/auditor/vulnscan/` (models, versions, severity, runtime, lockfiles/{__init__,registry_config,npm,composer,python}), `tests/vulnscan/` (6 files), `pyproject.toml` (core deps + `types-PyYAML`), `.specs/features/vuln-scan/`, `.specs/STATE.md`
- **Branch**: develop
