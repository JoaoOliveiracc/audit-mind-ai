# search_code Scoping Validation

**Date**: 2026-11-10
**Spec**: `.specs/features/search-code-scoping/spec.md`
**Diff surface**: uncommitted working tree: `src/auditor/tools/filesystem.py`, `src/auditor/tools/project.py`, `tests/test_tools_scoping.py`
**Verifier**: independent sub-agent (author ≠ verifier)

**Verdict**: ✅ PASS

---

## Task Completion

No `tasks.md` exists for this feature (small feature, executed in 2 steps per the traceability table). Both steps are present in the diff: step 1 (glob guard + per-file `_safe_resolve`) in `filesystem.py`, step 2 (relative `ignore_dirs` / `has_tests`) in `filesystem.py` and `project.py`.

---

## Spec-Anchored Acceptance Criteria

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| SCOPE-01: `glob` has a `..` component | string starts with `ERRO:`; no file content | `tests/test_tools_scoping.py:38-42`, parametrized with `../outside/*`, `src/../../outside/*`, `..\\outside\\*`: `out.startswith("ERRO:")`, `SECRET not in out` | ✅ PASS |
| SCOPE-02: absolute `glob` | string starts with `ERRO:`, no exception | `tests/test_tools_scoping.py:52-55`: `out.startswith("ERRO:")`, `SECRET not in out` (an exception would fail the test) | ✅ PASS |
| SCOPE-03: symlink inside root → target outside | no line from the target | `tests/test_tools_scoping.py:59-62`: `SECRET not in out`, `out == "(nenhum resultado)"` | ✅ PASS |
| SCOPE-04: symlink inside root → target inside | matches reported as `<symlink rel path>:<line>: <text>` | `tests/test_tools_scoping.py:66-69`: `set(out.splitlines()) == {"src/a.py:1: needle = 1", "src/in_link.py:1: needle = 1"}` | ✅ PASS |
| SCOPE-05: root has an ancestor named in `ignore_dirs` | project matches returned | `tests/test_tools_scoping.py:73-78` (`build`, `env`, `bin`): `_search(root, pattern="needle") == "main.py:1: needle = 1"` | ✅ PASS |
| SCOPE-06: file in an ignored dir inside the project | no matches from it | `tests/test_tools_scoping.py:82-87`: `== "app.js:1: needle = 2"` (`node_modules/x.js` excluded) | ✅ PASS |
| SCOPE-07: root has an ancestor named in `TEST_HINTS`, no test path inside | `has_tests == False` | `tests/test_tools_scoping.py:91-95`: `detect_stack(...).has_tests is False` | ✅ PASS |
| SCOPE-08: project has `tests/test_x.py` | `has_tests == True` | `tests/test_tools_scoping.py:98-102`: `detect_stack(...).has_tests is True` | ✅ PASS |

**Status**: ✅ 8/8 ACs covered; every assertion targets the exact spec outcome. No spec-precision gaps. The spec does not fix the `ERRO:` message text, and the tests correctly assert only the prefix.

---

## Edge Cases

- [x] `..` only inside a name (`**/*..py`) is not rejected: `tests/test_tools_scoping.py:45-48`, `out == "src/weird..py:1: needle = 2"`.
- [x] `\` separators with `..` (`..\\outside\\*`) are rejected: `tests/test_tools_scoping.py:38` (third param).

---

## Discrimination Sensor

Run in a scratch copy (`scratchpad/verifier/`). An in-test check confirmed that `auditor.__file__` resolved to the copy's `src/`. The real tree was never modified.

| # | Location | Mutation | Killed? |
| - | -------- | -------- | ------- |
| a | `filesystem.py:87` | Remove the `..` component check (keep only `is_absolute`) | ✅ Killed (3 tests: all SCOPE-01 params) |
| b | `filesystem.py:87` | Remove the `is_absolute()` check | ✅ Killed (`test_absolute_glob_is_rejected`; pathlib raises `NotImplementedError`) |
| c | `filesystem.py:97-100` | Remove the per-file `_safe_resolve` symlink check | ✅ Killed (`test_symlink_to_outside_is_not_searched`) |
| d | `filesystem.py:102` | `ignore_dirs` check back to absolute `path.parts` | ✅ Killed (3 tests: SCOPE-05 build/env/bin) |
| e | `project.py:83` | `has_tests` back to absolute `path.parts` | ✅ Killed (`test_has_tests_ignores_ancestor_named_tests`) |
| f | `filesystem.py:87` | `..` check becomes a substring check (`".." in glob`) | ✅ Killed (`test_dotdot_inside_a_name_is_not_a_traversal`) |
| g | `filesystem.py:87` | Split only on `/` (drop `\`) | ✅ Killed (`[..\\outside\\*]` param) |

**Sensor depth**: lightweight+ (7 manual mutants, all branches of the new code)
**Result**: 7/7 killed: ✅ PASS

---

## Adversarial Probes (scratch copy, outside the test suite)

| Input | Result |
| ----- | ------ |
| Directory symlink to outside (`dirlink/*`, `dirlink/**`, `rootlink/**/*`, default `**/*`) | No secret returned (blocked by per-file `_safe_resolve`) |
| Symlink loop back to root (`src/inner -> root`) | No error, no escape |
| `**/..`, `*/../*`, `**/*/..`, `src/./../../outside/*` | `ERRO:` |
| Wildcards that could match `..` (`[.][.]/outside/*`, `?./outside/*`, `.[.]/outside/*`) | No results (scandir never yields `..`; the per-file check would catch it anyway) |
| `~/*`, `C:\x\*`, `\\server\share\*`, NUL byte | No results, no exception (treated as literal relative names on POSIX) |
| Root is itself a symlink / root is relative `Path(".")` | Matches returned correctly |
| `glob=""` | ⚠️ raises `ValueError: Unacceptable pattern` (pre-existing, outside the spec) |
| `glob="."` | ⚠️ raises `IndexError` (pre-existing, outside the spec) |

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ (+10/-1, +1/-1) |
| Surgical changes | ✅ only `search_code` and one `detect_stack` line |
| No scope creep | ✅ out-of-scope items (G34 `os.walk`, ignore lists) untouched |
| Matches patterns | ✅ reuses `_safe_resolve`; `ERRO:` string convention |
| Spec-anchored outcome check | ✅ |
| Coverage expectation (1:1 AC mapping) | ✅ |
| Every test maps to an AC or edge case | ✅ (each test is labeled with its SCOPE id) |
| Documented guidelines | none feature-specific; strong defaults applied |

Nit: `path.relative_to(root)` is computed up to three times per file in `search_code`. This is cosmetic and does not need a fix.

---

## Gate Check

- **Command**: `.venv/bin/pytest -q` ; `.venv/bin/ruff check .`
- **Result**: 38 passed, 0 failed, 0 skipped; ruff: All checks passed
- **Test count before feature**: 25 (38 − 13 new)
- **Test count after feature**: 38
- **Delta**: +13 (all in `tests/test_tools_scoping.py`); no existing test file modified (`git status` shows only the new file under `tests/`)

---

## Non-blocking Observations (ranked)

1. **Pre-existing exceptions on degenerate globs** (`""` → `ValueError`, `"."` → `IndexError`). These are outside the spec, which requires no-raise only for absolute globs. The impact is low: `create_react_agent`'s `ToolNode` turns tool exceptions into error messages by default. A follow-up could catch `(ValueError, NotImplementedError, IndexError)` around `root.glob` and return `ERRO:`.
2. **Test gap: no test for a directory symlink pointing outside.** The probe shows it is blocked, and mutant c would also cover it. A regression test (`src/d -> ../outside/`) would make it explicit.
3. **Not covered by design** (consistent with `read_file`): hard links to outside files, and a TOCTOU window between the `_safe_resolve` check and `open`. Both need an attacker with local filesystem write access, so they are outside this threat model.
4. **Windows portability** (not a supported target here): `Path("\\x").is_absolute()` is False on Windows. pathlib would then raise `NotImplementedError` and not escape, and the per-file check still applies.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| SCOPE-01..08 | Pending | ✅ Verified |

---

## Summary

**Overall**: ✅ Ready
**Spec-anchored check**: 8/8 ACs matched spec outcome, 0 spec-precision gaps; 2/2 edge cases covered
**Sensor**: 7/7 mutations killed
**Gate**: 38 passed, ruff clean
