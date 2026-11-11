# Web UI Internationalization Specification (G50)

## Problem Statement

The web UI (`frontend/`) has about 250 Portuguese strings hard-coded in 14 files (labels, buttons,
aria-labels, status, severities, errors), and `index.html` declares `lang="pt-BR"`. That limits the
product to Portuguese speakers and makes adding another language a rewrite. The goal is a global
UI: English by default, Brazilian Portuguese kept as an option, and a third language added later by
creating one catalog file.

## Goals

- [ ] Every UI string the frontend owns comes from a typed message catalog. Zero Portuguese
      literals remain in components.
- [ ] English is the default language; pt-BR is kept with the same coverage (the build fails if a key is missing).
- [ ] The language is chosen automatically from the browser, can be changed in the UI, and the choice persists.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Backend text (LLM questions/findings/summary, scan status line, API error `detail`, MD/HTML reports, CLI) | User decision: "front agora, backend depois". This becomes a separate feature (audit `language`). |
| Languages other than `en` and `pt-BR` | Not requested; the architecture makes them a one-file addition. |
| Translating code comments and test names | Not user-visible. |
| RTL layout | No RTL language planned. |
| i18n library (react-i18next, FormatJS) | ~250 strings and 2 locales; a typed in-house catalog gives compile-time key parity with no dependency (see design). |
| Server-side language negotiation (`Accept-Language`) | The UI is a static SPA; detection happens in the browser. |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Model | i18n with `en` (default) + `pt-BR` | User decision. | y |
| Scope | frontend only; backend later | User decision. | y |
| Detection order | saved choice → first supported `navigator.languages` entry (`pt*` → `pt-BR`, `en*` → `en`) → `en` | Brazilians keep Portuguese without touching anything; everyone else gets English. Any `pt-*` maps to `pt-BR` because it is the only Portuguese catalog. | y (agent) |
| Persistence | `localStorage` key `auditor.locale`; read/write errors ignored | Per-browser preference; private mode must not break the UI. | y (agent) |
| Selector | compact `EN / PT` toggle in the header, `aria-label` "Language" in both languages | One control, discoverable and accessible. | y (agent) |
| Backend strings on the page | shown as received (Portuguese) | Out of scope; the UI never translates server text. | y (agent) |
| Page title | `Audit Mind AI` (product name in README/docs) in every language | The current `Auditor-IA` is the Portuguese working name. | y (agent) |
| Plurals | `Intl.PluralRules` of the active locale | Correct for `en` and `pt-BR`, and for future languages. | y (agent) |
| Test locale | tests render in `en` (the default). pt-BR is covered by dedicated tests | The suite asserts the product default. | y (agent) |
| Clarify "skipped" answer `(sem resposta)` | kept as a protocol constant `NO_ANSWER` sent to the backend (same value as the CLI); not UI text | The LLM consumes it with Portuguese prompts; it follows the audit language in the backend feature. | y (agent) |
| Vite dev proxy missing `/defaults` (G48 bug found while reading `vite.config.ts`) | fixed in passing (one route added) | Without it, `make dev` never applies `AUDITOR_VULN_SCAN` to the checkbox. | y (agent) |
| Severity, status and tier names | translated in the UI; API keys (`critical`, `running`…) stay unchanged | Keys are protocol, labels are presentation. | y (agent) |

**Open questions:** none — all resolved or logged above.

---

## User Stories

### P1: English-first UI with typed catalogs ⭐ MVP

**User Story**: As a non-Portuguese-speaking engineer, I want the whole web UI in English, so that I can run and read audits without translating the interface.

**Acceptance Criteria**:

1. **I18N-01** WHEN the app renders with locale `en` THEN every string the frontend owns SHALL come
   from the `en` catalog: visible text, `aria-label`, `title`, `placeholder`, severity, status and
   score-tier labels, and client-side errors (e.g. `sse.ts` lost connection).
2. **I18N-02** The `pt-BR` catalog SHALL be typed against the `en` catalog's shape, so that a
   missing or extra key fails `tsc` (and therefore `make ci`).
3. **I18N-03** No component, state or API module under `frontend/src/` (excluding `i18n/` and
   `*.test.*`) SHALL contain a Portuguese literal. A test SHALL fail if any non-catalog source file
   contains `[áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]` outside comments.
4. **I18N-04** WHEN a message depends on a count (achado(s), arquivo(s)…) THEN it SHALL use the
   locale's plural rules. Examples: `en` "1 finding" / "2 findings"; `pt-BR` "1 achado" / "2 achados".
5. **I18N-05** `index.html` SHALL declare `lang="en"`, and the title SHALL be `Audit Mind AI`.

**Independent Test**: render `App` with no saved choice and `navigator.language = 'en-US'`. The UI
is in English and `document.documentElement.lang === 'en'`.

---

### P1: Language detection, switch and persistence ⭐ MVP

**User Story**: As a Brazilian user, I want the UI to open in Portuguese and let me switch languages, so that the change doesn't cost me anything.

**Acceptance Criteria**:

1. **LOC-01** WHEN there is no saved choice THEN the locale SHALL be taken from the first
   *supported* entry of `navigator.languages` (fallback `[navigator.language]`), case-insensitive:
   `pt*` → `pt-BR`, `en*` → `en`; unsupported entries are skipped; none supported → `en`
   (e.g. `['es-ES','pt-BR']` → `pt-BR`; `['en-US','pt-BR']` → `en`).
2. **LOC-02** WHEN `localStorage['auditor.locale']` is `en` or `pt-BR` THEN it SHALL win over the
   browser. Any other saved value SHALL be ignored, falling back to LOC-01.
3. **LOC-03** WHEN the user activates the header toggle THEN the whole UI SHALL re-render in the
   other language without a reload or losing state (a running audit's timeline, form inputs, chat
   history), and the choice SHALL be saved to `auditor.locale`.
4. **LOC-04** WHEN the locale changes (including at startup) THEN `document.documentElement.lang`
   SHALL be set to the active locale (`en` or `pt-BR`).
5. **LOC-05** WHEN `localStorage` throws on read or write THEN the app SHALL still render, using
   LOC-01, and the toggle SHALL still work for the session.
6. **LOC-06** The toggle SHALL be a button showing the *other* language (`PT` while in `en`, `EN`
   while in `pt-BR`), with an accessible name that starts with that visible text (WCAG 2.5.3):
   `PT — switch language to Português (current: English)` /
   `EN — mudar idioma para English (atual: Português)`.

**Independent Test**: with `navigator.language = 'pt-BR'`, the UI opens in Portuguese. Clicking
`EN` switches to English, and after a remount it stays English.

---

### P2: Docs

1. **DOC-02** README / docs/USAGE (web section) SHALL mention the language behavior (default,
   detection, toggle, backend content still Portuguese), and `DOCUMENTACAO.md` §10.3 SHALL gain a
   resolved G50 row plus a follow-up note for the backend language feature.

---

## Edge Cases

- WHEN `navigator.languages` is empty or undefined THEN use `navigator.language`; if both are missing → `en`.
- WHEN `navigator.language` is `pt-PT` or `pt` THEN `pt-BR` (the only Portuguese catalog).
- WHEN a count is 0 THEN plural rules apply (`en` "0 findings"; `pt-BR` "0 achados" — `Intl` `pt` maps 0 to "one", so the catalog SHALL define 0 explicitly as plural in pt-BR).
- WHEN the server sends a status/severity key the catalog doesn't know THEN the raw key is shown (current behavior).
- WHEN the toggle is used while a clarify form has typed answers THEN the answers are kept (LOC-03).

Implicit dimensions: input validation (saved locale value → LOC-02), failure (storage → LOC-05).
The remaining dimensions are N/A for this scope: client-only presentation, no new I/O, auth or concurrency.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| I18N-01 | P1: English-first UI | Execute | Done |
| I18N-02 | P1: English-first UI | Execute | Done |
| I18N-03 | P1: English-first UI | Execute | Done |
| I18N-04 | P1: English-first UI | Execute | Done |
| I18N-05 | P1: English-first UI | Execute | Done |
| LOC-01 | P1: Detection & switch | Execute | Done |
| LOC-02 | P1: Detection & switch | Execute | Done |
| LOC-03 | P1: Detection & switch | Execute | Done |
| LOC-04 | P1: Detection & switch | Execute | Done |
| LOC-05 | P1: Detection & switch | Execute | Done |
| LOC-06 | P1: Detection & switch | Execute | Done |
| DOC-02 | P2: Docs | Execute | Done |

**Coverage:** 12 total, 12 mapped to tasks (see tasks.md).

---

## Success Criteria

- [ ] An English speaker can run a full audit in the web UI without seeing a Portuguese label the frontend owns.
- [ ] Adding a language = one new catalog file + one entry in the locale list. `tsc` lists every missing key.
- [ ] A Brazilian user's experience is unchanged on first open (auto pt-BR).

## Review log
- 2026-11-11 code review (Execute, 7 of 10 applied): every count string uses plural rules
  (pt-BR "1 confirmado", "1 arquivo"); severity/status/tier maps keep fixed keys (tsc parity) with
  `labelOf` for server keys; toggle accessible name starts with the visible text (LOC-06 updated);
  `<html lang>` set before first paint (`useLayoutEffect`); LOC-01 picks the first *supported*
  preference; client errors routed through notices (`fetch` TypeError → translated `network_error`,
  no `Error:` prefix, `HTTP <status>` when statusText is empty); guard test's i18n-exclusion check made real.
  Not applied (user decisions / documented): `(sem resposta)` protocol value and server-provided
  text stay Portuguese until the backend language feature; accent-based guard stays a heuristic.
- 2026-11-11 Verifier PASS (17/21 mutants) → fix loop 1: per-component en + pt-BR copy tests
  (`i18n/components-pt.test.tsx`: FolderPicker, ClarifyForm, ChatDock, History status labels,
  ResultsPanel — kills hard-coded English, M12b/M19); `api/sse.test.ts` (connection_lost code, M17);
  docs wording aligned with LOC-01 (first *supported* preference).
