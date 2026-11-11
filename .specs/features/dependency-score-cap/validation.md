# Validation — Dependency Penalty Cap (G49)

**Verdict: PASS** — 12/12 ACs covered by discriminating evidence; 17/18 injected faults killed
(the survivor is an equivalent mutant for every reachable input). No blocking gaps.

- **Diff range:** working tree on top of HEAD `c9538fa` (uncommitted: 15 modified files + untracked
  `tests/test_scoring_cap.py`).
- **Verifier:** independent (author ≠ verifier), 2026-11-10.
- **Gates:** `pytest -q` 550 passed (3.12) / 550 passed (3.10 scratch venv); `ruff check src tests`
  clean; `mypy src` clean (54 files). `tests/test_scoring_cap.py`: 32 tests.
- **Restoration:** every mutant was applied to the real file and restored byte-for-byte; md5 of all
  touched files checked after the run (all OK); `git diff --stat` unchanged (15 files, +119/−26).

## Per-AC evidence

Expected values derived independently from the spec (weights 40/20/8/3/0; cap 40).

| AC | Expected (from spec) | Evidence (tests) | Status |
| -- | -------------------- | ---------------- | ------ |
| SCORE-01 | 7 normative examples: 60, 80, 60, 60, 20, 40, 100; missing/unknown severity = 0 | `test_score01_normative_examples[5high,1high,2high-boundary,crit+3high,llmcrit+5high,mixed,6info]` (values match the spec exactly); `test_score01_missing_or_unknown_severity_weighs_zero`; `test_edge_floor_when_non_osv_alone_zeroes` | ✅ |
| SCORE-02 | Without OSV → old formula for generated mixed inputs | `test_score02_regression_without_osv_generated` (500 seeded random lists, incl. `endoflife`, `None`, `"bogus"`, compares against the old formula written inline); plus the unchanged pre-existing scoring/E2E tests; plus verifier's byte-identity check (below) | ✅ |
| SCORE-03 | `endoflife` and LLM (incl. `dependencies` dimension) at full weight | `test_score03_runtime_and_llm_dependencies_keep_full_weight` (5 eol high → 0; 5 LLM `dependencies` high → 0; 5 OSV + 2 eol high → 20); normative `mixed` → 40; E2E-06 | ✅ |
| SCORE-04 | `dependency_penalty → DependencyPenalty(applied, uncapped, packages)`, packages = OSV w>0, `DEPENDENCY_PENALTY_CAP = 40`, used by `compute_health_score` | `test_score04_cap_constant_and_breakdown` ((40,100,5) with 3 OSV info excluded from N); `test_review_score_and_breakdown_from_one_computation`; `test_review_scanner_source_tag_is_the_capped_group` | ✅ |
| SCORE-05 | Extra `"source":"osv"` in LLM output → stored finding has no `source`, full weight | `test_score05_llm_cannot_join_capped_group` (5 high → score 0, uncapped 0, no `source` key). Killed M11 (adding `source` to `Finding`). | ✅ (see gap 2) |
| SCORE-06 | synthesis stores `{"applied","uncapped","packages"}` from the same call; explanations read it; absent → no line, stored score unchanged | `test_score06_synthesis_stores_breakdown_and_prompt_line` (52, {40,100,5}); `test_score06_pre_g49_state_never_recomputes` (G48-era state score 0 + 5 OSV high, no field → no line in MD/HTML/chat/CLI, `0/100` kept); `test_review_suffix_comes_from_stored_value_not_current_constant`; E2E `dependency_penalty == {20,20,1}` | ✅ |
| EXPL-01 | Exact text with U+2212/U+2014; suffix only when applied < uncapped; placement MD / HTML / CLI | `test_expl01_line_text` (1 high, 2 high = 40 no suffix, 5 high with `— teto de 40 aplicado; sem teto seriam −100`); `test_expl01_markdown_placement` (next list item after `- **Pontuação de saúde:** 60/100`); `test_expl01_html_placement_under_label`; `test_expl01_cli_panel_line` | ✅ |
| EXPL-02 | uncapped 0 or absent → no line; outputs byte-identical to today | `test_expl02_no_line_without_penalty` (None, zero, {}); `test_expl02_outputs_identical_without_penalty` (MD/HTML/chat/CLI equal for absent vs zero); `test_expl02_html_only_adds_the_line`; `test_expl03_prompt_unchanged_without_penalty`. **Verifier extra:** rendered MD, HTML, chat context, CLI summary, synthesis prompt and score from HEAD `c9538fa` (`git archive`) vs working tree for a state with LLM high + eol medium + OSV info → **byte-identical** | ✅ |
| EXPL-03 | Prompt line right after `Pontuação de saúde calculada: …` (or nothing) | `test_score06_synthesis_stores_breakdown_and_prompt_line` (line i+1); `test_expl03_prompt_unchanged_without_penalty` (i+1 blank, as before) | ✅ |
| EXPL-04 | Chat context line right after `Pontuação de saúde: …` | `test_expl04_chat_context_line`; absent/zero cases in EXPL-02 and SCORE-06 tests | ✅ |
| E2E-06 | `test_e2e05` asserts `health_score == 40` and MD line `−20 pontos (1 pacote(s))` without suffix | `tests/test_e2e.py::test_e2e05_vuln_scan_end_to_end` (score 40, breakdown {20,20,1}, exact MD list line incl. trailing `\n`, `"teto de 40" not in md`) | ✅ |
| DOC-01 | DOCUMENTACAO § Pontuação de saúde, ARCHITECTURE §8, USAGE vuln-scan describe the cap; §10.3 resolved G49 row | Manual review of the diff: formula + cap 40 + runtimes/LLM full weight + explanation line in all three docs; G49 ✅ row in §10.3 and G25–G49 headers updated. (Docs: no automated test — manual evidence only, as is usual for DOC ACs.) | ✅ |

## Discrimination sensor (fault injection)

Each fault applied alone to the real source file, full `pytest -q -x tests/` run, file restored.

| # | Injected fault | Result | Killed by |
| - | -------------- | ------ | --------- |
| M1 | Cap also applied to `endoflife` | KILLED | `test_e2e05_vuln_scan_end_to_end` (and SCORE-03 tests) |
| M2 | Suffix when `uncapped >= cap` (off-by-one at sum 40, decided by constant) | KILLED | `test_expl01_line_text[2 high]` |
| M3 | `packages` counts `info` OSV findings | KILLED | `test_score04_cap_constant_and_breakdown` |
| M4 | MD/HTML line recomputed from `findings` instead of stored value | KILLED | `test_expl02_html_only_adds_the_line` |
| M5 | MD line placed after "Total de achados" | KILLED | `test_expl01_markdown_placement` |
| M6 | HTML line missing | KILLED | `test_expl01_html_placement_under_label` |
| M7 | CLI line missing | KILLED | `test_expl01_cli_panel_line` |
| M8 | Chat line missing | KILLED | `test_expl04_chat_context_line` |
| M9 | Prompt line missing | KILLED | `test_score06_synthesis_stores_breakdown_and_prompt_line` |
| M10 | synthesis does not store `dependency_penalty` | KILLED | `test_e2e05_vuln_scan_end_to_end` |
| M11 | `Finding` model gains `source` field (LLM can join capped group) | KILLED | `test_score05_llm_cannot_join_capped_group` |
| M12 | Score subtracts `uncapped` (no cap) | KILLED | `test_score01_normative_examples[5high]` |
| M13 | ASCII `-` instead of U+2212 | KILLED | `test_e2e05_vuln_scan_end_to_end` / `test_expl01_line_text` |
| M14 | HTML line rendered with `\|safe` (autoescape bypass) | **SURVIVED** | — (equivalent: line is built only from `int()` values and fixed text, so it never contains HTML metacharacters) |
| M15 | Chat recomputes from `findings` | KILLED | `test_score06_pre_g49_state_never_recomputes` |
| M16 | CLI recomputes from `findings` | KILLED | `test_score06_pre_g49_state_never_recomputes` |
| M17 | Line shows `uncapped` as the applied amount | KILLED | `test_expl01_line_text[5 high]` |
| M18 | `DEPENDENCY_PENALTY_CAP = 41` | KILLED | `test_score01_normative_examples[5high]` |

**Kill rate:** 17/18 (94%); 17/17 of the non-equivalent mutants.

## Gaps (ranked, none blocking)

1. **M14 survivor (low, equivalent today).** No test asserts that the HTML line is autoescaped.
   Harmless now because `dependency_penalty_line` coerces every value with `int()`; it would matter
   only if the line ever carried free text. Optional: a test rendering a stored value that can't
   be coerced, or asserting the template expression has no `|safe`.
2. **SCORE-05 exercises the model, not the node (low).** The test runs
   `DimensionResult.model_validate(raw) → model_dump(mode="json")`, the same steps the production
   path uses (`with_structured_output(DimensionResult)` in `nodes/audit.py:177`, then
   `finding.model_dump(mode="json")` at `audit.py:263`), but it doesn't call `audit_node`. If the
   node later stopped going through the Pydantic model (e.g. raw dict ingestion), this test would
   not catch it.
3. **Floor edge case: line not asserted (low).** The spec edge case "non-OSV ≥ 100 → score 0; the
   EXPL line still shows the group's share" is tested only for the score
   (`test_edge_floor_when_non_osv_alone_zeroes`), not for the line. The implementation shows it
   (the line only depends on the stored breakdown), but no test pins it.
4. **EXPL-02 "byte-identical to today" in the suite is relative (spec precision).** The suite
   compares absent vs zero-breakdown states on the current code, not against pre-G49 output. The
   verifier closed this once by diffing HEAD vs working-tree outputs (identical), but the suite has
   no golden. Pre-existing renderer/CLI tests passing unchanged give partial cover.
5. **Spec precision (informational).** EXPL-01 says "HTML: directly under the label"; the test
   checks that the line comes after the label and before "achado(s) no total" with no closing tag
   between the label and the opening tag of the line. That is a reasonable reading. DOC-01 has
   manual evidence only.
