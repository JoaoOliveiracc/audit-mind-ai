# API Hardening Specification (G31 + G27)

## Problem Statement

(G31) Audits whose process dies (API restart, `--reload`) stay `running`/`waiting_input` forever:
the in-memory registry is lost, the UI tries to reconnect and gets 404 — although the persistent
checkpointer holds everything needed to continue. (G27) The local API trusts any `Host` header, so
a malicious web page can use DNS rebinding to list host directories, start audits (sending code to
the LLM provider) and read reports; nothing stops it from being bound to a public interface either.

## Goals

- [ ] No audit stays in a non-terminal state after a restart; the user can resume it on demand.
- [ ] Requests with a non-local `Host` are rejected; binding to a non-local interface requires an explicit opt-in.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Automatic resume at startup | User chose on-demand resume (no unexpected token spend). |
| Local auth token | User chose Host allowlist only. |
| Resuming `error` audits | Different failure class (provider errors); deferred. |
| Cancelling running audits | Separate feature. |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Orphan handling | Mark `interrupted` at API startup; `POST /audits/{id}/resume` + "Retomar" button | User decision. | y |
| DNS-rebinding defense | `Host` allowlist (`localhost`, `127.0.0.1`, `[::1]`) + `AUDITOR_ALLOWED_HOSTS` extras | User decision. | y |
| Non-local bind | Refused unless `--allow-remote`; with it, a visible warning | User decision. | y |
| How resume decides what to do | From the checkpoint: pending interrupt → re-ask questions; pending nodes → continue (`stream(None)`); nothing pending → finalize metadata | State-driven; no extra column needed. | y (agent) |
| Which statuses are resumable | Only `interrupted` | Keeps the transition table small (`interrupted → running/waiting_input`). | y (agent) |
| Rejected-host response | `400` plain text `Host não permitido.` | Same status Starlette uses for invalid hosts. | y (agent) |
| Own middleware vs Starlette's | Own ASGI middleware | Starlette's parser breaks on IPv6 (`[::1]:8020` → `[`; verified in source). | y (agent) |
| Existing API tests | `TestClient(app, base_url="http://localhost")` | `testserver` is (correctly) not an allowed host; no assertion changes. | y (agent) |
| Local bind names | `127.0.0.1`, `localhost`, `::1` | Loopback only. | y (agent) |

**Open questions:** none.

---

## User Stories

### P1: Host allowlist ⭐ MVP
1. **HOST-01** WHEN a request's `Host` is `localhost`, `127.0.0.1` or `[::1]` (with or without port, any case) THEN it SHALL be served normally.
2. **HOST-02** WHEN `Host` is anything else (e.g. `evil.example`, `evil.example:8020`) THEN the API SHALL respond `400` with body `Host não permitido.` and SHALL NOT execute the route (e.g. no audit created).
3. **HOST-03** WHEN the `Host` header is missing or empty THEN the API SHALL respond `400`.
4. **HOST-04** WHEN `AUDITOR_ALLOWED_HOSTS="a.local, B.local"` THEN `a.local` and `b.local` SHALL also be allowed, in addition to the defaults.

### P1: Non-local bind guard ⭐ MVP
1. **BIND-01** WHEN `auditor serve` runs with `--host` `127.0.0.1`, `localhost` or `::1` THEN the server SHALL start as before.
2. **BIND-02** WHEN `--host` is any other value and `--allow-remote` is absent THEN the CLI SHALL exit with code `2`, print a message mentioning `--allow-remote`, and SHALL NOT start the server.
3. **BIND-03** WHEN `--allow-remote` is given with a non-local host THEN the CLI SHALL print a warning that the API has no authentication and that clients need `AUDITOR_ALLOWED_HOSTS`, and SHALL start the server.

### P1: Orphan reconciliation ⭐ MVP
1. **ORPH-01** WHEN the API starts THEN every audit with status `started`, `running` or `waiting_input` SHALL be set to `interrupted`; `completed`/`error` SHALL be unchanged.

### P1: Resume on demand ⭐ MVP
1. **RES-01** WHEN an `interrupted` audit's checkpoint has a pending clarification interrupt THEN the resumed runner SHALL emit a `clarification` event with the same questions, set status `waiting_input`, and after answers continue to completion (`completed`).
2. **RES-02** WHEN the checkpoint has pending nodes and no interrupt THEN the runner SHALL continue from the last checkpoint (`stream(None)`) and finish with status `completed`.
3. **RES-03** WHEN the checkpoint has nothing pending THEN the runner SHALL finish with status `completed` and the report paths/health score from the state, without running nodes.
4. **RES-04** WHEN `POST /audits/{id}/resume` targets an `interrupted` audit THEN the API SHALL respond `200` with the summary (status `running`) and the audit's stream SHALL be available.
5. **RES-05** WHEN the id does not exist THEN `404`.
6. **RES-06** WHEN the audit is not `interrupted` (e.g. `completed`, `error`, or has a live runner) THEN `409`.
7. **RES-07** WHEN the audit's provider/model cannot be initialized (`LLMConfigError`) THEN `400` and the status SHALL remain `interrupted`.

### P2: Resume from the history UI
1. **UI-01** WHEN an audit is `interrupted` THEN the history SHALL label it `interrompida` and show a `Retomar` button; other statuses SHALL NOT show it.
2. **UI-02** WHEN `Retomar` is clicked THEN `onResume(audit)` SHALL be called and `onOpen` SHALL NOT.
3. **UI-03** WHEN resume succeeds THEN the app SHALL switch to the live run view connected to the audit's stream; WHEN it fails THEN the API error SHALL be displayed.

## Edge Cases
- Covered inside the ACs: IPv6 with port (HOST-01), port on rejected hosts (HOST-02), missing Host (HOST-03), live runner on resume (RES-06).

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| HOST-01..04 | Host allowlist | T1 | Verified |
| BIND-01..03 | Bind guard | T2 | Verified |
| ORPH-01 | Reconciliation | T3 | Verified |
| RES-01..03 | Resume (runner) | T4 | Verified |
| RES-04..07 | Resume (route) | T5 | Verified |
| UI-01..03 | UI | T6 | Verified |

**Coverage:** 18 total, 18 mapped, 0 unmapped.

## Success Criteria
- [ ] After killing the API mid-audit and restarting, the audit shows `interrompida` and `Retomar` finishes it.
- [ ] `curl -H 'Host: evil.example' http://127.0.0.1:8020/fs/browse` → `400`.
