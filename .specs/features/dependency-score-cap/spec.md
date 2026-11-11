# Dependency Penalty Cap in the Health Score Specification (G49)

## Problem Statement

With the opt-in dependency scan (G48), each vulnerable `package@version` becomes its own finding
weighted like a hand-found code finding (`critical=40, high=20, medium=8, low=3, info=0`). On a
typical JavaScript project with an old lockfile, five transitive packages with HIGH advisories
already subtract 100 points, so the health score drops to 0 whatever the code quality. The score
stops reflecting the audit, and turning the scan on "punishes" the user for asking for more data.

## Goals

- [ ] Vulnerable packages still lower the score in proportion to their severity, but as a group
      they subtract **at most 40 points** (the weight of one critical finding).
- [ ] Scores of audits without OSV findings (scan disabled or clean) are **exactly** what they are
      today.
- [ ] Every place that shows or explains the score (report, CLI, executive summary, report chat)
      says how much the packages took off and whether the cap was applied.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| A separate "dependency score" | User decision: single score with a group cap. |
| Capping runtime findings (`source="endoflife"`) | User decision: few, independent risks — normal weight. |
| Capping LLM findings of the `dependencies` dimension | They are not grouped deterministic data; normal weight. |
| Changing `SEVERITY_WEIGHT` or the CLI/web score tiers (≥ 75 / ≥ 50) | Not requested. |
| Recomputing scores of audits already stored in the history | Stored audits keep the score they were finished with. |
| Configurable cap (env var) | No demand; a fixed constant keeps scores comparable across runs and machines. |
| Showing the breakdown in the web UI | Not requested; the web shows the score without explanation (the G48 status card does not explain it). The breakdown is reachable from the web through the HTML report and the report chat (EXPL-04). Candidate follow-up. |
| SARIF | Has no score. |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Aggregation rule | sum of the OSV findings' weights, capped at 40 | User decision ("Teto do grupo"). | y |
| Runtime findings | normal weight, outside the group | User decision. | y |
| Which findings form the group | exactly `source == "osv"`, a field only the scanner sets | The LLM's `Finding` schema has no `source` field and Pydantic ignores extra keys, so the audited code (prompt injection) cannot move a finding into the capped group — SCORE-05 makes this a tested guarantee. | y (agent) |
| Cap value | constant `DEPENDENCY_PENALTY_CAP = 40` in `scoring.py`, independent of `SEVERITY_WEIGHT` | Equals one critical today; a later weight change must not silently move the cap. | y (agent) |
| Severity counts | unchanged — every package still counted by its severity | Counts describe findings; only the score is capped. The EXPL line reconciles "5 Altos" with a score of 60. | y (agent) |
| Dev-only packages | already `info` (weight 0) — no special handling; not counted in N | Existing G48 rule; N counts only packages that weigh. | y (agent) |
| Unverified OSV findings (kept by `verify` with lower confidence) | count with full weight | Confidence never affected the score; out of scope to change. | y (agent) |
| Audit resumed across the upgrade | synthesis (which runs at the end) uses the new rule | The score is computed once, in `synthesis`. | y (agent) |
| Audits finished before G49 (history, report chat) | keep their stored score; **no** explanation line | Recomputing the breakdown from their findings would print "teto aplicado" next to a score computed without the cap — SCORE-06 stores the breakdown instead of recomputing it. | y (agent) |

**Open questions:** none — all resolved or logged above.

---

## User Stories

### P1: Capped dependency penalty ⭐ MVP

**User Story**: As a tech lead who enabled the dependency scan, I want vulnerable packages to lower
the health score without zeroing it, so that the score still reflects the code audit.

**Acceptance Criteria**:

1. **SCORE-01** WHEN the health score is computed THEN the system SHALL use
   `penalty = Σ weight(f) for findings with source ≠ "osv" + min(40, Σ weight(f) for findings with source == "osv")`
   and `score = max(0, 100 − min(100, penalty))` (weights from `SEVERITY_WEIGHT`; missing or
   unknown severity = 0).
2. **SCORE-02** WHEN there are no findings with `source == "osv"` THEN the score SHALL equal the
   current formula `max(0, 100 − min(100, Σ weight(f)))` for every input (regression guarantee,
   tested over a generated set of mixed inputs, not only hand-picked cases).
3. **SCORE-03** WHEN findings have `source == "endoflife"` or no `source` (LLM), including LLM
   findings of the `dependencies` dimension, THEN they SHALL keep their full weight (never capped).
4. **SCORE-04** The rule SHALL live only in `auditor.scoring`: a function
   `dependency_penalty(findings) -> DependencyPenalty(applied, uncapped, packages)` (packages =
   OSV findings with weight > 0; each OSV finding is already one distinct `name@version`, its
   occurrences across lockfiles grouped by the scanner) used by `compute_health_score`; the cap
   SHALL be the constant `DEPENDENCY_PENALTY_CAP = 40`.
5. **SCORE-05** WHEN an investigator's structured output contains a finding with an extra
   `"source": "osv"` key THEN the finding stored in the state SHALL have no `source` and SHALL keep
   its full weight.
6. **SCORE-06** WHEN `synthesis` computes the score THEN it SHALL also store
   `dependency_penalty = {"applied", "uncapped", "packages"}` in the audit state, computed from
   the same findings in the same call; every explanation (EXPL-*) SHALL read this stored value and
   never recompute it from `findings`. WHEN the state has no `dependency_penalty` (audit finished
   before G49) THEN no explanation line SHALL appear and the stored score SHALL be shown unchanged.

Examples (normative, each one a test): 5 OSV `high` → 60; 1 OSV `high` → 80; 2 OSV `high` → 60
(sum exactly 40, no cap); 1 OSV `critical` + 3 OSV `high` → 60; 1 LLM `critical` + 5 OSV `high` → 20;
1 OSV `high` + 1 `endoflife` `high` + 1 LLM `high` → 40; 6 OSV `info` (dev-only) → 100.

**Independent Test**: unit tests on `compute_health_score`/`dependency_penalty` with the examples.

---

### P1: Explainable score

**User Story**: As a reader of the report, I want to know how much the vulnerable packages took
off the score, and whether the cap was applied.

**Acceptance Criteria**:

1. **EXPL-01** WHEN the stored `uncapped > 0` THEN the explanation line SHALL be exactly
   `Pacotes vulneráveis (OSV): −<applied> pontos (<packages> pacote(s))`, and WHEN the stored
   `applied < uncapped` (i.e. `uncapped > 40` at computation time) SHALL end with
   ` — teto de <applied> aplicado; sem teto seriam −<uncapped>` (decided from the stored value, never
   from the current constant) (`−` is U+2212 MINUS SIGN
   and `—` is U+2014 EM DASH, as in the rest of the report; built by one helper in
   `auditor.scoring`, reused by every output). It SHALL appear:
   - Markdown report: as a list item right after `- **Pontuação de saúde:** …`;
   - HTML report: directly under the "Pontuação de saúde" label of the score card (autoescaped);
   - CLI summary: as a line inside the final panel right after `Pontuação de saúde: …`.
2. **EXPL-02** WHEN `uncapped == 0` or `dependency_penalty` is absent THEN no such line SHALL
   appear anywhere (reports, CLI, prompt and chat context byte-identical to today for the same state).
3. **EXPL-03** WHEN the synthesis prompt is built THEN it SHALL include the EXPL-01 line (or
   nothing, per EXPL-02) on the line right after `Pontuação de saúde calculada: …`.
4. **EXPL-04** WHEN the report chat context is built (`chat.build_report_context`) THEN it SHALL
   include the same line right after `Pontuação de saúde: …` (or nothing, per EXPL-02).

**Independent Test**: render a report/CLI summary from a state with 5 OSV `high` findings and see
`Pacotes vulneráveis (OSV): −40 pontos (5 pacote(s)) — teto de 40 aplicado; sem teto seriam −100`.

---

### P1: End-to-end and docs

1. **E2E-06** The offline e2e of G48 (`test_e2e05_vuln_scan_end_to_end`: 1 LLM `high` + 1 OSV
   `high` + 1 `endoflife` `high`) SHALL also assert `health_score == 40` and that the Markdown report
   contains `Pacotes vulneráveis (OSV): −20 pontos (1 pacote(s))` without the cap suffix.
2. **DOC-01** The health-score sections of `DOCUMENTACAO.md` (§ Pontuação de saúde), `docs/ARCHITECTURE.md`
   (§ 8 Health score) and `docs/USAGE.md` (vuln-scan section) SHALL describe the cap; `DOCUMENTACAO.md`
   §10.3 SHALL gain a resolved G49 row.

---

## Edge Cases

- WHEN all OSV findings are `info` THEN `uncapped == 0` → no EXPL line, score unaffected.
- WHEN the OSV group sum is exactly 40 THEN no cap suffix (only sums > 40 are capped).
- WHEN a finding's `severity` is missing or unknown THEN weight 0 (current behavior).
- WHEN OSV findings were rejected by `verify` THEN they are no longer in `findings` and don't count.
- WHEN the non-OSV penalty alone is ≥ 100 THEN score 0 regardless of the group (floor unchanged);
  the EXPL line still shows the group's share.
- WHEN an OSV finding has no CVSS/label THEN it is already `medium` (G48 rule, weight 8) — counted
  normally in the group.
- WHEN the report chat opens an audit finished before G49 THEN no EXPL line (SCORE-06).

Remaining implicit-requirement dimensions N/A for this scope (pure, deterministic computation; no
I/O, concurrency, auth or external calls).

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| SCORE-01 | P1: Capped penalty | Execute | Done |
| SCORE-02 | P1: Capped penalty | Execute | Done |
| SCORE-03 | P1: Capped penalty | Execute | Done |
| SCORE-04 | P1: Capped penalty | Execute | Done |
| SCORE-05 | P1: Capped penalty | Execute | Done |
| SCORE-06 | P1: Capped penalty | Execute | Done |
| EXPL-01 | P1: Explainable score | Execute | Done |
| EXPL-02 | P1: Explainable score | Execute | Done |
| EXPL-03 | P1: Explainable score | Execute | Done |
| EXPL-04 | P1: Explainable score | Execute | Done |
| E2E-06 | P1: E2E and docs | Execute | Done |
| DOC-01 | P1: E2E and docs | Execute | Done |

**Coverage:** 12 total, 12 mapped to tasks (T1–T7 in tasks.md).

---

## Success Criteria

- [ ] A project with only vulnerable packages never scores below 60 because of them.
- [ ] Every existing scoring test and the E2E scores still pass unchanged (SCORE-02).
- [ ] The score shown is always explainable from the same function that computed it (SCORE-04),
      stored once with the score (SCORE-06).

## Review log
- 2026-11-10 spec review (8 items): SCORE-05 (LLM can't join the capped group — prompt-injection
  guard); SCORE-04 single `dependency_penalty` function shared by score and explanations; EXPL-01
  exact placement per output + N counts only packages that weigh; EXPL-02 byte-identical when no
  penalty; EXPL-04 report chat context; boundary example (sum exactly 40); E2E-06; DOC-01; assumptions
  for unverified findings and resumed audits.
- 2026-11-10 spec review #2 (5 items): SCORE-06 — breakdown stored in the state by `synthesis`
  and read by every explanation (otherwise the chat of a G48-era audit would print "teto aplicado"
  beside an uncapped stored score); EXPL-01 exact characters (U+2212/U+2014) and one shared line
  builder; N = distinct `name@version` (scanner groups lockfile occurrences); EXPL-02 also covers
  absent breakdown and prompt/chat; web out-of-scope rationale corrected; edge cases (floor with
  EXPL line, OSV without CVSS = medium, pre-G49 audit in chat).
- 2026-11-10 code review (Execute): score and breakdown from one computation
  (`score_with_breakdown`); cap suffix decided from the stored value; `OSV_SOURCE` shared with the
  scanner; chat insertion simplified. Kept per spec: under the floor (non-OSV ≥ 100) the line still
  shows the group's share.
