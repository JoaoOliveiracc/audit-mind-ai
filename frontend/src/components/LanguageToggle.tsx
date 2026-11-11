import { useI18n } from '../i18n/I18nProvider'

/** Alterna en ↔ pt-BR; o botão mostra o OUTRO idioma (LOC-06). */
export default function LanguageToggle() {
  const { locale, t, setLocale } = useI18n()
  const next = locale === 'en' ? 'pt-BR' : 'en'
  return (
    <button
      type="button"
      className="btn !px-2 !py-0.5 !text-xs font-mono"
      aria-label={t.language.toggleLabel}
      title={t.language.toggleLabel}
      onClick={() => setLocale(next)}
    >
      {next === 'en' ? 'EN' : 'PT'}
    </button>
  )
}
