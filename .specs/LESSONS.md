# LESSONS — auto-maintained by scripts/lessons.py

> Machine-owned. Do NOT hand-edit. Changes are overwritten on the next `lessons.py` write.
> Canonical state lives in `.specs/lessons.json`. Edit lessons only via the script.
> promote_threshold=2 distinct features · window_days=45 · quarantine_threshold=2

## Confirmed (load these at Specify/Design)

Corroborated across multiple features. Safe to apply as guidance.

_none_

## Candidates (under observation — do NOT load as guidance yet)

Seen once or not yet corroborated. Tracked, not trusted.

### L-001 — When a spec says every status variant appends a suffix, test the suffix on each variant, including the error/incomplete branch
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `report` · harmful: 0
- features: vuln-scan
- evidence: RPT-01 status.py:38 (report)
- last seen: 2026-11-10T21:51:43Z

### L-002 — When grouping records from several sources, test conflicting flags across sources (one private one public, one dev one prod) for each aggregated flag
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `vulnscan` · harmful: 0
- features: vuln-scan
- evidence: M09 scanner.py:153 (vulnscan)
- last seen: 2026-11-10T21:51:43Z

### L-003 — Assert every counter in a stats dict from the producer itself, not only from the renderer that consumes it
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `vulnscan` · harmful: 0
- features: vuln-scan
- evidence: M24 scanner.py:177 (vulnscan)
- last seen: 2026-11-10T21:51:43Z

### L-004 — Test caps and limits at exactly the limit, not only above it
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `vulnscan` · harmful: 0
- features: vuln-scan
- evidence: M10 scanner.py:155 (vulnscan)
- last seen: 2026-11-10T21:51:43Z

### L-005 — Parametrize privacy tests over every configured env var or source in the allowlist, not a subset
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `vulnscan` · harmful: 0
- features: vuln-scan
- evidence: M25 python.py:218 (vulnscan)
- last seen: 2026-11-10T21:51:43Z

### L-006 — When a component receives a server-loaded default via props, test the parent wiring with a non-default server value
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `frontend` · harmful: 0
- features: vuln-scan
- evidence: M30 App.tsx:47 (frontend)
- last seen: 2026-11-10T21:51:43Z

### L-007 — When the spec quotes user-facing wording, assert that wording or update the spec to the implemented text
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `vulnscan` · harmful: 0
- features: vuln-scan
- evidence: RT-03 runtime.py:197 (vulnscan)
- last seen: 2026-11-10T21:51:43Z

## Quarantined (failed when applied — ignore)

A confirmed lesson that recurred alongside failure. Kept for the maintainer to review.

_none_
