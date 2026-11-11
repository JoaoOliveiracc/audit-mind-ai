import { createContext, useCallback, useContext, useLayoutEffect, useMemo, useState, type ReactNode } from 'react'

import type { Notice } from '../types'
import { en, type Messages } from './en'
import { DEFAULT_LOCALE, detectLocale, safeStorage, saveLocale, type Locale } from './locale'
import { ptBR } from './pt-BR'

export const CATALOGS: Record<Locale, Messages> = { en, 'pt-BR': ptBR }

interface I18n {
  locale: Locale
  t: Messages
  setLocale: (locale: Locale) => void
}

// Sem provider (testes de componente isolados): inglês, troca sem efeito.
const I18nContext = createContext<I18n>({ locale: DEFAULT_LOCALE, t: en, setLocale: () => {} })

export function I18nProvider({ children, initialLocale }: { children: ReactNode; initialLocale?: Locale }) {
  const [locale, setLocaleState] = useState<Locale>(
    () => initialLocale ?? detectLocale(typeof navigator === 'undefined' ? undefined : navigator, safeStorage()),
  )

  // Antes da 1ª pintura: leitor de tela/hifenização já usam o idioma certo (LOC-04).
  useLayoutEffect(() => {
    document.documentElement.lang = locale
  }, [locale])

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next)
    saveLocale(safeStorage(), next)
  }, [])

  const value = useMemo(() => ({ locale, t: CATALOGS[locale], setLocale }), [locale, setLocale])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18n {
  return useContext(I18nContext)
}

/** Rótulo de uma chave vinda do servidor (severidade/status); chave desconhecida aparece crua. */
export function labelOf<T extends Record<string, string>>(map: T, key: string): string {
  return Object.prototype.hasOwnProperty.call(map, key) ? map[key as keyof T] : key
}

/** Erro capturado → aviso: falha de rede do `fetch` (TypeError) vira código traduzido; o resto,
 * a mensagem do servidor/erro como veio (sem o prefixo "Error: " de `String(err)`). */
export function errorNotice(err: unknown): Notice {
  if (err instanceof TypeError) return { code: 'network_error' }
  return err instanceof Error ? err.message : String(err)
}

/** Texto de um aviso: mensagens do servidor passam como vieram; códigos do cliente são traduzidos. */
export function noticeText(t: Messages, notice: Notice): string {
  if (typeof notice === 'string') return notice
  if (notice.code === 'audit_failed') return t.app.notice.audit_failed(notice.detail)
  return t.app.notice[notice.code]
}
