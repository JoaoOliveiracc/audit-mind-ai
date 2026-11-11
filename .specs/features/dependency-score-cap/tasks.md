# Dependency Penalty Cap — Tasks (G49)

Spec: [spec.md](spec.md). Design skipped: there are no architectural decisions (the rule is pure;
storing the breakdown in the state is SCORE-06). 7 tasks fit one batch, so they run inline (no
sub-agents). After T7: `/code-review`, then the Verifier.

Gate (every task): `pytest -q` on 3.12 and 3.10 (scratchpad venv), `ruff check`, `mypy src`; T5 and T7 also `make ci`.
Tests come first in each task and assert the spec's values, not the implementation's.

| ID | Task | Files | Depends | Reqs | Verification |
| -- | ---- | ----- | ------- | ---- | ------------ |
| T1 | `DEPENDENCY_PENALTY_CAP = 40`, `DependencyPenalty(applied, uncapped, packages)`, `dependency_penalty(findings)`; `compute_health_score` uses it | `src/auditor/scoring.py`, `tests/test_scoring_cap.py` | — | SCORE-01..04 | The 7 normative examples; a generated regression comparing against the old formula for inputs without `osv` (SCORE-02); `endoflife` and LLM `dependencies` findings at full weight; missing or unknown severity = 0 |
| T2 | Prompt-injection guard test: an LLM `DimensionResult` with an extra `"source": "osv"` key → the stored finding has no `source` and keeps full weight | `tests/test_scoring_cap.py` | T1 | SCORE-05 | Runs through `audit_node`'s ingestion path (`model_validate` → `model_dump`) and then `compute_health_score` |
| T3 | `dependency_penalty_line(dp) -> str \| None` (exact text, U+2212/U+2014, cap suffix only when > 40) | `src/auditor/scoring.py`, tests | T1 | EXPL-01 (text), EXPL-02 | Exact strings for 1 high, 2 high (40, no suffix), 5 high (suffix "−100"); `None` for uncapped 0 and for absent |
| T4 | `AuditState.dependency_penalty`; `synthesis` stores it from the same call as the score; the prompt gets the line right after `Pontuação de saúde calculada` | `state.py`, `nodes/synthesis.py`, `prompts/templates.py`, tests | T3 | SCORE-06, EXPL-03 | The stored value matches the score; the prompt contains the line or is byte-identical to today when there is none |
| T5 | Outputs: MD list item after `Pontuação de saúde`; HTML under the label (autoescaped); CLI panel line; chat context line. All read `state["dependency_penalty"]`, never `findings` | `report/renderer.py`, `report.html.j2`, `cli.py`, `chat.py`, tests | T4 | EXPL-01 (placement), EXPL-02, EXPL-04, SCORE-06 (absent) | Placement per output; byte-identical MD/HTML/CLI/chat without a penalty; a G48-era state (score 0, 5 OSV high, no field) shows no line |
| T6 | E2E: `test_e2e05` asserts `health_score == 40` and the MD line `−20 pontos (1 pacote(s))` with no suffix | `tests/test_e2e.py` | T5 | E2E-06 | Passes offline |
| T7 | Docs: DOCUMENTACAO (§ Pontuação de saúde + resolved G49 row in §10.3), ARCHITECTURE §8, USAGE (vuln-scan) | docs | T5 | DOC-01 | Text describes the cap of 40, runtimes at full weight, the explanation line; `make ci` 0 |

Commits: one per task (the user runs git; commands are listed at the end).
