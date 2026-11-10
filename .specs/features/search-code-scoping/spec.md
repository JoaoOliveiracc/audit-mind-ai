# search_code Scoping Specification

## Problem Statement

`search_code` (the investigators' grep tool) does not enforce the project-root boundary that
`read_file`/`list_directory` enforce: a `glob` containing `..` or an outbound symlink reads files
outside the audited project and sends their contents to the LLM provider (G25/G26 — reproduced).
It also compares `ignore_dirs` against the **absolute** path, so a project located under any
ancestor directory named `build`, `bin`, `env`, … returns no results at all; `detect_stack` has
the same flaw for `has_tests` (G30 — reproduced). See `DOCUMENTACAO.md` §10.3.

## Goals

- [ ] No `search_code` call can return content from a file whose real path is outside the root.
- [ ] Ignore rules and test detection depend only on the path **relative to the root**.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Replacing `root.glob` with a pruned `os.walk` (G34, performance) | Separate perf item; not needed for correctness. |
| Changing `read_file`/`list_directory` | Already scoped correctly (`_safe_resolve`). |
| Changing ignore lists / `TEST_HINTS` contents | Behavior change unrelated to the bugs. |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| How to signal an invalid `glob` | Return a string starting with `ERRO:` (no exception) | Matches the existing tool error convention (`ERRO: regex inválida`, `ERRO: Acesso negado`), which the ReAct agent reads as tool output. | y (convention) |
| Symlink inside the root pointing to another file inside the root | Still searched; reported under the symlink's own relative path | Content stays inside the boundary; matches `_safe_resolve` semantics used by `read_file`. | y |
| Symlink pointing outside the root | Silently skipped (no error line) | A search is a scan over many files; one escaped link must not abort the scan. | y |
| Where the `ignore_dirs` check applies | To the path relative to the root (the root itself and its ancestors never count) | That is what "ignore build/dependency dirs inside the project" means. | y |

**Open questions:** none — all resolved or logged above.

---

## User Stories

### P1: Root-confined code search ⭐ MVP

**User Story**: As an operator auditing an untrusted repository, I want `search_code` to only ever
read files inside the project root so that no external file content leaks to the LLM provider,
even under prompt injection.

**Acceptance Criteria**:

1. **SCOPE-01** WHEN `glob` contains a `..` path component (e.g. `../outside/*`, `src/../../x/*`)
   THEN `search_code` SHALL return a string starting with `ERRO:` and SHALL NOT include content from
   any file.
2. **SCOPE-02** WHEN `glob` is an absolute path (e.g. `/etc/*`) THEN `search_code` SHALL return a
   string starting with `ERRO:` (and SHALL NOT raise).
3. **SCOPE-03** WHEN a file inside the root is a symlink whose real target is outside the root THEN
   `search_code` SHALL NOT return any line from that target.
4. **SCOPE-04** WHEN a file inside the root is a symlink whose real target is inside the root THEN
   `search_code` SHALL still report matches from it, as `<symlink relative path>:<line>: <text>`.

**Independent Test**: project with `src/link.txt → ../outside/s.txt` and a secret in `s.txt`:
searching the secret with the default glob and with `glob="../outside/*"` returns no secret.

### P1: Ignore rules relative to the root ⭐ MVP

**User Story**: As a user whose projects live under folders like `~/build/` or `~/env/`, I want
search and stack detection to behave the same regardless of where the project sits on disk.

**Acceptance Criteria**:

1. **SCOPE-05** WHEN the project root has an ancestor directory whose name is in `ignore_dirs`
   (e.g. `…/build/proj`) THEN `search_code` SHALL return the matches from files inside the project.
2. **SCOPE-06** WHEN a file is inside an ignored directory **within** the project (e.g.
   `node_modules/x.js`) THEN `search_code` SHALL NOT return matches from it (existing behavior kept).
3. **SCOPE-07** WHEN the project root has an ancestor directory named in `TEST_HINTS` (e.g.
   `…/tests/proj`) and the project itself contains no test path THEN `detect_stack` SHALL report
   `has_tests == False`.
4. **SCOPE-08** WHEN the project contains a test directory (e.g. `tests/test_x.py`) THEN
   `detect_stack` SHALL report `has_tests == True` (existing behavior kept).

---

## Edge Cases

- WHEN `glob` contains `..` only as part of a name (e.g. `**/*..py`) THEN it SHALL NOT be rejected
  (only a whole `..` component is a traversal). — covered by SCOPE-01 definition.
- WHEN `glob` uses `\` separators with `..` (e.g. `..\\x\\*`) THEN SHALL be rejected like SCOPE-01.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| SCOPE-01 | P1: Root-confined search | Execute (step 1) | Verified |
| SCOPE-02 | P1: Root-confined search | Execute (step 1) | Verified |
| SCOPE-03 | P1: Root-confined search | Execute (step 1) | Verified |
| SCOPE-04 | P1: Root-confined search | Execute (step 1) | Verified |
| SCOPE-05 | P1: Relative ignore rules | Execute (step 2) | Verified |
| SCOPE-06 | P1: Relative ignore rules | Execute (step 2) | Verified |
| SCOPE-07 | P1: Relative ignore rules | Execute (step 2) | Verified |
| SCOPE-08 | P1: Relative ignore rules | Execute (step 2) | Verified |

**Coverage:** 8 total, 8 mapped to steps, 0 unmapped.

## Success Criteria

- [x] The G25/G26/G30 reproductions from the 2026-11-10 analysis no longer reproduce.
- [x] Full gate green: `pytest`, `ruff`; no existing test modified or removed.
