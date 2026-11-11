// Spec: .specs/features/web-i18n/spec.md — I18N-03 (guarda heurística: texto acentuado fora dos catálogos)
/// <reference types="vite/client" />
const sources = import.meta.glob('../**/*.{ts,tsx}', { query: '?raw', import: 'default', eager: true }) as Record<
  string,
  string
>

const ACCENTED = /[áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]/

/** Remove comentários de bloco/JSX e de linha (sem confundir `//` de URLs em strings). */
export function stripComments(code: string): string {
  return code.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`\\])\/\/.*$/gm, '$1')
}

describe('I18N-03: sem literais em português fora de i18n/', () => {
  // O Vite normaliza os caminhos relativos a este arquivo: `./x` = o próprio i18n/ (catálogos).
  const files = Object.keys(sources).filter(
    (p) => p.startsWith('../') && !/\.test\.tsx?$/.test(p) && !p.startsWith('../test/'),
  )

  it('varre os módulos da aplicação', () => {
    expect(files.length).toBeGreaterThan(15)
    expect(files).toContain('../components/Timeline.tsx')
    // Os catálogos entram no glob como `./…` (mesma pasta) e ficam de fora da varredura.
    expect(Object.keys(sources)).toContain('./pt-BR.ts')
    expect(files.some((p) => p.includes('i18n/'))).toBe(false)
  })

  it.each(files)('%s', (path) => {
    const offending = stripComments(sources[path])
      .split('\n')
      .filter((line) => ACCENTED.test(line))
    expect(offending).toEqual([])
  })

  it('a guarda detecta um literal plantado e ignora comentários', () => {
    expect(ACCENTED.test(stripComments("const a = 'Concluída'"))).toBe(true)
    expect(ACCENTED.test(stripComments('// comentário em português\nconst a = 1'))).toBe(false)
    expect(ACCENTED.test(stripComments('/** documentação */ const a = 1'))).toBe(false)
    expect(ACCENTED.test(stripComments("const u = 'http://x' // á"))).toBe(false)
  })
})
