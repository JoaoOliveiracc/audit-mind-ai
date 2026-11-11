// Spec: .specs/features/web-i18n/spec.md — LOC-01/02/05, I18N-02, I18N-04
import { en } from './en'
import { browserLocale, detectLocale, saveLocale, STORAGE_KEY } from './locale'
import { plural } from './plural'
import { ptBR } from './pt-BR'

const store = (value: string | null) => ({ getItem: (k: string) => (k === STORAGE_KEY ? value : null) })
const throwing = {
  getItem: () => {
    throw new Error('SecurityError')
  },
  setItem: () => {
    throw new Error('QuotaExceeded')
  },
}

describe('LOC-01: idioma do navegador', () => {
  it.each([
    [{ languages: ['pt-BR', 'en'] }, 'pt-BR'],
    [{ languages: ['PT-pt'] }, 'pt-BR'],
    [{ languages: ['pt'] }, 'pt-BR'],
    [{ languages: ['en-US', 'pt-BR'] }, 'en'],   // 1ª preferência suportada vence
    [{ languages: ['es-ES', 'pt-BR'] }, 'pt-BR'], // não suportada é pulada
    [{ languages: ['es-ES', 'fr'] }, 'en'],
    [{ languages: ['es-ES'] }, 'en'],
    [{ languages: [], language: 'pt-BR' }, 'pt-BR'],
    [{ language: 'de-DE' }, 'en'],
    [{}, 'en'],
    [undefined, 'en'],
  ] as const)('%j → %s', (nav, expected) => {
    expect(browserLocale(nav as never)).toBe(expected)
  })
})

describe('LOC-02: escolha salva vence o navegador', () => {
  it('valor válido vence', () => {
    expect(detectLocale({ languages: ['pt-BR'] }, store('en'))).toBe('en')
    expect(detectLocale({ languages: ['en-US'] }, store('pt-BR'))).toBe('pt-BR')
  })
  it.each(['fr', 'pt', 'EN', '', 'pt-br'])('valor inválido %j é ignorado', (saved) => {
    expect(detectLocale({ languages: ['pt-BR'] }, store(saved))).toBe('pt-BR')
    expect(detectLocale({ languages: ['en-US'] }, store(saved))).toBe('en')
  })
  it('sem storage usa o navegador', () => {
    expect(detectLocale({ languages: ['pt-BR'] }, undefined)).toBe('pt-BR')
  })
})

describe('LOC-05: storage que lança', () => {
  it('leitura que lança cai no navegador', () => {
    expect(detectLocale({ languages: ['pt-BR'] }, throwing)).toBe('pt-BR')
  })
  it('gravação que lança não propaga', () => {
    expect(() => saveLocale(throwing, 'en')).not.toThrow()
  })
  it('gravação válida usa a chave auditor.locale', () => {
    const setItem = vi.fn()
    saveLocale({ setItem }, 'pt-BR')
    expect(setItem).toHaveBeenCalledWith('auditor.locale', 'pt-BR')
  })
})

describe('I18N-04: plurais', () => {
  it('en', () => {
    expect(en.common.findings(0)).toBe('0 findings')
    expect(en.common.findings(1)).toBe('1 finding')
    expect(en.common.findings(2)).toBe('2 findings')
  })
  it('pt-BR (0 explícito como plural)', () => {
    expect(ptBR.common.findings(0)).toBe('0 achados')
    expect(ptBR.common.findings(1)).toBe('1 achado')
    expect(ptBR.common.findings(2)).toBe('2 achados')
  })
  it('todas as contagens seguem o plural (0, 1, 2)', () => {
    expect([0, 1, 2].map(ptBR.timeline.confirmed)).toEqual(
      ['0 confirmados pelo juiz', '1 confirmado pelo juiz', '2 confirmados pelo juiz'])
    expect(ptBR.timeline.rejected(1)).toBe('1 descartado (alucinação)')
    expect(ptBR.timeline.refuted(1)).toBe('1 refutado (falso positivo)')
    expect(ptBR.timeline.uncertainOf(1, 1)).toBe('1 incerto · de 1 julgado')
    expect(ptBR.results.discarded(1)).toBe('1 descartado')
    expect(ptBR.results.uncertain(2)).toBe('2 incertos')
    expect(ptBR.timeline.filesAndLoc(1, 10)).toBe('1 arquivo · ~10 LOC')
    expect(ptBR.timeline.filesAndLoc(0, 0)).toBe('0 arquivos · ~0 LOC')
    expect(en.timeline.filesAndLoc(1, 10)).toBe('1 file · ~10 LOC')
    expect(en.timeline.filesAndLoc(3, 10)).toBe('3 files · ~10 LOC')
  })
  it('usa Intl.PluralRules do idioma', () => {
    expect(plural('en', 1, { one: '# x', other: '# xs' })).toBe('1 x')
    expect(plural('en', 1.5, { one: '# x', other: '# xs' })).toBe('1.5 xs')
    expect(plural('pt-BR', 0, { one: '# x', other: '# xs' })).toBe('0 x')    // sem `zero`: regra do Intl
  })
})

/** Formato do catálogo: mesmas chaves e mesmo tipo (texto × função) em todo nível. */
function shape(obj: unknown): unknown {
  if (typeof obj === 'function') return `fn/${(obj as (...a: unknown[]) => unknown).length}`
  if (obj && typeof obj === 'object')
    return Object.fromEntries(Object.keys(obj).sort().map((k) => [k, shape((obj as Record<string, unknown>)[k])]))
  return typeof obj
}

describe('I18N-02: paridade dos catálogos (também verificada pelo tsc)', () => {
  it('pt-BR tem exatamente as chaves e assinaturas do en', () => {
    expect(shape(ptBR)).toEqual(shape(en))
  })
  it('nenhum texto vazio', () => {
    const empty: string[] = []
    const walk = (o: Record<string, unknown>, path: string) => {
      for (const [k, v] of Object.entries(o)) {
        if (typeof v === 'string' && !v.trim()) empty.push(`${path}.${k}`)
        else if (v && typeof v === 'object') walk(v as Record<string, unknown>, `${path}.${k}`)
      }
    }
    walk(en, 'en')
    walk(ptBR as Record<string, unknown>, 'pt-BR')
    expect(empty).toEqual([])
  })
})

describe('I18N-01: erros capturados viram avisos', () => {
  it('falha de rede do fetch (TypeError) vira código traduzido', async () => {
    const { errorNotice, noticeText } = await import('./I18nProvider')
    const n = errorNotice(new TypeError('Failed to fetch'))
    expect(n).toEqual({ code: 'network_error' })
    expect(noticeText(en, n)).toBe('Could not reach the server. Check that the API is running (make api).')
    expect(noticeText(ptBR, n)).toBe('Não foi possível falar com o servidor. Verifique se a API está rodando (make api).')
  })
  it('Error comum passa a mensagem sem o prefixo "Error: "', async () => {
    const { errorNotice } = await import('./I18nProvider')
    expect(errorNotice(new Error('detalhe da API'))).toBe('detalhe da API')
    expect(errorNotice('x')).toBe('x')
  })
  it('chave desconhecida do servidor aparece crua', async () => {
    const { labelOf } = await import('./I18nProvider')
    expect(labelOf(en.common.status, 'completed')).toBe('completed')
    expect(labelOf(ptBR.common.status, 'completed')).toBe('concluída')
    expect(labelOf(ptBR.common.status, 'paused')).toBe('paused')
    expect(labelOf(ptBR.common.severity, 'toString')).toBe('toString')   // sem herdar do protótipo
  })
})
