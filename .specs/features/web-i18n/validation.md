# G50 web-i18n — Validation (independent Verifier)

**Verdict: PASS** (12/12 ACs evidenced; 4 sensor survivors, all test-coverage gaps on behaviour that is currently implemented correctly — none is a spec violation).

- Diff range: working tree (uncommitted) on top of `HEAD = dcb125d` (branch `develop`); 29 files changed, +277/−231, plus untracked `frontend/src/i18n/`, `components/LanguageToggle.tsx`, `.specs/features/web-i18n/`.
- Gates (run in `frontend/`): `./node_modules/.bin/vitest run` → **119/119 passed** (12 files); `./node_modules/.bin/tsc --noEmit` → **exit 0**. Re-run after the sensor: identical.
- Tree integrity: `git status --short` and `git diff --stat` recorded before and after the sensor are byte-identical; each mutated file was restored from a backup and verified with `cmp`.

## Per-AC evidence

| AC | Evidence (test → asserted value) | Matches spec? |
| -- | -------------------------------- | ------------- |
| I18N-01 | `locale-ui.test.tsx` "I18N-01" block: SSE `connection_lost` code → "Connection to the server was lost." / "Conexão com o servidor perdida."; server text shown raw; severity "Critical"/"Crítico", "confidence 80%"/"confiança 80%", health aria "Health score: 40 out of 100 (critical)" / "Pontuação de saúde: 80 de 100 (saudável)"; timeline steps pt. `i18n.test.ts`: TypeError → `network_error` text in both locales, no "Error:" prefix, unknown server key raw (incl. `toString`). Existing component tests assert English copy (StartForm, History, Timeline, ResultsPanel, ChatDock). Manual scan of all non-catalog `.ts/.tsx`: no user-visible literal outside catalogs except product name `Audit Mind AI` (h1) and protocol `NO_ANSWER = '(sem resposta)'` (documented). | Yes (pt-BR rendering not asserted for FolderPicker, ClarifyForm, ChatDock, ResultsPanel, History status — see gaps) |
| I18N-02 | `ptBR: Messages` in `pt-BR.ts`; sensor M14 (removed `finding.recommendation`) → `tsc` TS2741. Runtime deep shape equality incl. function arity + no empty strings. | Yes |
| I18N-03 | `no-literals.test.ts`: scans >15 files, includes `Timeline.tsx`, excludes `i18n/` (real check), self-test with planted literal; sensor M12 killed by the guard. | Yes (heuristic, accent-only by design) |
| I18N-04 | `i18n.test.ts`: en "0 findings"/"1 finding"/"2 findings"; pt-BR "0 achados"/"1 achado"/"2 achados"; all pt count strings at 0/1/2 (confirmado, descartado, refutado, incerto/julgado, arquivo); `Intl` fallback without `zero`. Sensor M13 killed. | Yes |
| I18N-05 | `locale-ui.test.tsx` reads `index.html?raw`: `<html lang="en"`, `<title>Audit Mind AI</title>`. File confirmed. | Yes |
| LOC-01 | Matrix: `['pt-BR','en']`→pt-BR, `PT-pt`→pt-BR, `pt`→pt-BR, `['en-US','pt-BR']`→en, **`['es-ES','pt-BR']`→pt-BR**, `['es-ES','fr']`→en, `[]`+`language:'pt-BR'`→pt-BR, `de-DE`→en, `{}`/`undefined`→en. App-level en-US and pt-BR. Sensors M03, M04 killed. | Yes |
| LOC-02 | Valid `en`/`pt-BR` beat browser; invalid `fr`,`pt`,`EN`,`''`,`pt-br` ignored (both browser directions); App-level saved `en` vs pt browser, saved `fr` ignored. Sensors M01, M02 killed. | Yes |
| LOC-03 | App test: path input value kept across toggle, History count kept, `localStorage['auditor.locale']==='pt-BR'`, remount stays pt; displayed notice re-translates. Sensors M06, M09b killed. | Yes (timeline/clarify-answers/chat-history preservation not individually asserted; provider-above-App structure covers them) |
| LOC-04 | `<html lang>` `en` / `pt-BR` at startup and after toggle (`useLayoutEffect`). Sensor M07 killed. | Yes |
| LOC-05 | Unit: throwing getItem → browser; throwing setItem doesn't propagate; App: `Storage.prototype` get/set throw → renders pt by browser, toggle works. Sensors M05, M10 killed. | Yes |
| LOC-06 | Text `PT` in en / `EN` in pt; accessible name exactly "PT — switch language to Português (current: English)" / "EN — mudar idioma para English (atual: Português)". Sensor M08 killed. | Yes (matches review-log update) |
| DOC-02 | README "Language" paragraph; docs/USAGE "Web interface language"; DOCUMENTACAO §10.3 row `~~G50~~ ✅` with "Pendente (próxima feature): idioma da auditoria no backend", header ranges G25–G50; `/defaults` proxy noted. | Yes (wording imprecision, see gaps) |

## Discrimination sensor (one fault at a time, restored + `cmp` each)

| ID | Fault | Result |
| -- | ----- | ------ |
| M01 | `detectLocale` ignores saved choice | KILLED (3) |
| M02 | any saved non-empty value accepted | KILLED (5) |
| M03 | any non-`en` entry → pt-BR | KILLED (3) |
| M04 | supported-entry loop stops after first entry | KILLED (`['es-ES','pt-BR']`) |
| M05 | `getItem` throw propagates | KILLED (2) |
| M06 | `setLocale` doesn't persist | KILLED |
| M07 | `<html lang>` not updated | KILLED (3) |
| M08 | toggle shows current language | KILLED |
| M09 | `main.tsx` App gets random key | SURVIVED (main.tsx not under test; benign — key evaluated once) |
| M09b | provider remounts children on locale (`key={locale}`) | KILLED (2) |
| M10 | `setItem` throw propagates | KILLED |
| M11 | StartForm submit hard-coded "Start audit" | KILLED (4) |
| M12 | HealthStamp tier hard-coded Portuguese (accented) | KILLED (guard + UI) |
| M12b | History status shown as raw key (no translation) | **SURVIVED** |
| M13 | pt-BR zero plural removed | KILLED |
| M14 | pt-BR catalog key removed | KILLED (tsc TS2741) |
| M15 | ChatDock send hard-coded "Enviar" (non-accent pt) | KILLED (6) |
| M16 | ResultsPanel "Baixar SARIF" (non-accent pt) | KILLED |
| M17 | `sse.ts` emits hard-coded English text instead of `connection_lost` code | **SURVIVED** |
| M18 | `errorNotice` stops mapping TypeError | KILLED |
| M19 | FolderPicker "Select this folder" hard-coded English | **SURVIVED** |

Score: 17/21 killed; meaningful survivors: M12b, M17, M19.

## Gaps (ranked)

1. **Hard-coded English in components without a pt-BR assertion is undetected** (M19). The guard only catches accents, and en tests can't distinguish catalog from literal. Affects FolderPicker, ClarifyForm, ChatDock, ResultsPanel, History (T3/T4 promised "one pt-BR assertion each"; component test files contain none). Suggest one pt-BR render per component.
2. **`sse.ts` → `{ code: 'connection_lost' }` untested** (M17): sse is mocked in App tests and the reducer test injects the code directly. Add an `sse.test.ts` asserting `onError` receives the code on a non-recoverable `EventSource` error.
3. **History status labels not asserted translated** (M12b): no test renders `waiting_input` in en or any status in pt-BR.
4. Docs precision: README/USAGE/DOCUMENTACAO say pt is chosen when the browser's *first preferred* language is `pt*`; LOC-01 (updated) uses the first *supported* entry (`['es-ES','pt-BR']` → pt-BR).
5. Design drift (minor): design says global test setup pins `navigator.language='en-US'` and clears storage; `src/test/setup.ts` only imports jest-dom (relies on jsdom default `en-US` and per-file isolation). `Messages = typeof en` instead of an explicit `Widen<>` (equivalent here since `en` isn't `as const`).
6. LOC-03 preservation is asserted for form input/history/notice only, not a running timeline, typed clarify answers or chat history (edge case listed in spec); structurally covered by the provider sitting above App state (M09b).
