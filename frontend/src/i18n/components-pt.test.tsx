// Spec: .specs/features/web-i18n/spec.md — I18N-01 (cada componente nos dois idiomas; pega literal
// fixo em inglês, que a guarda por acentos não vê) — fix loop do Verifier (M12b, M19)
import { render, screen } from '@testing-library/react'
import type { ReactElement } from 'react'

import * as client from '../api/client'
import ChatDock from '../components/ChatDock'
import ClarifyForm from '../components/ClarifyForm'
import FolderPicker from '../components/FolderPicker'
import History from '../components/History'
import ResultsPanel from '../components/ResultsPanel'
import type { AuditSummary, FindingsPayload } from '../types'
import { I18nProvider } from './I18nProvider'
import type { Locale } from './locale'

vi.mock('../api/client', () => ({
  browseFs: vi.fn(),
  chatAudit: vi.fn(),
  reportUrl: (id: string, f: string) => `/audits/${id}/report?format=${f}`,
}))

const inLocale = (locale: Locale, ui: ReactElement) => render(<I18nProvider initialLocale={locale}>{ui}</I18nProvider>)

const audit: AuditSummary = { id: 'a1', status: 'completed', project_path: '/p', created_at: 'x', health_score: 80 }
const payload: FindingsPayload = {
  findings: [{ dimension: 'security', title: 'T', severity: 'high', description: 'd', recommendation: 'r',
    confidence: 0.9 } as never],
  dimension_summaries: [], health_score: 80, executive_summary: '', stack_profile: {} as never,
  verification: { enabled: true, verified: 1, unverified: 1, rejected: 1 } as never,
  adversarial: { enabled: true, judged: 1, confirmed: 1, uncertain: 1, refuted: 1 } as never,
}

describe.each([
  ['en', {
    folder: ['Select this folder', 'Cancel', 'Choose folder'],
    clarify: ['Send answers', 'Skip all'],
    chat: ['Ask about the result', 'Send'],
    history: ['History · 2', 'completed', 'interrupted', 'Resume', 'Delete'],
    results: ["Auditor's opinion", '(summary not generated)', '1 finding', 'High · 1', '1 discarded',
      '1 confirmed', '1 refuted', 'Open HTML report', 'Download Markdown'],
  }],
  ['pt-BR', {
    folder: ['Selecionar esta pasta', 'Cancelar', 'Escolher pasta'],
    clarify: ['Enviar respostas', 'Pular todas'],
    chat: ['Perguntar sobre o resultado', 'Enviar'],
    history: ['Histórico · 2', 'concluída', 'interrompida', 'Retomar', 'Excluir'],
    results: ['Parecer do auditor', '(resumo não gerado)', '1 achado', 'Alto · 1', '1 descartado',
      '1 confirmado', '1 refutado', 'Abrir relatório HTML', 'Baixar Markdown'],
  }],
] as const)('%s', (locale, copy) => {
  beforeEach(() => {
    vi.mocked(client.browseFs).mockReturnValue(new Promise(() => {}))
  })

  it('FolderPicker', () => {
    inLocale(locale, <FolderPicker onSelect={() => {}} onClose={() => {}} />)
    for (const text of copy.folder) expect(screen.getByText(text)).toBeInTheDocument()
  })

  it('ClarifyForm', () => {
    inLocale(locale, <ClarifyForm questions={[{ question: 'Q?' } as never]} onSubmit={() => {}} />)
    for (const text of copy.clarify) expect(screen.getByText(text)).toBeInTheDocument()
  })

  it('ChatDock', () => {
    inLocale(locale, <ChatDock auditId="a1" />)
    for (const text of copy.chat) expect(screen.getByText(text)).toBeInTheDocument()
  })

  it('History (inclui rótulo de status traduzido)', () => {
    inLocale(locale, <History audits={[audit, { ...audit, id: 'i1', status: 'interrupted', health_score: null }]}
      onOpen={() => {}} onDelete={() => {}} onResume={() => {}} />)
    const text = document.body.textContent ?? ''
    for (const s of copy.history) expect(text).toContain(s)
  })

  it('ResultsPanel', () => {
    inLocale(locale, <ResultsPanel auditId="a1" payload={payload} counts={{ high: 1 }} />)
    const text = document.body.textContent ?? ''
    for (const s of copy.results) expect(text).toContain(s)
  })
})
