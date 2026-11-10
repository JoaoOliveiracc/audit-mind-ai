# Report Names & History Polish Specification (G45 + G46)

## Problem Statement

(G45) Reports are named only by a 1-second timestamp (`auditoria-AAAAMMDD-HHMMSS.*`): two audits
finishing in the same second overwrite each other's files, and deleting one (audit-retention)
removes the other's reports. (G46) In the history, opening an `interrupted` audit — or an `error`
audit from a previous process — tries to reconnect the SSE stream, gets 404 and shows "Conexão com o
servidor perdida."; and the **Retomar** button stays clickable while the request is in flight (a
double click shows a harmless 409 next to the run that started).

## Goals
- [ ] Every audit gets its own report files; no write ever overwrites an existing report.
- [ ] Opening interrupted/error audits gives a clear message instead of a broken connection; Retomar can't be double-fired.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Click-on-row = resume | User chose an explanatory message (resume stays explicit — costs tokens). |
| Renaming existing reports on disk | Old files keep their names; metadata already stores their paths. |
| Showing partial results of interrupted/error audits | Separate feature. |

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Name format | `auditoria-AAAAMMDD-HHMMSS-<id8>.{md,html,sarif}` | User decision. | y |
| `<id8>` source | graph `thread_id` (= API audit id / CLI uuid), first 8 chars after keeping only `[0-9A-Za-z]`; if absent/empty → 8 random hex | Traceable to the history; sanitizing prevents path tricks from programmatic thread ids. | y (agent) |
| No-overwrite guarantee | exclusive create (`"x"`); if any of the 3 names exists, try `-2`, `-3`, … | Defense in depth beyond the id. | y (agent) |
| Interrupted row click | message `Auditoria interrompida — use Retomar para continuar do último checkpoint.`; stays on the history | User decision. | y |
| Error audits | never reconnect; message `Auditoria falhou: <error>` (or `Auditoria falhou.` if no error text); stays on the history | User decision (include). Same behavior in-process and after restart — simpler. | y |
| In-flight Retomar | button disabled with label `Retomando…` while the request runs; handler ignores re-entry | Prevents the 409. | y (agent) |

**Open questions:** none.

## User Stories

### P1: Unique report files ⭐ MVP
1. **REP-01** WHEN reports are written for a run with `thread_id` `T` THEN the three files SHALL be named `auditoria-<YYYYMMDD-HHMMSS>-<id8(T)>.{md,html,sarif}` inside the output dir.
2. **REP-02** WHEN two different runs write in the same second THEN they SHALL produce distinct files and neither SHALL modify the other's.
3. **REP-03** WHEN a target name already exists THEN the writer SHALL NOT overwrite it and SHALL use the next free `-N` suffix for all three files.
4. **REP-04** WHEN `thread_id` is missing, empty, or has no alphanumeric chars THEN `<id8>` SHALL be 8 random hex chars; WHEN it contains other chars (e.g. `../a/b`) THEN they SHALL be dropped and the files SHALL stay inside the output dir.
5. **REP-05** `report_node` SHALL take `thread_id` from the LangGraph run config.

### P1: History opens interrupted/error audits safely ⭐ MVP
1. **HIS-01** WHEN the user opens an `interrupted` audit THEN the app SHALL NOT connect to the stream, SHALL stay on the history and SHALL show `Auditoria interrompida — use Retomar para continuar do último checkpoint.`
2. **HIS-02** WHEN the user opens an `error` audit THEN the app SHALL NOT connect to the stream, SHALL stay on the history and SHALL show `Auditoria falhou: <error>` (`Auditoria falhou.` when no error text).
3. **HIS-03** WHEN a resume request is in flight THEN that audit's Retomar button SHALL be disabled and labeled `Retomando…`, and further clicks SHALL NOT send another request.

## Requirement Traceability

| ID | Task | Status |
| -- | ---- | ------ |
| REP-01..04 | T1 | Verified |
| REP-05 | T2 | Verified |
| HIS-01..03 | T3 | Verified |
| — docs | T4 | Verified |

**Coverage:** 8 total, 8 mapped.
