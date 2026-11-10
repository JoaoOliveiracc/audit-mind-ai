# Vulnerable Dependencies & Runtimes (G48) Validation

**Date**: 2026-11-10
**Spec**: `.specs/features/vuln-scan/spec.md`
**Diff range**: uncommitted working tree on branch `feat/vuln-scan` on top of HEAD `a693a1f7161b4a3afdf6a721ba4003f832539db1`
**Verifier**: independent sub-agent (author ≠ verifier, evidence-or-zero)

## Verdict: ❌ FAIL (minor)

The core behavior is implemented, and most ACs have assertions that check the outcome the spec defines. The verdict is not PASS for two reasons:
- RPT-01 has a real spec deviation that no test catches.
- The sensor found 6 non-equivalent surviving mutants. One of them is on the privacy guarantee ("never sends private package names").

---

## Task Completion

T1–T12 are marked done in `tasks.md`. No task is blocked. I did not take the author's notes on trust: every claim below was re-derived from the code and tests.

---

## Spec-Anchored Acceptance Criteria

| AC | Spec-defined outcome | Evidence (`file` — assertion) | Result |
| -- | -------------------- | ----------------------------- | ------ |
| LOCK-01 | `Dependency(...)` per package; `line` = version line per format | `test_vs_npm.py::test_package_lock_v3` (`lodash.line == _line_of(... '"version": "4.17.15"' ...)`), `::test_yarn_v1`, `::test_yarn_berry_with_yarnrc_scope`, `::test_pnpm_v9` (key line); `test_vs_composer.py::test_composer_public_package_and_version_line`; `test_vs_python.py::test_poetry`/`test_uv`/`test_pipfile_lock`/`test_requirements_pins_only` (`line == 2/3`); `test_vs_review3_fixes.py::test_duplicate_package_versions_cite_own_line` | ✅ PASS |
| LOCK-02 | `dev` only for listed markers / dev requirement filenames | `test_vs_npm.py:59` (`vitest.dev is True`), `::test_pnpm_v6_dev_flag`, `test_vs_composer.py::test_composer_packages_dev_are_dev`, `test_vs_python.py` (`pytest.dev is True` for poetry `category`, uv, Pipfile), `::test_requirements_dev_filenames` (4 names) | ✅ PASS (⚠️ poetry `groups = ["dev"]` path untested) |
| LOCK-03 | per-format private rules incl. user/env registry config, pip env/pip.conf | `test_vs_npm.py` (host, git, no-resolved, `.npmrc` scope/default, `.yarnrc.yml`), `test_vs_review3_fixes.py` (user `~/.npmrc`/`~/.yarnrc.yml`, env vars, pip env ×7, pip.conf ×6, `PIP_CONFIG_FILE`, broken pip.conf ⇒ skip), composer notification-url/branch, poetry/uv/Pipfile sources, requirements index ⇒ `skipped_files == ["requirements.txt"]`; scanner `test_private_and_ignored_dirs_never_queried` | ⚠️ PARTIAL: cross-lockfile "private in any occurrence" (M09) and `UV_FIND_LINKS` (M25) untested |
| LOCK-04 | malformed ⇒ no raise, recorded as parse error | `test_vs_npm.py::test_package_lock_malformed_never_raises` (`len(errors) == 1`), pnpm, composer, python malformed; `test_vs_review3_fixes.py::test_one_crashing_parser_does_not_discard_other_results` | ✅ PASS |
| LOCK-05 | `.lock` not binary | `test_vs_integration.py::test_lock_files_are_readable_by_tools` | ✅ PASS |
| OSV-01 | chunks ≤ 500, `next_page_token`, each advisory fetched once, PEP 503 | `test_vs_osv.py::test_querybatch_chunks_of_500` (`[500,500,200]`), `::test_pagination_requests_only_paginated_queries`, `::test_each_advisory_fetched_once...` (`fetched == [id]`), `test_vs_core.py::test_normalize_name` | ✅ PASS (M04 is equivalent: every PyPI parser already normalizes) |
| OSV-02 | id, CVEs, summary, severity precedence, fixed version of the matching range | `test_vs_osv.py:94-97` (`fixed_for(d4)=="4.17.21"`, `fixed_for(d3)=="3.10.2"`), `test_vs_core.py` label > CVSS > medium+note | ✅ PASS |
| OSV-03 | only https api.osv.dev / endoflife.date, 15 s, payload e/n/v only, 5 MB cap, 10 000 cap + `truncated` | `test_vs_osv.py::test_only_https_osv_host_is_allowed`, `test_vs_eol.py::test_only_https_endoflife_host`, `::test_default_client_has_15s_timeout`, `::test_payload_has_only_ecosystem_name_version`, `::test_oversized_response_is_an_error_not_a_crash`, `test_vs_scanner.py::test_max_packages_cap` | ⚠️ PASS with boundary gap (`>` vs `>=` at exactly 10 000 untested, M10) |
| FND-01 | one finding per pkg@version across lockfiles; title, severity=max, dev→info, evidence, description, recommendation | `test_vs_scanner.py::test_one_finding_per_package_version_across_lockfiles` (exact title, `"high"`, evidence = line, other occurrence listed, `"Atualize para ≥ 4.17.21."`), `::test_recommendation_without_any_fix`, `::test_dev_only_package_is_info` | ⚠️ PARTIAL: "dev → info" only when *all* occurrences are dev is untested (M08) |
| FND-02 | verified and not judged | `test_vs_integration.py::test_verify_confirms_deterministic_finding_in_large_lockfile`, `::test_adversarial_skips_deterministic_findings`, e2e `"judged" not in osv[0]` | ✅ PASS |
| RT-01 | detection sources | `test_vs_runtime.py` (nvmrc, node-version, engines, composer, python-version, pyproject, Dockerfile variants) | ✅ PASS |
| RT-02 | cycle vs exact; cycle EOL→high; exact behind patch→medium | `test_vs_runtime.py::test_classify`, `test_vs_eol.py::test_evaluate` (exact status/severity) | ✅ PASS |
| RT-03 | range min-cycle EOL → medium, "a faixa permite runtime sem suporte" | `test_vs_eol.py::test_evaluate` (`>=16`→medium), `test_vs_review2_fixes.py::test_eol_range_title_says_unsupported` | ⚠️ Spec-precision gap: the quoted wording is never asserted (message asserted only as truthy) |
| RT-04 | unknown → no finding, recorded in stats; source/file/line/evidence | `test_vs_eol.py` (`"unknown"`), `test_vs_scanner.py::test_runtime_finding` (`("high", ".nvmrc", 1, "16")`) | ❌ GAP: the `runtime_unknown` stat is never asserted from `scan()` (M24 survived) |
| RT-05 | independent declarations | `test_vs_runtime.py::test_each_declaration_is_returned_separately` (detector level only) | ✅ PASS (weak: no scanner-level two-finding test) |
| CFG-01 | off by default; flag/request wins; disabled ⇒ no network | `test_vs_integration.py::test_setting_defaults_off_and_reads_env`, `::test_cli_flag_precedence` (4 cases), `::test_api_request_precedence` (4), `::test_disabled_node_makes_no_client_and_keeps_findings` (`boom`) | ✅ PASS |
| CFG-02 | stats keys, SSE event, report, CLI | `test_vs_scanner.py::test_stats_and_errors` (exact tuple), `test_vs_integration.py:82` (`emitted[0]["type"] == "dependency_scan"`), `test_vs_report.py` | ✅ PASS |
| UI-01 | checkbox label, sent as `vuln_scan`, initial = `GET /defaults`, user choice not overwritten, results panel status | `StartForm.test.tsx` (5 tests), `test_vs_review3_fixes.py::test_defaults_endpoint_exposes_vuln_scan_default`, `ResultsPanel.test.tsx` RPT-01 block | ⚠️ PARTIAL: wiring `App.tsx` `getDefaults → vulnScanDefault` untested (M30 survived) |
| RPT-01 | exact wording for disabled / incomplete+reasons / clean / with findings; **every enabled status** appends "(K privada(s) não consultada(s))" | `test_vs_report.py::test_status_headline` (7 exact headlines), MD/HTML/CLI tests, e2e line | ❌ FAIL: `status.py:38-39` returns the bare `INCOMPLETE` headline with no private suffix. Probe: `{'skipped_private': 2, 'errors': ['x']}` → `'Varredura de dependências incompleta'`. No test covers incomplete + K>0. |
| DUP-01 | exact note only when enabled | `test_vs_integration.py::test_investigator_prompt_note` (exact text, both states) | ✅ PASS |
| E2E-05 | 1 OSV verified/not judged, 1 runtime, `skipped_private == 1`, zero network | `tests/test_e2e.py::test_e2e05_vuln_scan_end_to_end` (socket.connect patched, private name never sent) | ✅ PASS |

**Status**: 14/21 fully verified. 1 FAIL (RPT-01). 1 GAP (RT-04 stats). 5 partial or spec-precision (LOCK-03, OSV-03, FND-01, RT-03, UI-01).

---

## Discrimination Sensor

The sensor ran at P0 depth (32 manual behavior-level mutants, because privacy and egress are critical paths). Each mutated file was backed up to scratchpad `verifier-backup/` and restored after each mutant, and its sha256 was re-checked: all 15 files matched (`sha256sum -c` SUCESSO). Harness: `scratchpad/mutants.py`, log `scratchpad/mutants.log`.

| # | File:line | Mutation | Result |
| - | --------- | -------- | ------ |
| M01 | `lockfiles/registry_config.py:53` | drop `YARN_NPM_REGISTRY_SERVER` env | ✅ Killed |
| M02 | `lockfiles/registry_config.py:58` | ignore user `~` config | ✅ Killed |
| M03 | `lockfiles/python.py:280` | no PEP 503 on requirements names | ✅ Killed |
| M04 | `sources/osv.py:26` | `dep_key` without normalization | ⚪ Survived — equivalent (all PyPI parsers normalize) |
| M05 | `sources/osv.py:49` | fixed version ignores range | ✅ Killed |
| M06 | `severity.py:64` | drop DB label precedence | ✅ Killed |
| M07 | `scanner.py:82` | severity min→max rank | ✅ Killed |
| M08 | `scanner.py:83` | dev→info when **any** occurrence is dev | ❌ Survived |
| M09 | `scanner.py:153` | private only if **all** occurrences private | ❌ Survived (privacy) |
| M10 | `scanner.py:155` | `truncated` `>` → `>=` | ❌ Survived (boundary) |
| M11 | `scanner.py:100` | drop other occurrences in description | ✅ Killed |
| M12 | `sources/__init__.py:35` | 5 MB cap → 10 MB | ✅ Killed |
| M13 | `sources/__init__.py:22` | drop https scheme check | ✅ Killed |
| M14 | `nodes/dependency_scan.py:25` | `flag or env` precedence | ✅ Killed |
| M15 | `nodes/dependency_scan.py:39` | client created before disabled check | ✅ Killed |
| M16 | `nodes/adversarial.py:39` | judge deterministic findings | ✅ Killed |
| M17 | `nodes/verify.py:83` | lockfile limit = max_file_bytes | ✅ Killed |
| M18 | `status.py:41` | wording "entre"→"de" | ✅ Killed |
| M19 | `status.py:38` | truncated not incomplete | ✅ Killed |
| M20 | `nodes/audit.py:156` | DUP-01 note always on | ✅ Killed |
| M21 | `runtime.py:203` | ranges get behind-patch check | ✅ Killed |
| M22 | `runtime.py:197` | range EOL → high | ✅ Killed |
| M23 | `runtime.py:53` | Node `20.11` classified as cycle | ✅ Killed |
| M24 | `scanner.py:177` | `runtime_unknown` never incremented | ❌ Survived |
| M25 | `lockfiles/python.py:218` | drop `UV_FIND_LINKS` | ❌ Survived (privacy) |
| M26 | `lockfiles/composer.py:44` | missing notification-url ⇒ public | ✅ Killed |
| M27 | `lockfiles/python.py:255` | unreadable pip.conf ⇒ ignored | ✅ Killed |
| M28 | `lockfiles/python.py:24` | `requirements-test*` not dev | ✅ Killed |
| M29 | `frontend/src/components/StartForm.tsx:25` | late default overwrites user choice | ✅ Killed |
| M30 | `frontend/src/App.tsx:47` | ignore `/defaults` value | ❌ Survived |
| M31 | `scanner.py:83` | never downgrade dev → info | ✅ Killed |
| M32 | `lockfiles/registry_config.py:55` | ignore `npm_config_@scope:registry` env | ✅ Killed |

**Result**: 25/32 killed. 1 survivor is equivalent and 6 are real → ❌ FAIL.

---

## Code Quality (spot-check)

| Principle | Status |
| --------- | ------ |
| Minimum code / surgical | ✅ (vulnscan is self-contained; integration edits are small) |
| Matches patterns | ✅ |
| Spec-anchored asserted values | ⚠️ RPT-01 incomplete+private and RT-03 wording are not asserted |
| Every test maps to an AC or review fix | ✅ (test docstrings cite ACs or review items) |
| Guidelines | none project-specific; strong defaults applied |

## Edge Cases

- [x] Malformed lockfiles, symlinks, oversized lockfiles, pagination cap, HTTP errors: handled and tested.
- [ ] Same package private in one lockfile and public in another: handled in code (`any`), but untested.
- [ ] Package dev in one lockfile and prod in another: handled in code (`all`), but untested.
- [ ] Exactly 10 000 public packages: untested boundary.
- [ ] VCS/URL/path requirements lines are silently ignored, not counted in `skipped_private` (spec-precision: the Decisions table says privates are "counted in stats").

## Gate Check

- `.venv/bin/pytest -q`: 509 passed (baseline 509) · `ruff`: clean · `mypy src`: clean (54 files)
- frontend `vitest run`: 53 passed (baseline 53) · `tsc --noEmit`: exit 0
- Results are identical before and after the sensor run.

---

## Fix Plans

1. **RPT-01 incomplete status drops private count** (Major, spec deviation). In `src/auditor/vulnscan/status.py:38-39`, append `suffix` (private, plus the runtime parts) to `INCOMPLETE` when K>0. Add a `test_status_headline` case `{**BASE, "skipped_private": 2, "errors": ["x"]}` → `"Varredura de dependências incompleta (2 privada(s) não consultada(s))"`.
2. **Cross-lockfile private leak untested** (M09, privacy). Add a `test_vs_scanner.py` case: `@acme/x@1.0.0` private in one lockfile (scoped `.npmrc` in that package dir) and public in another. Assert it is not in `osv.queried` and `skipped_private` counts it.
3. **Mixed dev/prod occurrences** (M08). Add a scanner test: the same vulnerable package is `dev: true` in one lockfile and prod in another. Assert severity stays the advisory severity, not `info`.
4. **RT-04 stats** (M24). In `test_vs_scanner.py`, add `.node-version` = `lts` (or `.python-version` `3.99`). Assert `result.stats["runtime_unknown"] == 1` and that no endoflife finding exists for it.
5. **`UV_FIND_LINKS`** (M25). Add `"UV_FIND_LINKS"` to the param list of `test_pip_env_private_index_skips_requirements`.
6. **10 000 boundary** (M10). Run `scan(..., max_packages=3)` with exactly 3 public packages. Assert `truncated is False` and all 3 are queried.
7. **App wiring of `/defaults`** (M30). In `App.test.tsx`, mock `getDefaults` → `{vuln_scan: true}` and assert the checkbox ends up checked.
8. **RT-03 wording** (spec-precision). Either assert the message contains "permite" + "sem suporte", or relax the spec quote to match the implemented message.

## Requirement Traceability Update

| Requirement | New Status |
| ----------- | ---------- |
| LOCK-01, LOCK-02, LOCK-04, LOCK-05, OSV-01, OSV-02, FND-02, RT-01, RT-02, RT-05, CFG-01, CFG-02, DUP-01, E2E-05 | ✅ Verified |
| LOCK-03, OSV-03, FND-01, RT-03, UI-01 | ⚠️ Verified with test gaps (fixes 2, 3, 5, 6, 7, 8) |
| RT-04 | ❌ Needs test (fix 4) |
| RPT-01 | ❌ Needs fix (fix 1) |

---

## Re-verification (fix loop 1) — 2026-11-10

**Verdict: ✅ PASS**

Safety: `status.py`, `scanner.py`, `lockfiles/python.py` and `frontend/src/App.tsx` were backed up fresh to scratchpad `verifier-backup-fl1/` (the fix changed `status.py`). Every file was restored after each mutant and the sha256 check passed (`sha256sum -c` SUCESSO ×4). No git writes. Harness: `scratchpad/mutants_fl1.py`, log `scratchpad/mutants_fl1.log`.

### Previously surviving mutants (re-applied)
| # | File | Result | Killing test |
| - | ---- | ------ | ------------ |
| M08 | `scanner.py:83` any-dev → info | ✅ Killed | `test_vs_fix_loop1.py::test_dev_in_one_prod_in_other_keeps_severity` |
| M09 | `scanner.py:153` private only if all | ✅ Killed | `::test_private_in_one_lockfile_is_never_queried` |
| M10 | `scanner.py:155` cap `>=` | ✅ Killed | `::test_cap_boundary` |
| M24 | `scanner.py` runtime_unknown not counted | ✅ Killed | `::test_unknown_runtime_counted_in_stats` |
| M25 | `lockfiles/python.py:218` drop `UV_FIND_LINKS` | ✅ Killed | `::test_uv_find_links_env_skips_requirements` |
| M30 | `App.tsx:47` ignore `/defaults` | ✅ Killed | `App.test.tsx` "AUDITOR_VULN_SCAN=true no servidor deixa o checkbox marcado" |

### New mutants in fixed code
| # | File | Mutation | Result |
| - | ---- | -------- | ------ |
| N1 | `status.py:39` | incomplete headline without suffix | ✅ Killed |
| N2 | `status.py:25` | suffix only when K > 1 | ✅ Killed |
| N3 | `status.py:38` | incomplete only with > 1 reason | ✅ Killed |
| N4 | `App.tsx:48` | `/defaults` failure ⇒ checked | ✅ Killed |
| N5 | `App.tsx:47` | inverted server default | ✅ Killed |

**Sensor**: 11/11 killed. Across both rounds, all 31 non-equivalent mutants are now killed; M04 is equivalent.

### AC updates
- **RPT-01 → ✅ PASS.** `test_vs_fix_loop1.py:33-35` asserts `headline == "Varredura de dependências incompleta (2 privada(s) não consultada(s))"`.
- **RT-03 → ✅ PASS.** The spec now quotes the implemented text. `test_vs_fix_loop1.py:81-86` asserts the exact message prefix and `severity == "medium"`.
- **RT-04, LOCK-03, OSV-03, FND-01, UI-01 → ✅ PASS.** The gaps are closed by the tests above. The poetry `groups = ["dev"]` case is covered by `test_poetry_dev_group`.
- **Accepted note (not a spec violation):** VCS/URL/path requirement lines are never queried but are not counted in `skipped_private`.

**ACs verified: 21/21.**

### Gates
pytest 518 passed (new baseline) · ruff clean · mypy clean · vitest 55 passed · tsc exit 0.

### Lessons
L-001..L-007 stay `candidate`. `lessons.py` has no "resolved" state: a candidate is general guidance that is promoted when it recurs in a later feature, and `penalize` applies only when a confirmed lesson was loaded and the failure recurred, which is not the case here. Fixing the grounding incidents does not change their status.
