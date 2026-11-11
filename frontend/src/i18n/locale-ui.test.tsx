// Spec: .specs/features/web-i18n/spec.md — LOC-01..06, I18N-01, I18N-05
/// <reference types="vite/client" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import indexHtml from '../../index.html?raw'

import * as client from '../api/client'
import * as sse from '../api/sse'
import App from '../App'
import FindingCard from '../components/FindingCard'
import HealthStamp from '../components/HealthStamp'
import Timeline from '../components/Timeline'
import { auditReducer, initialState } from '../state/auditReducer'
import type { AuditSummary, Notice } from '../types'
import { I18nProvider } from './I18nProvider'
import { STORAGE_KEY } from './locale'

vi.mock('../api/client', () => ({
  getProviders: vi.fn(),
  getDefaults: vi.fn(),
  listAudits: vi.fn(),
  resumeAudit: vi.fn(),
  createAudit: vi.fn(),
  deleteAudit: vi.fn(),
  getAudit: vi.fn(),
  getFindings: vi.fn(),
  submitAnswers: vi.fn(),
  browseFs: vi.fn(),
  reportUrl: vi.fn(),
  chatAudit: vi.fn(),
}))
vi.mock('../api/sse', () => ({ connectAuditStream: vi.fn() }))

const interrupted: AuditSummary = {
  id: 'i1', status: 'interrupted', project_path: '/proj/beta', created_at: '2026-11-10T10:00:00+00:00',
}

function setNavigator(languages: string[]) {
  vi.spyOn(window.navigator, 'languages', 'get').mockReturnValue(languages)
  vi.spyOn(window.navigator, 'language', 'get').mockReturnValue(languages[0] ?? '')
}

const toggle = () => screen.getByRole('button', { name: /^(PT|EN) — / })

beforeEach(() => {
  window.localStorage.clear()
  document.documentElement.lang = ''
  vi.mocked(client.getProviders).mockResolvedValue([])
  vi.mocked(client.getDefaults).mockResolvedValue({ vuln_scan: false })
  vi.mocked(client.listAudits).mockResolvedValue([interrupted])
  vi.mocked(sse.connectAuditStream).mockReturnValue({ close: vi.fn() })
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

describe('LOC-01 / LOC-04: idioma inicial', () => {
  it('navegador en-US, sem escolha salva → inglês e <html lang="en">', async () => {
    setNavigator(['en-US'])
    render(<I18nProvider><App /></I18nProvider>)
    expect(await screen.findByRole('button', { name: 'Start audit' })).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('en')
  })

  it('navegador pt-BR → português e <html lang="pt-BR">', async () => {
    setNavigator(['pt-BR', 'en'])
    render(<I18nProvider><App /></I18nProvider>)
    expect(await screen.findByRole('button', { name: 'Iniciar auditoria' })).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('pt-BR')
  })
})

describe('LOC-02: escolha salva', () => {
  it('auditor.locale=en vence navegador pt-BR', async () => {
    setNavigator(['pt-BR'])
    window.localStorage.setItem(STORAGE_KEY, 'en')
    render(<I18nProvider><App /></I18nProvider>)
    expect(await screen.findByRole('button', { name: 'Start audit' })).toBeInTheDocument()
  })

  it('valor inválido é ignorado', async () => {
    setNavigator(['pt-BR'])
    window.localStorage.setItem(STORAGE_KEY, 'fr')
    render(<I18nProvider><App /></I18nProvider>)
    expect(await screen.findByRole('button', { name: 'Iniciar auditoria' })).toBeInTheDocument()
  })
})

describe('LOC-03 / LOC-06: botão de idioma', () => {
  it('mostra o OUTRO idioma e o aria-label exato', async () => {
    setNavigator(['en-US'])
    render(<I18nProvider><App /></I18nProvider>)
    await screen.findByRole('button', { name: 'Start audit' })
    expect(toggle()).toHaveTextContent(/^PT$/)
    expect(toggle()).toHaveAccessibleName('PT — switch language to Português (current: English)')
    fireEvent.click(toggle())
    expect(toggle()).toHaveTextContent(/^EN$/)
    expect(toggle()).toHaveAccessibleName('EN — mudar idioma para English (atual: Português)')
  })

  it('troca sem perder o estado, grava a escolha e persiste após remontar', async () => {
    setNavigator(['en-US'])
    const { unmount } = render(<I18nProvider><App /></I18nProvider>)
    const path = await screen.findByLabelText('Project path')
    fireEvent.change(path, { target: { value: '/proj/kept' } })

    fireEvent.click(toggle())

    expect(screen.getByRole('button', { name: 'Iniciar auditoria' })).toBeInTheDocument()
    expect(screen.getByLabelText('Caminho do projeto')).toHaveValue('/proj/kept')   // estado mantido
    expect(screen.getByText('Histórico · 1')).toBeInTheDocument()
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('pt-BR')
    expect(document.documentElement.lang).toBe('pt-BR')

    unmount()
    render(<I18nProvider><App /></I18nProvider>)
    expect(await screen.findByRole('button', { name: 'Iniciar auditoria' })).toBeInTheDocument()
  })

  it('aviso já exibido acompanha a troca de idioma', async () => {
    setNavigator(['en-US'])
    vi.mocked(client.getAudit).mockResolvedValue(interrupted)
    render(<I18nProvider><App /></I18nProvider>)
    fireEvent.click(await screen.findByText('/proj/beta'))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Audit interrupted — use Resume to continue from the last checkpoint.')
    fireEvent.click(toggle())
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Auditoria interrompida — use Retomar para continuar do último checkpoint.')
  })
})

describe('LOC-05: localStorage que lança', () => {
  it('renderiza pelo navegador e a troca funciona na sessão', async () => {
    setNavigator(['pt-BR'])
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceeded')
    })
    render(<I18nProvider><App /></I18nProvider>)
    expect(await screen.findByRole('button', { name: 'Iniciar auditoria' })).toBeInTheDocument()
    fireEvent.click(toggle())
    expect(screen.getByRole('button', { name: 'Start audit' })).toBeInTheDocument()
  })
})

describe('I18N-01: textos do cliente nos dois idiomas', () => {
  it('erro de conexão do SSE é um código traduzido, não texto fixo', async () => {
    const lost: Notice = { code: 'connection_lost' }
    let s = auditReducer(initialState, { type: 'START' })
    s = auditReducer(s, { type: 'ERROR', message: lost })
    const { unmount } = render(<Timeline state={s} onClarifySubmit={() => {}} />)
    expect(screen.getByText('Connection to the server was lost.')).toBeInTheDocument()
    unmount()
    render(<I18nProvider initialLocale="pt-BR"><Timeline state={s} onClarifySubmit={() => {}} /></I18nProvider>)
    expect(screen.getByText('Conexão com o servidor perdida.')).toBeInTheDocument()
  })

  it('mensagem do servidor aparece como veio', () => {
    const s = auditReducer(auditReducer(initialState, { type: 'START' }), { type: 'ERROR', message: 'boom do servidor' })
    render(<I18nProvider initialLocale="pt-BR"><Timeline state={s} onClarifySubmit={() => {}} /></I18nProvider>)
    expect(screen.getByText('boom do servidor')).toBeInTheDocument()
  })

  it('severidade, confiança e rótulo do selo', () => {
    const finding = { dimension: 'security', title: 'T', severity: 'critical', description: 'd',
      recommendation: 'r', confidence: 0.8 } as never
    const { unmount } = render(<><FindingCard finding={finding} /><HealthStamp score={40} /></>)
    expect(screen.getByText('Critical')).toBeInTheDocument()
    expect(screen.getByText('confidence 80%')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Health score: 40 out of 100 (critical)' })).toBeInTheDocument()
    unmount()
    render(<I18nProvider initialLocale="pt-BR"><FindingCard finding={finding} /><HealthStamp score={80} /></I18nProvider>)
    expect(screen.getByText('Crítico')).toBeInTheDocument()
    expect(screen.getByText('confiança 80%')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Pontuação de saúde: 80 de 100 (saudável)' })).toBeInTheDocument()
  })

  it('rótulos das etapas da timeline', () => {
    const s = auditReducer(initialState, { type: 'START' })
    render(<I18nProvider initialLocale="pt-BR"><Timeline state={s} onClarifySubmit={() => {}} /></I18nProvider>)
    expect(screen.getByText('01 · Descoberta')).toBeInTheDocument()
    expect(screen.getByText('08 · Relatório')).toBeInTheDocument()
  })
})

describe('I18N-05: index.html', () => {
  it('lang="en" e título Audit Mind AI', () => {
    const html = indexHtml
    expect(html).toMatch(/<html lang="en"/)
    expect(html).toMatch(/<title>Audit Mind AI<\/title>/)
  })
})

describe('regressão: retomada funciona em pt-BR', () => {
  it('botão Retomar em pt-BR dispara resumeAudit', async () => {
    setNavigator(['pt-BR'])
    vi.mocked(client.resumeAudit).mockResolvedValue({ ...interrupted, status: 'running' })
    render(<I18nProvider><App /></I18nProvider>)
    fireEvent.click(await screen.findByRole('button', { name: 'Retomar auditoria de /proj/beta' }))
    await waitFor(() => expect(client.resumeAudit).toHaveBeenCalledWith('i1'))
  })
})
