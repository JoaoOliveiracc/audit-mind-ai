# Report Chat & SARIF Download Validation

**Date**: 2026-11-10
**Spec**: `.specs/features/report-chat-and-sarif/spec.md`
**Diff range**: uncommitted working tree on `develop` (after `75dba47`)
**Verifier**: independent sub-agent (author ≠ verifier); read-only on the real tree, mutations only in scratch copies under `scratchpad/verifier21/`

**Verdict**: ❌ **FAIL (minor)**. All 8 ACs have evidence and every gate is green. One mutant from the required list survived: (r), where `App` passes a hardcoded `auditId=""` to `ChatDock`. Per the checklist, a surviving mutant needs a fix task before the feature is marked done. The fix is small: one App-level test.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 `chat.py` + `CHAT_SYSTEM` | ✅ Done | `src/auditor/chat.py`, `src/auditor/prompts/templates.py:247-258` |
| T2 schemas + route | ✅ Done | `src/auditor/api/schemas.py:63-78`, `src/auditor/api/routes.py:137-161` |
| T3 SARIF download | ✅ Done | `frontend/src/components/ResultsPanel.tsx:129-131` |
| T4 ChatDock | ✅ Done | `frontend/src/components/ChatDock.tsx`, `App.tsx:226` |
| T5 E2E-04 + docs | ✅ Done | `tests/test_e2e.py:131-134`; README, SECURITY, DOCUMENTACAO, ROADMAP |

---

## Spec-Anchored Acceptance Criteria

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| CHAT-01 completed audit → 200 | `200 {"answer": <LLM text>}`, using the audit's provider/model | `tests/test_chat.py:122-124`: `r.status_code == 200`; `r.json() == {"answer": "Resposta do LLM."}`; `calls == [("anthropic", "claude-x")]` | ✅ PASS |
| CHAT-02 order: system → `<relatorio>` (summary + every title) → history (user→Human, assistant→AI) → question last | exact message types and order | `tests/test_chat.py:34-39`: `[type(m) for m in msgs] == [System, Human, Human, AI, Human]`; `msgs[0].content == CHAT_SYSTEM`; `msgs[-1].content == question`. `:43-46`: summary, `72/100`, both titles, `app.py:1`, evidence and dimension summary are in the inner context. `:25`: `startswith("<relatorio>\n") and endswith("\n</relatorio>")`. Route level: `:126-127` | ✅ PASS |
| CHAT-03 neutralize inner tags | exactly one open tag and one close tag survive | `tests/test_chat.py:54`: `text.count("</relatorio>") == 1 and text.count("<relatorio>") == 1` | ✅ PASS (only exact lowercase tags are covered; see gap 5) |
| CHAT-03 evidence ≤ 500 | truncated to 500 chars | `tests/test_chat.py:61`: `"E"*500 in inner and "E"*501 not in inner` | ✅ PASS |
| CHAT-03 context ≤ 30 000 | ≤ 30 000 chars | `tests/test_chat.py:68`: `len(inner) <= 30_000` (input ≈ 150 k chars); `:69`: most severe finding kept | ✅ PASS |
| CHAT-04 unknown → 404 | 404 | `tests/test_chat.py:134,137`: `status == 404`; `detail == "Auditoria não encontrada."` (tells it apart from a missing route) | ✅ PASS |
| CHAT-04 not completed → 409 | 409 | `tests/test_chat.py:130,134`: `running` and `error` → 409, plus the exact detail; `llm.inputs == []` | ✅ PASS (the 409 for empty state is untested; gap 3) |
| CHAT-04 provider config error → 400 | 400 | `tests/test_chat.py:149`: `status_code == 400 and "credencial ausente" in detail` | ✅ PASS |
| CHAT-04 LLM error / empty answer → 502 | 502 | `tests/test_chat.py:152-156`: `RuntimeError` → 502; `"  "` → 502 | ✅ PASS |
| CHAT-04 422 cases | empty, `"   "`, 2 001 chars, 11 turns, 4 001-char turn (plus bad role) → 422 | `tests/test_chat.py:159-168`: `status_code == 422`; `llm.inputs == []` | ✅ PASS |
| UI-01 SARIF link | href `/audits/{id}/report?format=sarif`, `download="auditoria.sarif"` | `frontend/src/components/ResultsPanel.test.tsx:20-21`: `toHaveAttribute('href', '/audits/a1/report?format=sarif')`, `toHaveAttribute('download', 'auditoria.sarif')` | ✅ PASS |
| UI-02 send → API(question, last ≤ 10 turns) → show Q + A as Markdown | call args, history slice, Markdown rendering | `ChatDock.test.tsx:27`: `toHaveBeenCalledWith('a1', 'Qual o mais grave?', [])`; `:28`: question shown; `:29`: `getByText('Senha hardcoded').tagName === 'STRONG'`; `:39-47`: second call history equals `[Q1, R:Q1]`, the 7th call has length 10, starts at `Q2` and ends at `R:Q6` | ✅ PASS at component level; ⚠️ App wiring untested (mutant r) |
| UI-03 pending disables input and button | both disabled | `ChatDock.test.tsx:64-65`: `input().toBeDisabled()`, `send().toBeDisabled()` | ✅ PASS |
| UI-03 empty question not sent | no API call | `ChatDock.test.tsx:53-55`: button disabled; `chatAudit` not called | ✅ PASS |
| UI-03 error → `role="alert"`, question kept | alert text and input value | `ChatDock.test.tsx:73-74`: `getByRole('alert')` has the error text; `input().toHaveValue('Q?')` | ✅ PASS |
| E2E-04 offline e2e chat → 200 with the fake answer | 200, `{"answer": SUMMARY}` | `tests/test_e2e.py:132-134`: `status_code == 200`; `json() == {"answer": SUMMARY}` | ✅ PASS (real route, real `build_chat_messages`, real graph state; the fake LLM ignores its input; see gap 7) |

**Status**: all ACs have evidence. No spec-precision gaps: the spec fixes the status codes and limits, and the tests assert those exact values.

---

## Discrimination Sensor

The scratch copy was proven to be the code under test. Every mutant was applied, `diff -u` against the real file showed only the intended change, and `import auditor.<mod>; print(m.__file__)` resolved to `scratchpad/verifier21/be/src/...`. Backend runs used the repo's `.venv/bin/python -m pytest tests/test_chat.py tests/test_e2e.py` with `PYTHONPATH=<copy>/src` and `HOME=<scratch>`. Frontend runs used vitest and tsc inside `scratchpad/verifier21/fe` (a copy without node_modules, with `node_modules` symlinked in).

| # | File | Mutation | Result | Killed by |
| - | ---- | -------- | ------ | --------- |
| a | `chat.py:53` | drop `_neutralize` | ✅ Killed | `test_chat03_inner_delimiters_are_neutralized` |
| b | `chat.py:52` | evidence not truncated | ✅ Killed | `test_chat03_evidence_truncated_to_500_chars` |
| c | `chat.py:54` | no 30 000 cap | ✅ Killed | `test_chat03_context_capped_at_30000_chars` |
| d | `chat.py:64` | question before history | ✅ Killed | `test_chat02_messages_order_and_roles`, `test_chat01_completed_audit_answers` |
| e | `chat.py:65` | roles swapped | ✅ Killed | `test_chat02_messages_order_and_roles` |
| f | `routes.py:143` | non-completed allowed | ✅ Killed | `test_chat04_unknown_or_not_completed[run-409]`, `[err-409]` |
| g | `routes.py:149` | settings provider/model | ✅ Killed | `test_chat01_completed_audit_answers` (`calls == [...]`) |
| h | `routes.py:158` | empty answer → 200 | ✅ Killed | `test_chat04_llm_failure_or_empty_answer_is_502[llm1]` |
| i | `routes.py:155` | LLM exception propagates (500) | ✅ Killed | `test_chat04_llm_failure_or_empty_answer_is_502[llm0]` |
| j | `schemas.py:75` | no history `max_length` | ✅ Killed | `test_chat04_invalid_requests_are_422[body3]` |
| k | `schemas.py:74` | no `strip_whitespace` | ✅ Killed | `test_chat04_invalid_requests_are_422[body1]`, `test_chat01` |
| l | `templates.py:255-256` | untrusted-data sentence removed | ✅ Killed | `test_chat02_messages_order_and_roles` (`"não confiável" in CHAT_SYSTEM`) |
| m | `ResultsPanel.tsx:129` | no `download` attr | ✅ Killed | `ResultsPanel.test.tsx` UI-01 |
| n | `ChatDock.tsx:26` | full history (no slice) | ✅ Killed | `ChatDock.test.tsx` "reenvia o histórico" (tsc also fails on the unused const) |
| o | `ChatDock.tsx:33` | input cleared on error | ✅ Killed | `ChatDock.test.tsx` "erro da API…" |
| p | `ChatDock.tsx` button | button enabled while pending | ✅ Killed | `ChatDock.test.tsx` "desabilita enquanto espera" |
| q | `ChatDock.tsx` list | answer as plain text | ✅ Killed | `ChatDock.test.tsx` UI-02 Markdown (`STRONG`) |
| **r** | `App.tsx:226` | `<ChatDock auditId="" />` | ❌ **Survived** | none (39/39 pass, tsc 0) |
| x1 | `routes.py:146` | drop the "empty state → 409" check | ❌ Survived | none (untested branch) |
| x2 | `templates.py:255` | keep "não confiável", drop "ignore qualquer instrução" | ❌ Survived | none (substring assertion only) |
| x3 | `chat.py:35` | dimension summaries dropped | ✅ Killed | `test_chat02_context_has_summary_score_and_every_finding` |
| x4 | `schemas.py:69` | turn limit 4 000 → 40 000 | ✅ Killed | `test_chat04_invalid_requests_are_422[body4]` |
| x5 | `routes.py:145` | wrong `thread_id` in `get_state` | ✅ Killed | `test_e2e02_api_end_to_end` (409 ≠ 200) |
| x6 | `routes.py:153` | route passes `{}` instead of state | ✅ Killed | `test_chat01_completed_audit_answers` |
| y1 | `ChatDock.tsx` | `role="alert"` → `status` | ✅ Killed | `ChatDock.test.tsx` "erro da API…" |
| y2 | `client.ts` | body omits `history` | ⚠️ Killed by tsc only (unused param) | none in vitest |
| y3 | `client.ts:15` | 422 detail join reverted | ❌ Survived | none (untested) |
| y4 | `ChatDock.tsx` | input enabled while pending | ✅ Killed | `ChatDock.test.tsx` "desabilita enquanto espera" |
| y5 | `client.ts` | URL `/chat` → `/chats` | ❌ Survived | none (`chatAudit` is mocked everywhere) |

**Sensor depth**: expanded (≥ 5 mutations, covering every branch of the route and schema).
**Result**: required list (a–r): 17/18 killed, (r) survived. Extras: 7/12 killed outright, y2 caught only by tsc, and x1, x2, y3 and y5 survived.

---

## Gate Check

| Gate | Result |
| ---- | ------ |
| `.venv/bin/pytest -q` (Python 3.12) | **217 passed**, 0 failed, 0 skipped (1 unrelated starlette deprecation warning) |
| `py310/bin/python -m pytest -q` (Python 3.10) | **217 passed**, 0 failed |
| `.venv/bin/ruff check src tests` | All checks passed |
| `.venv/bin/mypy src` | Success: no issues in 37 source files |
| `vitest run` | **39 passed** (7 files) |
| `tsc --noEmit -p .` | exit 0 |

- Test count before the feature: backend 198, frontend 33. After: 217 (+19), 39 (+6). No tests were deleted or weakened.
- `make ci` was not run as a whole. Its parts were run individually above.

---

## Security and Robustness Assessment

- **Host allowlist**: applies to this route. `LocalHostOnlyMiddleware` is app-wide (`api/main.py:50-52`), and the tests use `base_url="http://localhost"`. CSRF: the JSON body requires `Content-Type: application/json`, which FastAPI 0.139 enforces. A cross-origin page therefore triggers a preflight, and CORS only allows `:5173`. This is the same posture as `POST /audits`.
- **File access**: none. The route calls `llm.invoke(messages)` with no tools bound. The context comes only from checkpointed graph state, the question and history are passed as separate messages, and `audit_id` is only used as a store key and `thread_id`.
- **Prompt injection**: reasonable for a call with no tools. Report content is delimited and the system prompt marks it as untrusted. The worst realistic outcome is a misleading answer to the local user. Neutralization is exact-match only (`<relatorio>`, `</relatorio>`). `</RELATORIO>`, `</relatorio >` and `< /relatorio>` pass through unchanged (gap 5). The 30 000 truncation runs after neutralization, so it cannot reintroduce a tag (`‹` is one char, same length).
- **Cost and size limits**:
  - Input per call is bounded: about 30 k chars of context, 10 × 4 k of history, 2 k of question, plus the system prompt, roughly 73 k chars (about 20 k tokens).
  - Output is bounded by `AUDITOR_MAX_TOKENS` (default 8000) through `get_llm`.
  - There is no rate limit or per-audit quota. That is acceptable for a single-user local API.
  - Clients can forge `assistant` turns, which is harmless here because the client is the owner.
- **Provider**: `record["provider"]` and `record["model"]` are resolved and persisted at creation (`routes.py:91,113`), so the chat uses the audit's own configuration (mutant g is killed).
- **409 for empty state** (`routes.py:146`):
  - `auditor db compact` only deletes `checkpoint_ns != ''` rows and keeps the root checkpoints the route reads (`retention.py:86-96`), so compacting does not trigger it.
  - It is reachable when the checkpoint DB is deleted or replaced by hand, or when `AUDITOR_DATA_DIR` changes while metadata survives.
  - It is also reachable if `delete_audit` fails between `checkpointer.delete_thread` and `store.delete` (`retention.py:64-65`).
  - The branch is untested (x1 survived).
- **502 detail** echoes the provider exception text (`f"Falha ao consultar o LLM: {exc}"`). This is fine locally, but provider errors can be verbose.
- **422 UX**: `jsonOrThrow` joins the `msg` values of FastAPI's `detail` list with `; ` (`client.ts:14-16`). Reasonable, but untested (y3), and the messages are pydantic English (e.g. "String should have at most 2000 characters"). The UI already caps input at `maxLength={2000}` and trims, so 422 is mostly unreachable from the UI.
- **E2E-04** goes through the real stack: real `app`, real route, real `build_chat_messages` and real checkpointed state from a completed graph run. Only `_build_llm` is faked. x5 (wrong thread_id) is killed by E2E-04. The fake LLM returns `SUMMARY` whatever it receives, so E2E-04 does not prove the report text reached the LLM. The unit route test covers that (x6 killed).

---

## Code Quality

| Check | Status |
| ----- | ------ |
| Minimum code, no scope creep | ✅ Small pure module and thin route. The 422 `detail` join is a declared extra. |
| Matches patterns | ✅ Same `get_store` / `get_graph` / `get_llm` usage as `/findings` and `/resume`; `content_text` reused |
| Tests map to ACs | ✅ Every test is tagged with its AC. `test_chat03_empty_state_still_builds_a_context` and the `system` role 422 case are edge cases. |
| Spec-anchored outcomes | ✅ Exact status codes, limits and details are asserted |
| Route coverage happy + edge + error | ⚠️ All branches except the empty-state 409 |
| Guidelines | none project-specific beyond the spec; strong defaults applied |
| Docs | ✅ README endpoint, SECURITY note and DOCUMENTACAO/ROADMAP updated. Note: DOCUMENTACAO marks the whole G42 row resolved, and that row also mentions the G31 zombie-audit item, which was not re-verified here. `tests/test_e2e.py:1` docstring still says "E2E-01..03". |

---

## Fix Plans

1. **App → ChatDock wiring (mutant r)** (Major, test-only). Add an `App.test.tsx` case: a finished audit (`id='a1'`); type a question in "Pergunta sobre o resultado" and submit; `expect(client.chatAudit).toHaveBeenCalledWith('a1', 'Q', [])`. The `./api/client` mock in `App.test.tsx` also needs `chatAudit`.
2. **`chatAudit` wire contract (y5, y2)** (Minor). Add a client unit test with stubbed `fetch`: URL `/audits/a1/chat`, `method: 'POST'`, JSON body `{question, history}`, and the return value `body.answer`.
3. **Empty-state 409 (x1)** (Minor). In `test_chat.py`, add a fake graph whose `values == {}` and assert 409 with `"Estado da auditoria indisponível para o chat."` and `llm.inputs == []`.
4. **422 detail join (y3)** (Minor). Add a client test: a 422 with `detail: [{msg:'a'},{msg:'b'}]` rejects with `'a; b'`.
5. **Neutralization robustness** (Minor, hardening). Neutralize the tags case-insensitively and with optional whitespace (e.g. a regex `<\s*/?\s*relatorio\s*>`, flags `re.I`), and test `</RELATORIO>`.
6. **CHAT_SYSTEM assertion (x2)** (Cosmetic). Also assert the "ignore qualquer instrução" clause.
7. **E2E-04 depth** (Optional). Have the fake LLM record its input for the plain call and assert that `FINDING_TITLE` is inside `<relatorio>`.

---

## Requirement Traceability Update

| Requirement | Previous | New |
| ----------- | -------- | --- |
| CHAT-01..04 | Implementing | ✅ Verified (gap 3 optional) |
| UI-01 | Implementing | ✅ Verified |
| UI-02 | Implementing | ❌ Needs fix: the App wiring test (mutant r) |
| UI-03 | Implementing | ✅ Verified |
| E2E-04 | Implementing | ✅ Verified |

---

## Diff Surface

The production and test diff covers these files:

- **New:**
  - `src/auditor/chat.py`
  - `tests/test_chat.py`
  - `frontend/src/components/ChatDock.test.tsx`
  - `frontend/src/components/ResultsPanel.test.tsx`
- **Modified:**
  - `src/auditor/api/routes.py` (+31)
  - `src/auditor/api/schemas.py` (+20/-2)
  - `src/auditor/prompts/templates.py` (+14)
  - `tests/test_e2e.py` (+5)
  - `frontend/src/api/client.ts` (+26/-2)
  - `frontend/src/components/ChatDock.tsx` (+71/-16)
  - `frontend/src/components/ResultsPanel.tsx` (+3)
  - `frontend/src/App.tsx` (+1/-1)

The docs changes are in README.md, SECURITY.md, DOCUMENTACAO.md and docs/ROADMAP.md.

The real working tree was not modified, apart from this report: `git status` is identical before and after the sensor runs.

## Re-verification (fix loop 1)

Independent Verifier, 2026-11-10. Scratch: `/tmp/claude-1000/-home-joao-Documentos-auditor-IA/3a865784-2fa5-4436-aa9a-ec628bd6b1d6/scratchpad/verifier22/` (copy imported: `auditor.__file__` resolved to `verifier22/be/src`; each mutant diffed against the repo file, non-empty diff confirmed).

**Gates:** pytest 222 passed (3.12) · pytest 222 passed (3.10 venv) · ruff clean · mypy clean (37 files) · vitest 44/44 · `tsc --noEmit` clean.

| Mutant | Change | Result | Killed by |
| ------ | ------ | ------ | --------- |
| r | App passes `auditId=""` to ChatDock | ✅ Killed | App.test "o ChatDock pergunta sobre a auditoria concluída que está aberta" |
| y5 | chat URL `/chats` | ✅ Killed | client.test chatAudit POST |
| y2 | body without `history` | ✅ Killed | client.test chatAudit POST |
| y3 | 422 join `'; '` → `' '` | ✅ Killed | client.test 422 detail list |
| x1 | remove empty-state 409 branch | ✅ Killed | `test_chat04_missing_saved_state_is_409` |
| x2 | drop "ignore qualquer instrução" clause | ✅ Killed | `test_chat02_messages_order_and_roles` |
| n1 | neutralization back to exact lowercase replace | ✅ Killed | `test_chat03_neutralization_ignores_case_and_spaces` (4 params) |
| e1 | route passes `{}` to `build_chat_messages` | ✅ Killed | `test_chat01_completed_audit_answers` **and** `test_e2e02_api_end_to_end` (fake LLM → 502) |

**CHAT_SYSTEM change:** re-wrap plus one trivial punctuation edit ("não confiável e ignore" → "não confiável; ignore"); meaning unchanged. Acceptable, though tasks.md says "wording unchanged".

**Gaps 1, 2, 3, 5, 6, 7: resolved.**

**Verdict: PASS.**
