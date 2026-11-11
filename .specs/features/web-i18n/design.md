# Web UI Internationalization — Design (G50)

## Decision: in-house typed catalogs (no i18n library)

| Option | Pros | Cons |
| ------ | ---- | ---- |
| react-i18next | Standard; namespaces, lazy loading, ICU via plugins | +2 deps (~40 kB), string keys are untyped unless you add extra typing setup, too much for 2 locales and ~250 strings |
| FormatJS (react-intl) | ICU messages | Heavier; messages are strings, so parity is checked at runtime, not compile time |
| **Typed catalogs + React context** ✅ | Zero deps; `tsc` enforces key parity; messages can be functions (plurals, interpolation) with typed params | Must implement detection/persistence (~40 lines) |

Migrating to a library later stays cheap: components only call `t.<key>` and `useI18n()`.

## Modules (`frontend/src/i18n/`)

```
i18n/
├── en.ts          // source of truth: `export const en = { ... }`; export type Messages = typeof en (widened)
├── pt-BR.ts       // `export const ptBR: Messages = { ... }`, so a missing or extra key fails tsc (I18N-02)
├── locale.ts      // LOCALES, Locale type, detectLocale(nav, storage), saveLocale(), STORAGE_KEY
├── plural.ts      // plural(locale, n, { one, other, zero? }) via Intl.PluralRules (I18N-04)
└── I18nProvider.tsx  // context { locale, t, setLocale }; sets <html lang> (LOC-04); useI18n()
```

- **Message shape**: plain strings for static text; functions for parameterized text, for example
  `findings: (n: number) => plural('en', n, { one: '1 finding', other: `${n} findings` })` and
  `deleteLabel: (path: string) => \`Delete audit of ${path}\``. `Messages = typeof en`: object-literal
  strings already widen to `string`, so pt-BR uses different text with the same keys and parameters
  (no `Widen<>` helper needed).
- **Grouping**: by component (`t.history.*`, `t.timeline.*`, `t.start.*`, …) plus `t.common.*`
  (severity, status, tier, buttons). `score.ts` keeps `SEVERITY_ORDER`, and `SEVERITY_LABEL` moves
  to `t.common.severity`.
- **Non-React modules** (`sse.ts`): they take the text from the caller instead of importing the
  catalog (`h.onError(kind)` passes an error code `'connection_lost'`, and App maps it through `t`).
  Modules stay pure and testable.
- **Detection** (`detectLocale`): it receives `navigator`-like and `Storage`-like inputs (injectable
  for tests) and applies LOC-02 → LOC-01. Every storage access is wrapped in try/catch (LOC-05).
- **Toggle** (`LanguageToggle.tsx`): in the App header. Clicking it calls `setLocale(other)` and
  saves the choice. The provider lives above `App`'s state, so state survives (LOC-03).
- **Guard test** (I18N-03): a vitest test globs `src/**/*.{ts,tsx}` (excluding `i18n/` and tests),
  strips comments, and fails on accented Portuguese letters. This is a heuristic backstop; the main
  control is the review.

## Test strategy

- Test locale: jsdom's default `navigator.language` is `en-US` and components without a provider use
  the `en` default context → existing tests assert English
  (they are updated to the new copy — expected, since the product default changed).
- `i18n/*.test.ts`: detection matrix (LOC-01/02/05), plural tables (I18N-04, pt-BR zero), parity is
  enforced at compile time and additionally checked at runtime (deep key-set equality, so the test
  also covers function keys).
- `App.test.tsx`: toggle round-trip without losing state, `<html lang>`, persistence across remount (LOC-03/04/06).
