# Deduplication & Test Isolation — Validation

**Date**: 2026-11-10
**Spec**: `.specs/features/dedup-and-test-isolation/spec.md`
**Diff range**: uncommitted working tree on `develop` vs `HEAD` (`0d5d969`)
**Verifier**: independent sub-agent (author ≠ verifier)

**Verdict: ❌ FAIL (test gaps only; no production defect found).** The implementation is correct: gates are green on 3.12 and 3.10, behavior matches HEAD apart from the accepted changes, and the real `~/.config/auditor` is untouched. But 4 behavior-level mutants on spec-named call sites survive: CLI labels, CLI counts, report counts, and the `None`→info rule. ISO-03 has no automated sensor (the spec allows a manual gate for it).

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 events.py + use in nodes/runner/cli | ✅ Done | `src/auditor/events.py`; nodes import `emit as _emit` |
| T2 scoring.py + use in synthesis/runner/cli/renderer | ✅ Done | `src/auditor/scoring.py` |
| T3 lazy data dir + `AUDITOR_DATA_DIR` + conftest | ✅ Done | `store.py:16-41`, `tests/conftest.py` |
| T4 docs | ✅ Done | `.env.example:70`, `docs/USAGE.md:73`, `DOCUMENTACAO.md:178,483`, `SECURITY.md:59`, `docs/ARCHITECTURE.md` |

---

## Spec-Anchored Acceptance Criteria

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| DUP-01 no-op outside run | silent no-op | `tests/test_shared.py:18` — `events.emit({...}) is None` | ✅ (weak: checks only the return value and that nothing is raised) |
| DUP-01 reaches custom stream | payload reaches `stream_mode="custom"` | `tests/test_shared.py:34` — `chunks == [{"type": "probe", "value": 42}]` | ✅ (mutant j killed) |
| DUP-01 exists only in events.py; nodes use it | no other module-level `_emit` / `get_stream_writer` import | `tests/test_shared.py:37-48` — `offenders == []` (source scan) | ✅ (mutant a killed). The nodes using it is covered indirectly by `test_audit.py:321` and `test_adversarial.py:233`, which monkeypatch `_emit` |
| DUP-02 label for every compiled-graph node | `set(NODE_LABELS) == graph nodes` | `tests/test_shared.py:54-55` — `set(events.NODE_LABELS) == nodes`, `set(events.NODE_ICONS) == nodes` | ✅ (mutants b, c killed) |
| DUP-02 API phase events use it | `phase.label == NODE_LABELS[node]` | `tests/test_shared.py:76` — `phase["data"]["label"] == events.NODE_LABELS["discovery"]` | ✅ (mutant p killed) |
| DUP-02 **CLI** uses it | CLI line built from NODE_LABELS | — no evidence | ❌ GAP (mutant l survived) |
| DUP-03 include_zero=True → 5 keys, zeros, order | `{critical:0, high:2, medium:0, low:1, info:0}` in order | `tests/test_shared.py:86-87` | ✅ |
| DUP-03 include_zero=False → only present | `{high:2, low:1}` | `tests/test_shared.py:91`; `tests/test_api.py:38` | ✅ (mutants d, e killed) |
| DUP-03 missing severity → info | `{"info": 1}` | `tests/test_shared.py:95` (key absent only) | ✅ / ⚠️ the `severity: None` case is not tested (mutant k survived) |
| DUP-03 synthesis + API use it | identity / delegation | `tests/test_shared.py:102-104` — `synthesis.severity_counts is scoring.severity_counts`; `_counts(_F) == ...` | ✅ |
| DUP-03 **report + CLI** use it | context counts / table from `severity_counts` | `tests/test_shared.py:107-110` — scan for `counts.get(` only | ❌ GAP (mutants m and n survived; the scan misses a `Counter`-based copy) |
| DUP-04 no existing test modified, suite green | `git diff -- tests/` empty | `git diff --stat -- tests/` → empty; only new files (`conftest.py`, `test_shared.py`, `test_data_dir.py`) | ✅ |
| ISO-01 importing store/app creates nothing | no `$HOME/.config/auditor` | `tests/test_data_dir.py:15-22` — subprocess with tmp HOME; `not (tmp_path/".config"/"auditor").exists()` | ✅ (mutant f2 killed) |
| ISO-02 env var → meta, checkpoint, compact default | paths under `$AUDITOR_DATA_DIR` | `tests/test_data_dir.py:30-35` (both paths and both files created); `:54-55` (compact default path, dir not created) | ✅ (mutants g, o killed) |
| ISO-02 default → `~/.config/auditor` | default path | `tests/test_data_dir.py:42-43` (meta path only; checkpoint default implied by the shared `data_dir()`) | ✅ (mutant f killed) |
| ISO-03 full suite with fresh HOME → no `.config/auditor` | dir absent | manual gate (per tasks.md); re-run by Verifier, see below | ✅ manual / ⚠️ no automated sensor (mutant h survived) |

**Status**: ❌ 2 AC call-site gaps (DUP-02 CLI; DUP-03 report/CLI), plus 2 ⚠️ (None→info untested; ISO-03 manual only).

---

## Behavior Equivalence (HEAD vs working tree)

Method: I exported `git archive HEAD src` into a scratch dir. One script ran against the old and the new `src` (confirmed via `auditor.__file__`). It compared the CLI labels, the API `NODE_LABELS`, `synthesis.severity_counts` (the synthesis prompt input), `runner._counts`, `renderer.build_context()["counts"]`, `compute_health_score` and the full `_print_summary` table text. Cases: `[]`, high/high/low, mixed with missing key, `None`, `""`, unknown/uppercase (`"bogus"`, `"HIGH"`).

| Surface | Difference | Accepted? |
| ------- | ---------- | --------- |
| (a) CLI phase lines | only `planning`: "Planejando dimensões de auditoria" → "Planejando dimensões". Icons and spacing are identical. A node missing from the map now prints "• node" instead of "node" (unreachable: every graph node has a label) | ✅ spec accepts the label text change |
| (b) API phase labels | identical | ✅ |
| (c) synthesis / report / API counts | `severity: None` → key `None` became `info`. **Also** `severity: ""` → key `""` became `info` (same falsy `or` rule, not named in the spec) | None ✅ accepted; `""` minor, undocumented |
| (c) CLI table | for `None`/`""` findings the old table showed info=0 (the finding was dropped, so the rows did not sum to the total); the new table shows info=1 | ✅ follows from the None→info change (an improvement) |
| health score | identical in all cases | ✅ |
| unknown severities (`bogus`, `HIGH`) | identical (extra key kept, same order) | ✅ |

---

## Gate Check

| Interpreter | pytest | ruff `src tests` | mypy `src` |
| ----------- | ------ | ---------------- | ---------- |
| 3.12.3 (`.venv`) | 174 passed, 0 failed, 0 skipped | All checks passed | no issues (36 files) |
| 3.10.21 (scratch venv) | 174 passed | All checks passed | no issues (36 files) |

- Tests before the feature: 160 (collected with the 2 new files ignored); after: 174 (+14: `test_shared.py` 10, `test_data_dir.py` 4). No test was deleted or weakened.
- `make ci` was not run as a whole; its Python components were run individually above.

---

## ISO Evidence

- **ISO-03 (3.12):** `env -u AUDITOR_DATA_DIR HOME=<scratch>/verifier16/homeM1gK .venv/bin/pytest -q` → 174 passed. `$HOME` stayed empty and `.config/auditor` was not created.
- **ISO-03 (3.10):** same with a fresh HOME (`home9frm`) → 174 passed, HOME empty.
- **No eager creation (fresh HOME `homegATt`):** `python -c "import auditor.api.main, auditor.api.deps, auditor.cli"`, then `auditor db compact` (exit 0, "Nada a compactar: $HOME/.config/auditor/audits-checkpoints.sqlite não existe."), then `auditor serve --help`. HOME stayed empty. A real `serve` startup opens the store in the lifespan and creates the dir then, which is the intended "created when a store is opened".
- **Real dir mtimes** (`stat %Y`), recorded before the first test run (14:43) and after all runs, mutants included (14:49): unchanged.
  - `audits-checkpoints.sqlite` 1794332430
  - `audits.sqlite` 1794319360
  - `audits.sqlite-shm` 1794332464
  - `audits.sqlite-wal` 1794319399
  - dir 1794332430
  - Caveat: a live `auditor serve --reload` (pid 259712) was running against the real dir. It did not write during the window, so the evidence is valid but was not fully controlled.
- Observation (out of scope): `config.py:17-19` still *reads* the real `~/.config/auditor/.env` at import during tests. It is read-only, so ISO is not violated, but the developer's real keys and settings leak into the test environment.

---

## Discrimination Sensor

Method: for each mutant, a fresh copy of `src/ tests/ pyproject.toml .github Makefile frontend/package*.json` under `scratchpad/verifier16/mut_<id>`. `PYTHONPATH=<copy>/src`, cwd = copy, `HOME=<copy>/home`, `AUDITOR_DATA_DIR` unset. The unified diff was printed for each mutant, and `auditor.__file__` confirmed that the copy was imported. The unmutated baseline copy gave 174 passed.

| # | File:line | Mutation | Result | Killed by |
| - | --------- | -------- | ------ | --------- |
| a | `nodes/verify.py:19` | re-add local `def _emit` (delegating) | ✅ Killed | `test_dup01_dup02_no_copies_left_outside_events` |
| b | `events.py:21` | drop `"verify"` from NODE_LABELS | ✅ Killed | `test_dup02_labels_cover_every_graph_node` |
| c | `events.py:29` | drop `"report"` from NODE_ICONS | ✅ Killed | same |
| d | `scoring.py:19` | ignore `include_zero` (always zeros) | ✅ Killed | `test_api::test_counts_helper` + 2 dup03 tests |
| e | `api/runner.py:25` | `_counts` with `include_zero=True` (API contract change) | ✅ Killed | `test_api::test_counts_helper`, `test_dup03_old_entry_points_delegate_to_scoring` |
| f | `api/store.py:23` | `data_dir()` does `mkdir` eagerly | ✅ Killed | `test_iso02_default_is_home_config_and_not_created_eagerly`, `test_iso02_db_compact_default_follows_data_dir` |
| f2 | `api/store.py` module level | `data_dir().mkdir()` at import | ✅ Killed | `test_iso01_importing_store_and_app_creates_nothing` |
| g | `api/store.py:22` | ignore `AUDITOR_DATA_DIR` | ✅ Killed | `test_iso02_data_dir_from_env`, `test_iso02_db_compact_...` |
| h | `tests/conftest.py:7` | autouse removed | ❌ Survived (174 passed); **the fresh HOME got `.config/auditor`** | nothing automated; caught only by the manual ISO-03 gate |
| i | `tests/conftest.py:16-21` | `cache_clear` removed | ❌ Survived, no leak | — (consequence: the API singletons stay bound to the *first* test's tmp dir and their state is shared across tests; isolation from real HOME still holds) |
| j | `events.py:39` | `return` as first line of `emit` | ✅ Killed | `test_dup01_emit_reaches_the_custom_stream_inside_a_run` |
| k | `scoring.py:21` | `f.get("severity", INFO)` (None no longer → info) | ❌ Survived | — the accepted behavior change is not pinned |
| l | `cli.py:65` | CLI label ignores NODE_LABELS (`{node}`) | ❌ Survived | — DUP-02 "CLI SHALL use it" untested |
| m | `report/renderer.py:39` | `severity_counts(..., include_zero=False)` | ❌ Survived | — near-equivalent for HTML (template uses `counts.get(sev, 0)`), but `build_context()["counts"]` is unpinned |
| n | `cli.py:160` | re-add a local `Counter`-based counting copy | ❌ Survived | — the `counts.get(` source scan misses it |
| o | `api/store.py:41` | checkpointer opens `meta_db_path()` | ✅ Killed | `test_iso02_data_dir_from_env` |
| p | `api/runner.py:79` | phase label = raw node name | ✅ Killed | `test_dup02_api_phase_events_use_the_shared_labels` |

**Sensor depth**: expanded (17 mutants). **Result**: 11/17 killed. The required set (a–j) went 7/10: h and i are test-infrastructure mutants, h is covered by the manual gate, and i is defensive. Of the extras k–p, 4 survived (k, l, m, n): real call-site gaps.

---

## Judgment Calls

- **Source-scanning guards** (`test_shared.py:37-48`, `:107-110`): reasonable as cheap regression tripwires, but brittle in both directions.
  - False negatives: they match exact strings. A `Counter` copy (mutant n), a `def  _emit(`, an `_emit = lambda`, or labels under a different name all pass. The `"\nNODE_LABELS = {"` needle also misses the new annotated form `NODE_LABELS: dict[...] = {`.
  - False positives: any future legitimate `counts.get(` anywhere in `src` fails the build.
  - Behavior tests at each call site would be stronger: CLI `_run` output contains `NODE_LABELS[node]`, `_print_summary` table, `build_context()["counts"]`. Keep the scans as secondary checks.
- **`from ..events import emit as _emit`**: acceptable. There is exactly one implementation; the alias is only a name binding, so the existing monkeypatch points (`test_audit.py:321`, `test_adversarial.py:233`) keep working without touching tests. That satisfies DUP-04 literally without a second implementation. Cost: patching `events.emit` would not affect the nodes (name bound at import). This is documented in the inline comment; fine.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / surgical | ✅ (+50 / −113 in src) |
| No scope creep | ✅ (`build_checkpointer(db_path=None)` param is a small addition, unused by callers except tests indirectly; OK) |
| Matches patterns | ✅ |
| Spec-anchored asserted values | ✅ where present |
| Every AC call site covered | ❌ CLI (DUP-02/03), report (DUP-03) |
| Unclaimed tests | none — all new tests map to DUP/ISO |
| Guidelines | none project-specific — strong defaults applied |

---

## Fix Plans

1. **(Major) DUP-02 CLI label coverage.** Add a test that runs `cli._run` with a fake graph yielding `{"planning": {}}` and asserts the printed line contains `NODE_ICONS["planning"]` and `NODE_LABELS["planning"]`. Kills l.
2. **(Major) DUP-03 report/CLI counts coverage.**
   - Assert `renderer.build_context({"findings": [...]}, "x")["counts"]` equals the full 5-key dict, which kills m.
   - Assert the `_print_summary` table rows (e.g. `info │ 1` for a `None`-severity finding), which kills n and k.
3. **(Minor) Pin None→info.** `scoring.severity_counts([{"severity": None}], include_zero=False) == {"info": 1}`. Decide whether `""` → info is also intended and document it. Kills k.
4. **(Minor) ISO-03 automation (optional).** Add a session-scoped check in conftest that asserts nothing is created under `Path.home()/".config"/"auditor"` (compare against a pre-session snapshot), or a test that runs a subset of the suite in a subprocess with a fresh HOME. This would kill h. If neither is added, keep the manual gate.
5. **(Cosmetic) Guard needles.** Add `"\nNODE_LABELS: "` and `Counter(` variants, or replace the scans with AST-based checks for module-level `FunctionDef _emit` and dicts keyed by graph nodes.

---

## Requirement Traceability Update

| Requirement | Previous | New |
| ----------- | -------- | --- |
| DUP-01 | Implementing | ✅ Verified |
| DUP-02 | Implementing | ⚠️ Needs test (CLI) |
| DUP-03 | Implementing | ⚠️ Needs test (report, CLI, None) |
| DUP-04 | Implementing | ✅ Verified |
| ISO-01 | Implementing | ✅ Verified |
| ISO-02 | Implementing | ✅ Verified |
| ISO-03 | Implementing | ✅ Verified (manual gate) |

## Summary

**Overall**: ⚠️ Not ready until fix tasks 1–3 are done. Production code behaves correctly.
**Gate**: 174 passed on 3.12 and 3.10; ruff and mypy clean on both.
**Sensor**: 11/17 killed (the 6 survivors are h, i, k, l, m, n).

## Re-verification (fix loop 1)

**Gates**: `.venv/bin/pytest -q` 179 passed · ruff clean · mypy clean (36 files) · py3.10 venv 179 passed. `git status tests/`: only new files (conftest.py, test_data_dir.py, test_shared.py); no tracked test file modified (DUP-04 holds).
**Real data**: `~/.config/auditor/*.sqlite*` mtimes identical before/after (a live `auditor serve --reload`, pid 259712, was running).
**Checks**: conftest sets `HOME` at module import, before any `auditor` import (imports are inside fixtures). CLI-table test asserts full dict equality → an empty/wrong row dict fails (not vacuous).

| Mutant | Result | Killing test(s) |
| --- | --- | --- |
| h remove `_isolated_data_dir` autouse | KILLED | session `_no_leak_into_home` ("vazou dados para $HOME/.config/auditor") |
| k None no longer → info | KILLED | `test_dup03_none_or_empty_severity_counts_as_info`, report/CLI counting tests (6 fails) |
| l CLI label ignores NODE_LABELS | KILLED | `test_dup02_cli_phase_lines_use_shared_labels` |
| m renderer `include_zero=False` | KILLED | `test_dup03_report_context_counts_use_shared_counting` |
| n `Counter` copy in cli.py | KILLED | `test_dup03_no_other_counting_loops`, `test_dup03_cli_summary_table_uses_shared_counting` |

Note: scratch copies show 2 baseline failures in `test_ci_config.py` (frontend/ not copied); identical in an unmutated copy, so excluded.
Gaps 1–5 resolved. **Verdict: PASS.**
