# Audit Retention Specification

## Problem Statement

API audits are kept forever in `~/.config/auditor/` (metadata, graph checkpoints — which contain
excerpts of the audited code — and the report files). There is no way to delete an audit (G28).
Older audits also carry ReAct sub-agent checkpoints (≈ 850 MB in the current DB, G29). New audits
no longer produce them only **by accident** (the thread pool drops the context that propagates the
parent checkpointer); nothing guarantees it.

## Goals

- [ ] The user can delete any finished/orphaned audit, removing metadata, checkpoints and reports.
- [ ] Sub-agent checkpoints are never written, by design (not by accident).
- [ ] The existing bloated DB can be compacted without losing any audit.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Automatic expiry (TTL) | User chose manual deletion only. |
| Cancelling a running audit | User chose 409 for live audits; cancellation is a separate feature. |
| Reconciling/resuming orphaned audits after restart (G31) | Separate gap; here orphans only become deletable. |
| CLI `auditor audit` reports (no metadata DB) | CLI audits are not tracked; files are the user's. |
| Bulk delete | Not requested. |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Retention policy | Manual deletion only (API + history UI) | User decision. | y |
| What a delete removes | Metadata + all checkpoints/writes of the thread + the audit's `.md/.html/.sarif` reports | User decision; reports contain code excerpts. | y |
| Deleting a live audit | `409`, nothing removed | User decision. | y |
| Legacy DB | `auditor db compact` CLI command (subgraph checkpoints + VACUUM) | User decision. | y |
| "Live" audit | Has a runner in this process's registry whose `done` is not set; `running`/`waiting_input` rows without a live runner are **orphans** and deletable | Registry is in-memory; after restart nothing can resume them (G31). | y (agent) |
| Deletion order | report files → checkpoints → metadata | A failure leaves the metadata row, so the user can retry; never orphans files. | y (agent) |
| Which files may be deleted | Only the 3 report paths recorded for that audit, and only if suffix ∈ {`.md`,`.html`,`.sarif`} | Defense in depth against a tampered metadata DB deleting arbitrary files. | y (agent) |
| UI confirmation | Two-step inline button (no native `confirm()` dialog) | Accessible, testable, no blocking dialog. | y (agent) |
| Compaction while the API runs | Not supported: on lock, exit 1 with a message to stop the API | VACUUM needs exclusive access. | y (agent) |

**Open questions:** none.

---

## User Stories

### P1: Sub-agents never checkpoint ⭐ MVP

1. **SUB-01** WHEN an investigator (`_investigate_dimension`) runs inside a graph node that has a
   checkpointer, on the same thread/context THEN no checkpoint or write with a non-empty
   `checkpoint_ns` SHALL be stored for that thread.

**Independent Test**: run the investigator with a fake LLM inside a parent graph compiled with a
checkpointer; inspect the saver.

### P1: Delete an audit ⭐ MVP

1. **RET-01** WHEN `DELETE /audits/{id}` targets an audit with status `completed` or `error` and no
   live runner THEN the API SHALL respond `204`, and afterwards: `GET /audits/{id}` → `404`; the id
   is absent from `GET /audits`; the checkpointer holds no checkpoints/writes for that thread; the
   recorded `.md`, `.html` and `.sarif` files no longer exist.
2. **RET-02** WHEN the id does not exist THEN the API SHALL respond `404`.
3. **RET-03** WHEN the audit has a live runner (in registry, `done` not set) THEN the API SHALL
   respond `409` and SHALL NOT remove metadata, checkpoints or files.
4. **RET-04** WHEN the audit's status is `running`/`waiting_input` but there is no live runner
   (orphan) THEN it SHALL be deleted as in RET-01 (`204`).
5. **RET-05** WHEN a finished runner for the audit is still in the registry THEN it SHALL be removed
   (`GET /audits/{id}/stream` → `404` after deletion).

### P1: Compact the checkpoint DB ⭐ MVP

1. **CMP-01** WHEN `compact_checkpoints(db)` runs THEN every row with `checkpoint_ns != ''` in
   `checkpoints` and `writes` SHALL be deleted and every row with `checkpoint_ns == ''` SHALL be kept.
2. **CMP-02** WHEN compaction finishes THEN it SHALL return the number of removed checkpoints, removed
   writes, and the file size before and after; WHEN rows were removed THEN size after SHALL be
   strictly smaller than before (space is actually reclaimed — VACUUM).
3. **CMP-03** WHEN a thread had subgraph checkpoints THEN after compaction `graph.get_state(thread)`
   SHALL return the same `values` as before.
4. **CMP-04** WHEN the user runs `auditor db compact` THEN the CLI SHALL print removed counts and
   sizes and exit `0`; WHEN the DB file does not exist it SHALL print that there is nothing to
   compact and exit `0`; WHEN the DB is locked it SHALL print a message telling the user to stop the
   API and exit `1`.

### P2: Delete from the history UI

1. **UI-01** WHEN the history lists audits THEN each row SHALL show a delete control that does not
   open the audit when clicked.
2. **UI-02** WHEN the user clicks delete THEN the row SHALL ask for confirmation inline; only a
   second click on the confirm control SHALL call the delete action with the audit id.
3. **UI-03** WHEN the deletion succeeds THEN the history SHALL be refreshed; WHEN it fails (e.g.
   `409`) THEN the API's error message SHALL be displayed.

---

## Edge Cases

- **RET-06** WHEN a recorded report file is already missing THEN deletion SHALL still succeed (`204`).
- **RET-07** WHEN removing a report file fails with an `OSError` other than "not found" THEN the API
  SHALL respond `500` and SHALL keep the metadata row and checkpoints (retryable).
- **RET-08** WHEN a recorded report path has a suffix outside {`.md`,`.html`,`.sarif`} THEN that file
  SHALL NOT be deleted (the audit itself is still deleted).

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| SUB-01 | P1: Sub-agents | T1 | Verified |
| RET-01..08 | P1: Delete | T2, T3 | Verified |
| CMP-01..03 | P1: Compact | T4 | Verified |
| CMP-04 | P1: Compact | T5 | Verified |
| UI-01..02 | P2: UI | T6 | Verified |
| UI-03 | P2: UI | T7 | Verified |

**Coverage:** 17 total, 17 mapped to tasks, 0 unmapped.

## Success Criteria

- [ ] An audit deleted via the UI leaves no row, checkpoint or report behind.
- [ ] Running `auditor db compact` on the current DB keeps all 14 audits readable and frees the
      subgraph data (≈ 850 MB).
