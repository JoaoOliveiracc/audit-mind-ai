# Vulnerable Dependencies & Runtimes Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement with the `tlc-spec-driven` skill (Execute flow + Critical Rules). If it cannot be activated, STOP and tell the user.

**Design**: `.specs/features/vuln-scan/design.md` · **Status**: Done

## Test Coverage Matrix
| Layer | Test | Location | Run |
| ----- | ---- | -------- | --- |
| Pure (versions, severity, parsers, runtime) | unit with fixture files (real-world-shaped samples) | `tests/vulnscan/test_*.py` | `.venv/bin/pytest -q` |
| HTTP gateways | unit with `httpx.MockTransport` (no network) | `tests/vulnscan/test_sources.py` | same |
| Scanner / node | unit with fake clients | `tests/vulnscan/test_scanner.py` | same |
| CLI/API/report | integration (CliRunner/TestClient) | existing test files | same |
| Frontend form | Vitest | `frontend/src/components/StartForm.test.tsx` | `./node_modules/.bin/vitest run` |
| E2E | offline graph + fake transport | `tests/test_e2e.py` | pytest |

## Gate
Quick `.venv/bin/pytest -q` · Build `make ci` (end of each phase)

## Execution Plan
### Phase 1 — pure core (no I/O beyond reading fixtures)
`T1 → T2 → T3 → T4 → T5`
### Phase 2 — sources, orchestration, graph
`T6 → T7 → T8 → T9 → T10`
### Phase 3 — UI, E2E, docs
`T11 → T12`

## Task Breakdown
- **T1** `models.py`, `versions.py`, `severity.py` (CVSS v3 base score; GHSA map) — Req OSV-02 (severity part) · unit
- **T2** npm parsers: package-lock v2/v3, yarn v1 + berry, pnpm + `registry_config.py` (`.npmrc`, `.yarnrc.yml`) — Req LOCK-01..04 · unit
- **T3** composer.lock parser — LOCK-01..04 · unit
- **T4** Python parsers: poetry.lock, uv.lock, Pipfile.lock, requirements pins (dev filenames, index → skip file), PEP 503 names — LOCK-01..04, OSV-01 (normalization) · unit
- **T5** runtime detectors (nvmrc, node-version, engines, composer require.php, python-version, requires-python, Dockerfile FROM; cycle vs exact per runtime) — RT-01, RT-02 (parsing), RT-05 · unit
- **T6** `OSVClient` (querybatch chunks + pagination, vulns fetch + memo, fixed-version selection, 5 MB streaming cap) — OSV-01..03 · unit (MockTransport)
- **T7** `EndOfLifeClient` + runtime evaluation (EOL / behind patch / range) — RT-02..04, OSV-03 · unit (MockTransport)
- **T8** `scanner.scan` (walk with pruning, private filter, cross-lockfile grouping, 10 000 cap, findings, stats, error handling) — FND-01, LOCK-03, OSV-03 (cap), CFG-02 (stats) · unit (fake clients)
- **T9** graph node + settings `AUDITOR_VULN_SCAN` + CLI `--vuln-scan/--no-vuln-scan` + API `vuln_scan` + adversarial skip + investigator no-duplicate note + `.lock` not binary + core deps (`httpx`, `packaging`, `pyyaml`, `tomli;<3.11`) — CFG-01, FND-02, DUP-01, LOCK-05 · unit + integration
- **T10** stats + explicit scan status line in report (MD/HTML) and CLI summary, SSE event — CFG-02, RPT-01 · unit/integration
- **T11** web form checkbox + types + client — UI-01 · Vitest
- **T12** E2E-05 + docs (README, USAGE, DOCUMENTACAO G48 ✅, SECURITY egress section, ARCHITECTURE, `.env.example`) (AD-003 already recorded at Design) — E2E-05 · e2e + build gate

## Validation
Granularity: each task = one module/cohesive layer ✅. Dependencies linear within phases, phases ordered ✅. Co-location: every code task carries its tests ✅.
**Size:** 12 tasks → packs into 2–3 task-budgeted batches (Phase 1 = 5, Phase 2 = 5, Phase 3 = 2) → sub-agent offer applies.

## Phase 1 — execution notes & code-review fixes
- T1–T5 done. T3 tests and code were written in the same step (red was only an import error); T4/T5 ran red before implementing.
- Format decision (T3): Composer `v` prefix stripped before querying (OSV indexes Packagist without it); branch versions (`dev-main`) are private.
- `/code-review` after phase 1 — 10 findings, all fixed with regression tests (`tests/vulnscan/test_vs_review_fixes.py`):
  1. runtime deps declared in core (`pyyaml>=6`, `packaging>=23`, `tomli>=2; <3.11`) — pulled forward from T9;
  2. npm aliases (`package-lock` `name`, yarn v1 `alias@npm:real@…`) query the real package (also avoids leaking alias names);
  3. Pipfile.lock unknown `index` ⇒ private;
  4. `load_registry_config` never raises (unreadable/invalid UTF-8/non-mapping `npmScopes`);
  5. PHP/Python wildcard minor (`3.x`) ⇒ unknown (absent minor `>=8` stays `8.0`);
  6. `!=` accepted in ranges and ignored as lower bound;
  7. Composer pre-release order (dev < alpha < beta < RC < stable < patch; numeric suffix);
  8. pnpm v5 keys (`/name/version`) parsed; unrecognized entries recorded as an error (never "clean" silently);
  9. `===` pins; `--find-links`/`-f` and private sources in `-r`/`-c` includes (within root, cycle-safe) skip the file;
  10. STATE handoff refreshed.

## Phase 2 — execution notes
- T6 `sources/__init__.py` (allowlisted `checked_client`, streaming `get_json` 5 MB cap, `SourceError`) + `sources/osv.py` (`OSVClient`: chunks of 500, pagination ≤ 10 pages, memoized parallel fetch, `Advisory.fixed_for`). Extra: advisory ids URL-encoded in the path (`quote(id, safe='')`). `httpx>=0.27` moved from [dev] to core.
- T7 `sources/eol.py` (`EndOfLifeClient`, memo) + `runtime.evaluate` → `Evaluation(status, severity, message)`.
- T8 `scanner.scan` (walk with `ignore_dirs` pruning, no symlinks; 50 MB lockfile cap; package grouped by `(eco, normalized name, version)`, private if any occurrence is private; cap `MAX_PACKAGES`; runtime finding recommends newest supported cycle).
- T9 node `dependency_scan` (audit → dependency_scan → verify), `Settings.vuln_scan`, CLI `--vuln-scan/--no-vuln-scan`, API `vuln_scan`, `adversarial._eligible` skips osv/endoflife, `VULN_SCAN_NOTE` (DUP-01), `.lock` removed from binary extensions. Decision: `verify` allows up to 50 MB for deterministic findings (lockfiles exceed `max_file_bytes`) — FND-02.
- T10 `vulnscan/status.py` (`scan_status`) used by MD/HTML report ("Dependências e Runtimes" section, always present), CLI summary and `/audits/{id}/findings` (`dependency_scan`). RPT-01 precision fix recorded in spec (with-findings wording; private-count suffix).
- Suite: 360 → 440 (+80); 3.12 and 3.10 green; `make ci` exit 0.
- `/code-review` after phase 2 — 10 findings, all fixed with regression tests (`tests/vulnscan/test_vs_review2_fixes.py`):
  1. OSV/endoflife clients catch malformed shapes (`AttributeError`/`ValueError`, results not a list or wrong length) → recorded error;
  2. node `dependency_scan` has a catch-all (scan error → stats `errors`, LLM findings kept, status "incompleta"); clients closed even if the second constructor fails; runtime detectors tolerate wrong JSON/TOML types;
  3. symlinked files are skipped by the walker (could point outside the project);
  4. status: `skipped_files` make the scan incomplete (with reasons);
  5. pagination cap reached → recorded error (never silently complete);
  6. headline mentions runtime alerts and unevaluated runtime declarations;
  7. `verify` caches content + normalized text per file (one read per lockfile);
  8. runtime "behind patch" recommends the same cycle's latest patch; EOL range titled "sem suporte" (`Evaluation.reason/latest`);
  9. `_MIN_LINE_LEN` comment restored;
  10. single rule `models.is_deterministic` / `DETERMINISTIC_SOURCES` / `MAX_LOCKFILE_BYTES`, shared `RUNTIME_LABELS`; dead `ctx["dependency_scan"]` removed.
- Suite after fixes: 468 (3.12 and 3.10); `make ci` exit 0.

## Phase 3 — execution notes
- T11 `StartForm` checkbox "Verificar dependências vulneráveis (envia nomes e versões ao OSV.dev)" — visible outside "opções avançadas" (egress choice must be seen), off by default, sent as `vuln_scan` (`types.ts`). Extra: Timeline step "04 · Investigação" now covers nodes `audit` + `dependency_scan` (an unknown node would leave the step ambiguous); `Entry` exposes `data-status` for the test. Tests: `StartForm.test.tsx` (3), `Timeline.test.tsx` (+1).
- T12 E2E-05 `tests/test_e2e.py::test_e2e05_vuln_scan_end_to_end`: full graph, real `OSVClient`/`EndOfLifeClient` over `httpx.MockTransport`, `socket.connect` patched to fail; asserts 1 OSV finding verified and not judged, 1 runtime finding, `skipped_private == 1`, private name never sent, judge saw only the LLM finding, report status line. Passed on first run (it exercises behaviour delivered in phases 1–2).
- Docs: README (feature, diagram, command), docs/USAGE (env var + section), docs/ARCHITECTURE (diagram, §6.1, data flow), SECURITY (egress), docs/ROADMAP, DOCUMENTACAO (config, node table, flow, G48 row ✅, G25–G48), `.env.example`.
- Suite: backend 469 (3.12/3.10), frontend 48; `make ci` exit 0.
- `/code-review` after phase 3 — 10 findings; 8 fixed with regression tests (`tests/vulnscan/test_vs_review3_fixes.py`, `StartForm/Timeline/ResultsPanel.test.tsx`), 2 left to the user:
  1. web checkbox starts from the server default (`GET /defaults`), user choice never overwritten (UI-01 updated);
  2. user-level/env npm registry config (`~/.npmrc`, `~/.yarnrc.yml`, `npm_config_*registry`, `YARN_NPM_REGISTRY_SERVER`) and pip/uv global indexes (env + `pip.conf`; unreadable ⇒ private) honored — private names no longer leak (LOCK-03 updated); tests isolate host env/system `pip.conf` (`tests/conftest.py`);
  3. per-file guard in `scanner.scan` (one malformed lockfile no longer discards every other result);
  4. linear line lookup (`lockfiles/_lines.py`; 20 000-package `package-lock` was > 120 s, now < 3 s);
  7. poetry/uv `(name, version)` block index and section-aware Pipfile index (duplicate names cite their own line);
  8. Timeline step done when a later step ran (pre-G48 resumes never emit `dependency_scan`);
  9. results panel shows the RPT-01 status (`dependency_scan_status`, rendered by the backend `scan_status` — no duplicated wording);
  10. single precedence rule `resolve_vuln_scan` (CLI, API, node).
  - **Not changed (user decision):** (5) `.lock` readable by investigators even with the scan off — required by LOCK-05; (6) each vulnerable package weighs like any finding in the health score — changing the scoring formula is a product decision.
- Suite: backend 509 (3.12/3.10), frontend 53; `make ci` exit 0.

## Fix loop 1 (after Verifier FAIL minor — 14/21 ACs, 25/32 mutants)
| Gap | Fix | Test |
| --- | --- | ---- |
| 1 RPT-01 incomplete status lacked the private suffix | `status.py`: "incompleta" + suffix | `test_vs_fix_loop1.py::test_incomplete_headline_carries_private_suffix` |
| 2 M09 private-in-any-lockfile | — (code correct, untested) | `test_private_in_one_lockfile_is_never_queried` |
| 3 M08 dev-only = all occurrences | — | `test_dev_in_one_prod_in_other_keeps_severity` |
| 4 M24 `runtime_unknown` stat | — | `test_unknown_runtime_counted_in_stats` |
| 5 M25 `UV_FIND_LINKS` | — | `test_uv_find_links_env_skips_requirements` |
| 6 M10 cap boundary | — | `test_cap_boundary` (n == cap ⇒ not truncated) |
| 7 M30 App `getDefaults` wiring | — | `App.test.tsx` "AUDITOR_VULN_SCAN=true no servidor deixa o checkbox marcado" + fetch failure |
| 8 RT-03 wording | spec updated to the implemented text | `test_range_message_says_range_allows_unsupported_runtime` |
| minor poetry `groups = ["dev"]` | — | `test_poetry_dev_group` |
- Not changed: M04 (OSV query-side normalization) is equivalent — parsers already normalize PyPI names. VCS/URL/path requirement lines carry no version, so they are never queried (LOCK-03 satisfied) but are not counted in `skipped_private` — noted, not a spec violation.
