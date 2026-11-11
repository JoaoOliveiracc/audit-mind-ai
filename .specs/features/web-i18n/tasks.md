# Web UI Internationalization — Tasks (G50)

Spec: [spec.md](spec.md) · Design: [design.md](design.md). 8 tasks, one batch (inline, no sub-agents).
After T8: `/code-review`, then the Verifier.

Gate (each task): `./node_modules/.bin/vitest run` + `./node_modules/.bin/tsc --noEmit` in `frontend/`.
T8 also runs `make ci`. Tests come first and assert the spec's copy and behavior.

| ID | Task | Files | Depends | Reqs | Verification |
| -- | ---- | ----- | ------- | ---- | ------------ |
| T1 | i18n core: `locale.ts` (detect/save, storage-safe), `plural.ts`, `I18nProvider` + `useI18n`, `<html lang>` | `src/i18n/*`, tests | — | LOC-01, LOC-02, LOC-04, LOC-05, I18N-04 | Detection matrix; plural tables incl. pt-BR zero; lang attribute |
| T2 | Catalogs `en.ts` + `pt-BR.ts` (typed parity), `common` group (severity/status/tier/buttons); runtime parity test | `src/i18n/en.ts`, `pt-BR.ts`, test | T1 | I18N-02 | `tsc` fails on a missing key (checked by a throwaway edit during review); runtime key-set equality |
| T3 | Migrate `score.ts`, `HealthStamp`, `FindingCard`, `ClarifyForm`, `FolderPicker` | components + tests | T2 | I18N-01, I18N-04 | Tests in en; one pt-BR assertion each |
| T4 | Migrate `History`, `ResultsPanel`, `ChatDock` | components + tests | T2 | I18N-01 | Same |
| T5 | Migrate `Timeline`, `StartForm`, `auditReducer` labels, `sse.ts` (error code → App) | components + tests | T2 | I18N-01 | Same; sse emits a code, App shows the translated message |
| T6 | `App` + `LanguageToggle` in the header; provider in `main.tsx`; `index.html` lang/title | `App.tsx`, `main.tsx`, `components/LanguageToggle.tsx`, `index.html`, tests | T3–T5 | LOC-03, LOC-06, I18N-05 | Toggle round-trip keeps state; persists across remount; aria-label text |
| T7 | Guard test: no Portuguese literal outside `i18n/` and tests | `src/i18n/no-literals.test.ts` | T3–T6 | I18N-03 | Fails on a planted accented literal (manual check), passes on the tree |
| T8 | Docs: README + docs/USAGE web section, DOCUMENTACAO §10.3 G50 row + backend-language follow-up | docs | T6 | DOC-02 | `make ci` 0 |

Commits: the user runs git; commands are listed at the end.
