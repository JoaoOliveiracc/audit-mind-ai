# CI & Quality Gates Validation

**Date**: 2026-11-10
**Spec**: `.specs/features/ci-quality-gates/spec.md`
**Diff range**: uncommitted working tree on `develop` over `6f440e6` (HEAD)
**Verifier**: independent sub-agent (author ≠ verifier)

**Verdict**: ✅ **PASS**, with minor hardening gaps. All 12 ACs have evidence, every gate passes on 3.12 and 3.10, and all 27 requested or spec-relevant mutants were killed. 5 extra adversarial mutants survived. They are listed under Fix Plans as optional hardening, not blockers.

---

## Diff surface

| File | Change |
| ---- | ------ |
| `.github/workflows/ci.yml` (new) | 2 jobs: `backend` (matrix 3.10/3.12) and `frontend` (Node 20) |
| `Makefile` | `typecheck`, `frontend-ci`, `ci`; `install` uses `.[dev,api]`; `frontend-install` uses `npm ci` |
| `pyproject.toml` | `[dev]` gains `httpx>=0.27` and `pyyaml>=6`; `ruff>=0.15,<0.18`, `mypy>=2.1,<3`; `[tool.ruff.lint] select` |
| `frontend/pnpm-lock.yaml`, `frontend/pnpm-workspace.yaml` | deleted |
| `src/auditor/api/routes.py` | `_require()` guard in place of `store.get()` passed directly to `_summary` (lines 115, 166, 256-261) |
| `src/auditor/api/store.py` | `builtins.list[str]` annotation |
| `src/auditor/nodes/{adversarial,audit,verify}.py` | `get_stream_writer: Optional[...]` declaration; `stats: dict[str, Any]` |
| `src/auditor/nodes/{clarify,planning}.py` | `cast(Model, llm.invoke(...))` |
| `tests/test_ci_config.py` (new) | 8 structural tests |
| `README.md`, `DOCUMENTACAO.md`, `docs/USAGE.md`, `docs/ROADMAP.md` | CI badge, `make ci`, `.[dev,api]`, G36/G37/G38 status, G40 partial |

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 mypy zero | ✅ | 0 errors on mypy 2.1.0 (py3.12) and mypy 2.4.1 (py3.10, and also `--python-version 3.12`) |
| T2 npm only + httpx | ✅ | pnpm files deleted; `npm ci` is green inside `make ci` |
| T3 Makefile | ✅ | stops at the first failing gate (verified in scratch, see GATE-01) |
| T4 workflow | ✅ | structure verified; semantics reviewed (below) |
| T5 Python 3.10 | ✅ | ruff 0.17.4, mypy 2.4.1, pytest: all green |
| T6 docs | ✅ | consistent with the implementation |

---

## Spec-Anchored Acceptance Criteria

| AC | Spec-defined outcome | Evidence (`file:line` — assertion / command) | Result |
| -- | -------------------- | -------------------------------------------- | ------ |
| TYPE-01 | `mypy src` exits 0 with no errors | gate: `.venv/bin/mypy src` → `Success: no issues found in 34 source files` (3.12, mypy 2.1.0); py310 venv → same (mypy 2.4.1). Sensor T1–T7: reverting any single fix makes mypy fail | ✅ |
| TYPE-02 | `make typecheck` runs `mypy src` | `Makefile:16-17`; `tests/test_ci_config.py:60` — `re.search(r"^typecheck:\n\t.*mypy src$", makefile, re.M)` | ✅ |
| TYPE-03 | no behavior change; same test count | 112 tests collected without the new file, 120 = 112 + 8 with it; all pass. Diff review below | ✅ |
| GATE-01 | `make ci` runs ruff, mypy, pytest, npm ci, vitest, tsc, vite build and stops at the first error | `Makefile:23` `ci: lint typecheck test frontend-ci`; `tests/test_ci_config.py:59-62` (regexes for `ci:`, `typecheck:`, `frontend-ci: … npm ci.*npm test.*npm run build`, `lint: … ruff check src tests`); `tests/test_ci_config.py:67-68` — `'"build": "tsc --noEmit && vite build"' in pkg`, `'"test": "vitest run"' in pkg`. Real run: `make ci` exit 0 (ruff, mypy, 120 pytest, 27 vitest, tsc, vite build). Stop-on-first-error in scratch: a lint error stops at `Makefile:14: lint`; a type-only error stops at `Makefile:17: typecheck` (pytest not run), exit 2 | ✅ |
| CI-01 | triggers: push and PR to main/develop, plus workflow_dispatch | `tests/test_ci_config.py:25-27` — `set(on) == {"push","pull_request","workflow_dispatch"}`, `on["push"]["branches"] == ["main","develop"]`, same for PR | ✅ |
| CI-02 | backend matrix 3.10/3.12; install `.[dev,api]`, ruff, mypy, pytest | `tests/test_ci_config.py:31` — `matrix["python-version"] == ["3.10","3.12"]`; `:33-34` substring per command; `:35` setup-python uses `${{ matrix.python-version }}` | ✅ (substring check, see gaps) |
| CI-03 | Node 20; `frontend/` working dir; npm cache on `frontend/package-lock.json`; npm ci, vitest, tsc, build | `tests/test_ci_config.py:41` working-directory `== "frontend"`; `:43-45` node-version `"20"`, cache `"npm"`, cache-dependency-path `"frontend/package-lock.json"`; `:47-48` npm ci, npm test, npm run build; tsc and vitest through `:67-68` | ✅ |
| CI-04 | `permissions: contents: read`; concurrency group that cancels superseded runs | `tests/test_ci_config.py:52` — `== {"contents": "read"}`; `:53` — `cancel-in-progress is True`; `:54` — `"github.ref" in group` | ✅ |
| CI-05 | backend green on 3.10 in an isolated venv | `scratchpad/py310` (CPython 3.10.21, fresh install: ruff 0.17.4, mypy 2.4.1): ruff ✓, mypy ✓, pytest 120 passed | ✅ (manual evidence by design) |
| TOOL-01 | explicit ruff rule set; bounded ruff/mypy | `tests/test_ci_config.py:73-76` — regex for `select = ["E4","E7","E9","F"]` under `[tool.ruff.lint]`; `'"ruff>=0.15,<0.18"' in pyproject`; `'"mypy>=2.1,<3"' in pyproject`. Behaviour: ruff 0.17.4 (fresh) and 0.15.20 (local) both pass | ✅ |
| PKG-01 | pnpm files gone; `npm ci` succeeds from package-lock | `tests/test_ci_config.py:81-83` — `not exists()` ×2, `package-lock.json is_file()`; `npm ci` inside `make ci` → `added 318 packages` | ✅ |

**Status**: ✅ all ACs covered. No spec-precision gaps. CI-05 rests on command evidence, not a test, which tasks.md intends.

### TYPE-03 diff review (runtime-equivalence)

- `cast(...)` in `clarify.py` and `planning.py` is an identity function at runtime.
- `stats: dict[str, Any] = …` in `verify.py` and `adversarial.py` is an annotation only.
- `get_stream_writer: Optional[...]` without a value, in `audit.py`, `verify.py` and `adversarial.py`, is a bare module annotation. It adds an `__annotations__` entry and binds nothing. The `try/except ImportError` keeps doing the binding. `typing` is imported in each file, so eager evaluation is safe.
- `builtins.list[str]` in `store.py` is the same object as the builtin `list`. It only avoids the name being shadowed by `AuditStore.list` during type-checking.
- `_require()` in `routes.py:256-261` is the only change with a runtime path. It runs right after create (`:115`) or resume (`:166`) writes the record. It can only be reached if the record disappears in between, for example through a concurrent `DELETE /audits/{id}`. Before, `_summary(None)` raised `TypeError`, which the server turns into an unhandled 500. Now it is an `HTTPException(500)` with a JSON detail. The status code is the same and only the error body changes, on a path that is practically unreachable. **Judged acceptable.** A 404 or 409 would be more accurate for the race, but that would be a behavior change and is out of scope.

---

## Discrimination Sensor

The scratch copy was `scratchpad/verifier8`, made without `.git`, `.venv`, `node_modules` or `.env`. The copy's `src` was confirmed as the one imported (`auditor.__file__` resolves to the copy). Each mutant was restored after its run, and the copy was confirmed identical to the real repo afterwards.

| # | Target | Mutation | Killed by | Result |
| - | ------ | -------- | --------- | ------ |
| W1 | `ci.yml:26` | matrix `["3.12"]` (3.10 dropped) | `test_ci02` | ✅ Killed |
| W2 | `ci.yml:51` | working-directory `.` | `test_ci03` | ✅ Killed |
| W3 | `ci.yml:11-12` | `permissions` block removed | `test_ci04` | ✅ Killed |
| W4 | `ci.yml:16` | `cancel-in-progress: false` | `test_ci04` | ✅ Killed |
| W5 | `ci.yml:40-41` | `mypy src` step removed | `test_ci02` | ✅ Killed |
| W6 | `ci.yml:12` | `contents: write` | `test_ci04` | ✅ Killed |
| W7 | `ci.yml:56` | node `"18"` | `test_ci03` | ✅ Killed |
| W8 | `ci.yml:58` | cache-dependency-path `package-lock.json` | `test_ci03` | ✅ Killed |
| W9 | `ci.yml:7-8` | `pull_request` trigger removed | `test_ci01` | ✅ Killed |
| W10 | `ci.yml:9` | `workflow_dispatch` removed | `test_ci01` | ✅ Killed |
| W11 | `ci.yml:37` | install `.[dev]` (no api) | `test_ci02` | ✅ Killed |
| W12 | `ci.yml:43` | `run: echo skip # pytest -q` | `test_ci02` | ✅ Killed |
| MK1 | `Makefile:23` | `ci: lint test frontend-ci` (no typecheck) | `test_gate01` | ✅ Killed |
| MK3 | `Makefile:21` | `&& npm run build` dropped | `test_gate01` | ✅ Killed |
| PY1 | `pyproject.toml:74` | `select` line removed | `test_tool01` | ✅ Killed |
| PY2 | `pyproject.toml:35` | `ruff>=0.15` (unbounded) | `test_tool01` | ✅ Killed |
| PY3 | `pyproject.toml:36` | `mypy>=2.1` (unbounded) | `test_tool01` | ✅ Killed |
| PY5 | `pyproject.toml:32` | `httpx` removed | `test_tool01` | ✅ Killed |
| PKG1 | `frontend/` | `pnpm-lock.yaml` recreated | `test_pkg01` | ✅ Killed |
| PKG2 | `frontend/` | `pnpm-workspace.yaml` recreated | `test_pkg01` | ✅ Killed |
| PKG3 | `frontend/` | `package-lock.json` removed | `test_pkg01` | ✅ Killed |
| T1 | `clarify.py:31` | `cast` removed | mypy (2 errors) | ✅ Killed |
| T2 | `planning.py:32` | `cast` removed | mypy (4 errors) | ✅ Killed |
| T3 | `verify.py:127` | `stats` annotation removed | mypy (4) and `make ci` stops at typecheck | ✅ Killed |
| T4 | `adversarial.py:126` | `stats` annotation removed | mypy (5) | ✅ Killed |
| T5 | `routes.py:115` | `_require` → `store.get` | mypy (1) | ✅ Killed |
| T6 | `store.py:121` | `builtins.list` → `list` | mypy (1) | ✅ Killed |
| T7 | `audit.py:27` | Optional declaration removed | mypy (1) | ✅ Killed |
| S1 | `ci.yml` mypy step | `continue-on-error: true` added | — | ❌ Survived |
| S2 | `ci.yml` backend job | `if: false` added | — | ❌ Survived |
| S3 | `ci.yml:43` | `pytest -q \|\| true` | — | ❌ Survived |
| MK2 | `Makefile:17` | `-` prefix (ignore mypy failure) | — | ❌ Survived |
| PY4 | `pyproject.toml` | `extend-select = ["ALL"]` added | — | ❌ Survived (rule set silently widened) |

**Sensor depth**: lightweight, expanded (32 mutants)
**Result**: 27/32 killed. Every requested mutant was killed. The 5 survivors are "gate neutered but still present" cases that substring matching cannot see. They are low severity and listed as optional fixes.

---

## Gate Check

| Gate | Python 3.12 (`.venv`) | Python 3.10 (`scratchpad/py310`) |
| ---- | --------------------- | -------------------------------- |
| `ruff check src tests` | ✅ All checks passed (ruff 0.15.20) | ✅ All checks passed (ruff 0.17.4) |
| `mypy src` | ✅ 0 errors / 34 files (mypy 2.1.0) | ✅ 0 errors (mypy 2.4.1; also `--python-version 3.12` ✅) |
| `pytest -q` | ✅ 120 passed, 0 failed, 0 skipped | ✅ 120 passed, 0 failed, 0 skipped |
| `make ci` | ✅ exit 0 (and vitest 27 passed, tsc + vite build ✓) | n/a |

- **Test count before**: 112. **After**: 120. **Delta**: +8 (`tests/test_ci_config.py`). No tests removed or weakened.
- **CI-like run**: the suite was also run in the scratch copy with `env -i`, an empty `HOME`, no `.env` and no network (`unshare -rn`). Result: 120 passed. So the suite is offline-safe and does not depend on the local `.env` or `~/.config/auditor/.env`. The subprocess test (`tests/test_security.py:73-89`) passes when `auditor` is importable, through either the CI editable install or PYTHONPATH.

## Workflow semantics review (GitHub Actions)

- `defaults.run.working-directory: frontend` applies only to `run:` steps. `actions/setup-node`'s `cache-dependency-path` is resolved from `$GITHUB_WORKSPACE`, so `frontend/package-lock.json` is correct.
- `setup-python` with `cache: pip` and `cache-dependency-path: pyproject.toml` is supported and keys the cache on the file hash. Note that with unpinned transitive deps, a cache hit can serve stale wheels, but pip still resolves against the index, so correctness is unaffected.
- `on` → `True`: this is a PyYAML 1.1 quirk that affects only the test (`WORKFLOW[True]`, `tests/test_ci_config.py:24`). GitHub's parser reads `on` normally. The test would break, with a clear KeyError, if someone quoted `"on"`. That is acceptable.
- The concurrency group `ci-${{ github.workflow }}-${{ github.ref }}` keeps PR (`refs/pull/N/merge`) and push refs apart. `cancel-in-progress: true` also cancels superseded pushes to `main`. That is acceptable under the spec.
- `package-lock.json` is lockfileVersion 3 and every `resolved` URL is on `registry.npmjs.org` (364 entries). Linux rollup/esbuild optional binaries are present. No dependency requires Node > 20.
- `pip install -e ".[dev,api]"`: both extras exist (`pyproject.toml:29,47`), and `requires-python = ">=3.10"`.

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / surgical changes | ✅ the mypy fixes match the inline design exactly |
| No scope creep | ✅ (`pyyaml` added to `[dev]` for the new test, justified) |
| Matches patterns | ✅ |
| Spec-anchored outcome check | ✅ |
| Every test maps to an AC | ✅ each test is named after its AC; `test_frontend_build_script_includes_typecheck` covers the tsc/vitest part of GATE-01 and CI-03 |
| Guidelines | none project-specific; strong defaults applied |

**Is `tests/test_ci_config.py` reasonable?** Mostly yes. The workflow is checked through `yaml.safe_load` on structure, which is robust. The Makefile, pyproject and package.json checks are regex or exact-string matches, which are brittle to harmless reformatting (a multi-line `select`, reordered keys, a version bump to `<0.19`). They give a clear failure, though, and are cheap to update. `tomllib` is 3.11+, which explains the regex on 3.10, and `json.loads` would make the package.json check robust. Pinning exact version ranges is mild over-specification: every intentional ruff/mypy bump now also needs a test edit. That is acceptable as a deliberate trip-wire for TOOL-01.

---

## Fix Plans (optional hardening, none blocking)

1. **Neutered-gate survivors (S1–S3, MK2)**, Minor. In `tests/test_ci_config.py`, assert that no step or job has `continue-on-error` or `if:`, that `run` values equal the exact commands (no `|| true`), and that Makefile recipe lines do not start with `-`.
2. **PY4 (rule set widened via `extend-select`)**, Cosmetic. Assert that `extend-select` is absent, or parse with `tomli`/`tomllib` and compare `select` exactly.
3. **First-run risk: action and runtime age**, Minor and not test-covered. Today is 2026-11-10. Node 20 reached EOL on 2026-04-30, and GitHub has been migrating JS actions from the node20 runtime to node24. `actions/checkout@v4`, `setup-python@v5` and `setup-node@v4` are node20-runtime majors. They are expected to still run, either forced onto node24 or with deprecation annotations, but bumping to the current majors (checkout v5+, setup-python v6, setup-node v5+) and Node 22/24 for the frontend job avoids it. Python 3.10 is also past EOL (2026-10). It is still installable by setup-python, and it is the declared minimum, so keeping it in the matrix is correct. This is a spec-level decision for the user. Local frontend runs were on Node 22, and no Node 20 was available locally to confirm the frontend job under 20.
4. **Pre-existing, outside this diff**, Info. Some test imports the real app, which creates `~/.config/auditor/audits.sqlite` in `$HOME`. It is harmless on CI runners, but locally the suite touches the real user config dir.

## Requirement Traceability Update

| Requirement | Previous | New |
| ----------- | -------- | --- |
| TYPE-01..03 | Implementing | ✅ Verified |
| GATE-01 | Implementing | ✅ Verified |
| CI-01..04 | Implementing | ✅ Verified (structure; first real Actions run pending a push) |
| CI-05 | Implementing | ✅ Verified (local 3.10 venv) |
| TOOL-01 | Implementing | ✅ Verified |
| PKG-01 | Implementing | ✅ Verified |

## Summary

**Overall**: ✅ Ready, pending the first GitHub Actions run after the user commits and pushes `.github/`, which is currently untracked.
**Spec-anchored check**: 12/12 ACs matched; 0 spec-precision gaps.
**Sensor**: 27/32 killed (all requested); 5 low-severity survivors.
**Gate**: 3.12: 120 passed; 3.10: 120 passed; `make ci` exit 0.

## Re-verification (fix loop 1)

**Gates (real repo)**: ruff: all checks passed; mypy src: no issues (34 files); pytest -q: 124 passed. `make ci` not re-run (proven earlier).

| Mutant (scratch copy, tests/test_ci_config.py) | Result |
|---|---|
| `continue-on-error: true` on mypy step | killed (test:112) |
| `if: false` on backend job | killed (test:109) |
| `pytest -q \|\| true` | killed (test:124) |
| Makefile `-` prefix on mypy recipe | killed |
| `extend-select = ["ALL"]` in pyproject | killed (TOOL-01 test:72) |
| setup-node@v6 -> @v4 | killed (`_MIN_MAJOR`, test:88-91) |
| node-version "22" -> "20" | killed (test:44) |

Baseline unmutated copy passes. Tests match revised spec: CI-03 Node 22 (test:44), CI-06 / action pinning via minimum majors checkout@5, setup-python@6, setup-node@6 (test:88). Those majors are consistent with the Node-24-runtime releases as far as known; not confirmed against GitHub without network.

Gaps 1–3: **resolved** (all previous survivors now killed).

**Verdict**: ✅ Ready — 7/7 mutants killed; pending first real GitHub Actions run after the user commits `.github/`.
