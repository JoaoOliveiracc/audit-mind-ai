/** Idiomas suportados, detecção e persistência (spec: .specs/features/web-i18n — LOC-01/02/05). */

export const LOCALES = ['en', 'pt-BR'] as const
export type Locale = (typeof LOCALES)[number]
export const DEFAULT_LOCALE: Locale = 'en'
export const STORAGE_KEY = 'auditor.locale'

type NavigatorLike = { language?: string; languages?: readonly string[] }
type ReadableStorage = Pick<Storage, 'getItem'>
type WritableStorage = Pick<Storage, 'setItem'>

export function isLocale(value: unknown): value is Locale {
  return typeof value === 'string' && (LOCALES as readonly string[]).includes(value)
}

/** Idioma do navegador: a 1ª preferência SUPORTADA da lista (`pt*` → `pt-BR`, único catálogo
 * português; `en*` → `en`); nenhuma suportada → `en`. */
export function browserLocale(nav: NavigatorLike | undefined): Locale {
  const prefs = nav?.languages?.length ? nav.languages : nav?.language ? [nav.language] : []
  for (const raw of prefs) {
    const tag = raw.toLowerCase()
    if (tag.startsWith('pt')) return 'pt-BR'
    if (tag.startsWith('en')) return 'en'
  }
  return DEFAULT_LOCALE
}

/** Escolha salva (se válida) vence o navegador; erros de storage caem no navegador. */
export function detectLocale(nav: NavigatorLike | undefined, storage: ReadableStorage | undefined): Locale {
  try {
    const saved = storage?.getItem(STORAGE_KEY)
    if (isLocale(saved)) return saved
  } catch {
    /* storage indisponível (modo privado, bloqueado): segue pelo navegador */
  }
  return browserLocale(nav)
}

export function saveLocale(storage: WritableStorage | undefined, locale: Locale): void {
  try {
    storage?.setItem(STORAGE_KEY, locale)
  } catch {
    /* sem persistência: a troca vale só para a sessão */
  }
}

/** `window.localStorage` pode lançar só por ser acessado (cookies bloqueados). */
export function safeStorage(): Storage | undefined {
  try {
    return typeof window === 'undefined' ? undefined : window.localStorage
  } catch {
    return undefined
  }
}
