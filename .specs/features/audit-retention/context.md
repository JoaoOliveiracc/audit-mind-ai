# Audit Retention Context

**Gathered:** 2026-11-10
**Spec:** `.specs/features/audit-retention/spec.md`
**Status:** Ready for design

## Feature Boundary

Manual deletion of API audits (API + history UI), a CLI to compact the legacy checkpoint DB, and an
explicit opt-out of sub-agent checkpointing (G28/G29).

## Implementation Decisions

### Retention
- Manual deletion only; nothing expires automatically.

### Deletion scope
- Removes metadata, every checkpoint/write of the thread, and the audit's `.md/.html/.sarif` reports.

### Legacy database
- New `auditor db compact`: deletes subgraph checkpoints (`checkpoint_ns != ''`) + `VACUUM`; keeps
  every audit. Run with the API stopped.

### Live audits
- Deleting a running/awaiting audit returns `409`.

### Agent's Discretion
- Orphan definition, deletion order, report-path suffix guard, inline two-step confirmation in the UI,
  lock handling in the CLI (see spec assumptions).

### Declined / Undiscussed Gray Areas → Assumptions
- None — all four gray areas were answered.

## Specific References

No specific requirements — open to standard approaches.

## Deferred Ideas

- Automatic expiry (`AUDITOR_RETENTION_DAYS`) — option offered, not chosen.
- Cancelling running audits; reconcile/resume orphans after restart (G31).
