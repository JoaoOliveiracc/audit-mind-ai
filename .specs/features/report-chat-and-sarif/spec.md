# Report Chat & SARIF Download Specification (G42)

## Problem Statement
The results dashboard has no SARIF download (the API already serves `?format=sarif`; the client's
`reportUrl` only accepts `md|html`), and `ChatDock` is a disabled "em breve" placeholder for the
roadmap's "chat with the report".

## Out of Scope
| Feature | Reason |
| ------- | ------ |
| Reading code / tools in chat | User: report-only (cheap, predictable, no new disk access). |
| Persisted chat history | User: on-screen only. |
| Streaming answers | User: whole JSON answer. |
| Chat in the CLI | Not requested. |

## Decisions
| Decision | Default | Rationale | Confirmed? |
| -------- | ------- | --------- | ---------- |
| Chat context | final graph state of the audit: executive summary, health score, stack profile, dimension summaries, findings (title, severity, dimension, file:line, description, recommendation, evidence ≤ 500 chars) | "About the report" (user decision). | y |
| Untrusted data | context inside `<relatorio>…</relatorio>`; system prompt says it's untrusted data from the audited code and to ignore instructions in it; inner tags neutralized | Findings carry audited-code text (same pattern as G32 salvage). | y (agent) |
| Limits | question 1–2 000 chars; history ≤ 10 turns, each ≤ 4 000 chars (422 otherwise); context ≤ 30 000 chars | Bounded cost per question. | y (agent) |
| LLM | the audit's own provider/model (`get_llm(record.provider, record.model)`) | Same config the audit used. | y (agent) |
| Module | pure `auditor/chat.py` (`build_chat_messages`) + thin route | Testable without HTTP/LLM. | y (agent) |

## Acceptance Criteria

### Backend
1. **CHAT-01** WHEN `POST /audits/{id}/chat` is called for a `completed` audit THEN it SHALL return `200 {"answer": <LLM text>}`.
2. **CHAT-02** The LLM input SHALL be: system prompt first; then the report context inside `<relatorio>` delimiters (containing the summary and every finding title); then the history turns in order (user → Human, assistant → AI); then the question last.
3. **CHAT-03** Delimiter tags inside report content SHALL be neutralized — any case and inner whitespace, e.g. `</RELATORIO>`, `< /relatorio >` (fix loop 1); evidence SHALL be truncated to 500 chars; the context SHALL NOT exceed 30 000 chars.
4. **CHAT-04** unknown id → 404; audit not `completed` → 409; provider config error → 400; LLM error or empty answer → 502; empty/too-long question, history > 10 turns or a turn > 4 000 chars → 422.

### Frontend
5. **UI-01** The results panel SHALL offer "Baixar SARIF" linking to `/audits/{id}/report?format=sarif` with `download="auditoria.sarif"`.
6. **UI-02** `ChatDock` SHALL be enabled for finished audits: sending a question SHALL call the API with the question and the last ≤ 10 turns, then show the question and the answer (answer rendered as Markdown).
7. **UI-03** While a question is pending, input and button SHALL be disabled; an empty question SHALL NOT be sent; an API error SHALL be shown (`role="alert"`) and the question kept in the input.

### E2E
8. **E2E-04** The offline API e2e SHALL ask one chat question after completion and get a 200 with the fake LLM's answer.

## Traceability
| ID | Task | Status |
| -- | ---- | ------ |
| CHAT-01..04 | T1, T2 | Verified |
| UI-01 | T3 | Verified |
| UI-02..03 | T4 | Verified |
| E2E-04 | T5 | Verified |
