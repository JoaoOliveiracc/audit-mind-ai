# Report Chat & SARIF Download Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement with the `tlc-spec-driven` skill (Execute flow + Critical Rules). If it cannot be activated, STOP and tell the user.

**Spec**: `.specs/features/report-chat-and-sarif/spec.md` · **Status**: Done

## Design (inline)
- `src/auditor/chat.py`: `CHAT_SYSTEM` (in `prompts/templates.py`), `build_report_context(values) -> str` (caps + neutralization), `build_chat_messages(values, history, question) -> list[BaseMessage]`.
- `api/schemas.py`: `ChatTurn(role: Literal["user","assistant"], content: constr(max_length=4000))`, `ChatRequest(question: constr(min_length=1, max_length=2000, strip), history: list[ChatTurn] (max 10))`, `ChatResponse(answer)`.
- `api/routes.py`: `POST /audits/{id}/chat` → 404/409/400/502 per spec; state from `get_graph().get_state(...)`.
- Frontend: `client.chatAudit(id, question, history)`, `reportUrl(…, 'sarif')`; `ChatDock({auditId})` with local turns state; `ResultsPanel` SARIF link; `App` passes `auditId`.

## Tests
`tests/test_chat.py` (unit + route, fake LLM capturing input), `frontend/src/components/ChatDock.test.tsx`, `frontend/src/components/ResultsPanel.test.tsx`, append to `tests/test_e2e.py::test_e2e02`.

## Gate
Quick `.venv/bin/pytest -q` · Full `./node_modules/.bin/vitest run && ./node_modules/.bin/tsc --noEmit -p .` · Build `make ci`

## Tasks
- **T1** `chat.py` + prompt (CHAT-02, CHAT-03) · `feat(chat): build report-grounded chat messages`
- **T2** schemas + route (CHAT-01, CHAT-04) · `feat(api): POST /audits/{id}/chat`
- **T3** SARIF download (UI-01) · `feat(frontend): SARIF download button (G42)`
- **T4** ChatDock (UI-02, UI-03) · `feat(frontend): chat with the report (G42)`
- **T5** E2E-04 + docs (README endpoints, DOCUMENTACAO G42 ✅, SECURITY untrusted-data note, ROADMAP) · `test+docs: chat e2e and docs (G42)`

## Execution notes
- Own test fixes during execution: (1) CHAT-04 404 case would pass with no route (FastAPI 404) → now also asserts the `detail`; (2) ChatDock history expectation: with 12 messages the last 10 start at `Q2` (two oldest drop, not one); (3) `Array.prototype.at` not in the TS lib target → indexing.
- Implementation choice: the send button keeps the label "Enviar" while pending (accessible name stable); disabled state signals pending (spec only requires disabled).
- Extra: `jsonOrThrow` joins FastAPI 422 `detail` lists into a readable message (was `[object Object]`).
- Suite: backend 198 → 217 (+19), frontend 33 → 39 (+6); E2E-04 added inside `test_e2e02`.

## Fix loop 1 (after Verifier FAIL minor — mutant r survived)

| Gap | Fix | Test |
| --- | --- | ---- |
| 1 App → ChatDock wiring (r) | — | `App.test.tsx` "o ChatDock pergunta sobre a auditoria concluída que está aberta" |
| 2 chatAudit request untested (y5, y2) + 422 join (y3) | — | `frontend/src/api/client.test.ts` (stubbed `fetch`: URL, method, headers, body; 502 text; 422 list) |
| 3 empty-state 409 untested (x1) | — | `test_chat04_missing_saved_state_is_409` |
| 5 neutralization exact-lowercase only | case-insensitive regex with inner whitespace (spec CHAT-03 updated) | `test_chat03_neutralization_ignores_case_and_spaces` |
| 6 CHAT_SYSTEM substring (x2) | also asserts "ignore qualquer instrução" (prompt line re-wrapped so the phrase isn't split; wording changed slightly: "não confiável e ignore" → "não confiável; ignore" — same meaning. Correction recorded after the Verifier pointed out that "wording unchanged" was inaccurate.) | `test_chat02_messages_order_and_roles` |
| 7 E2E-04 didn't prove report reaches the LLM | fake LLM raises if a `<relatorio>` call lacks the finding title | `test_e2e02` |
| Docs | e2e docstring; G42 row resolution text notes the G31/vite items were resolved elsewhere | — |
