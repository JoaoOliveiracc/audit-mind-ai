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

- **Feature**: `.specs/features/web-i18n/` (G50) — **Done** (T1–T8, code review 7/10 applied, Verifier PASS + fix loop 1; 132 frontend tests)
- **Previous**: G49 Done (committed); open user decisions: `.lock` in `search_code` (LOCK-05); G49 floor line (nominal vs effective)
- **Next step**: user commits G50; next feature: backend audit language (`language` → LLM prompts/output, MD/HTML reports, CLI, scan status, API errors, `NO_ANSWER`)
- **Blockers**: none
- **Branch**: feat/vuln-scan
