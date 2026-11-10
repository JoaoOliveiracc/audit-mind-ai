// Spec: .specs/features/api-hardening/spec.md — UI-03 (App wiring da retomada)
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import * as client from './api/client'
import * as sse from './api/sse'
import App from './App'
import type { AuditSummary } from './types'

vi.mock('./api/client', () => ({
  getProviders: vi.fn(),
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
vi.mock('./api/sse', () => ({ connectAuditStream: vi.fn() }))

const interrupted: AuditSummary = {
  id: 'i1',
  status: 'interrupted',
  project_path: '/proj/beta',
  created_at: '2026-11-10T10:00:00+00:00',
}

beforeEach(() => {
  vi.mocked(client.getProviders).mockResolvedValue([])
  vi.mocked(client.listAudits).mockResolvedValue([interrupted])
  vi.mocked(client.browseFs).mockResolvedValue({ path: '/', parent: null, entries: [] })
  vi.mocked(sse.connectAuditStream).mockReturnValue({ close: vi.fn() })
})

afterEach(() => vi.clearAllMocks())

describe('App — retomada (UI-03)', () => {
  it('sucesso: conecta ao stream da auditoria e sai do histórico', async () => {
    vi.mocked(client.resumeAudit).mockResolvedValue({ ...interrupted, status: 'running' })
    render(<App />)

    fireEvent.click(await screen.findByRole('button', { name: 'Retomar auditoria de /proj/beta' }))

    await waitFor(() => expect(sse.connectAuditStream).toHaveBeenCalledTimes(1))
    expect(vi.mocked(sse.connectAuditStream).mock.calls[0][0]).toBe('i1')
    expect(client.resumeAudit).toHaveBeenCalledWith('i1')
    expect(screen.queryByRole('button', { name: /^Retomar auditoria de / })).not.toBeInTheDocument()
  })

  it('falha: mostra o erro da API e não conecta ao stream', async () => {
    vi.mocked(client.resumeAudit).mockRejectedValue(
      new Error('Só auditorias interrompidas podem ser retomadas.'),
    )
    render(<App />)

    fireEvent.click(await screen.findByRole('button', { name: 'Retomar auditoria de /proj/beta' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Só auditorias interrompidas podem ser retomadas.',
    )
    expect(sse.connectAuditStream).not.toHaveBeenCalled()
  })
})

// Spec: .specs/features/history-polish/spec.md — HIS-01..03
describe('App — abrir interrompida/erro e Retomar em voo', () => {
  async function openRow(audit: AuditSummary) {
    vi.mocked(client.listAudits).mockResolvedValue([audit])
    vi.mocked(client.getAudit).mockResolvedValue(audit)
    render(<App />)
    fireEvent.click(await screen.findByText(audit.project_path))
  }

  it('HIS-01: interrompida mostra orientação e não conecta ao stream', async () => {
    await openRow(interrupted)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Auditoria interrompida — use Retomar para continuar do último checkpoint.',
    )
    expect(sse.connectAuditStream).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Retomar auditoria de /proj/beta' })).toBeInTheDocument()
  })

  it('HIS-02: erro mostra a mensagem gravada e não conecta ao stream', async () => {
    await openRow({ ...interrupted, id: 'e1', status: 'error', project_path: '/proj/err',
      error: 'rate limit do provedor' })

    expect(await screen.findByRole('alert')).toHaveTextContent('Auditoria falhou: rate limit do provedor')
    expect(sse.connectAuditStream).not.toHaveBeenCalled()
    expect(screen.getByText('/proj/err')).toBeInTheDocument()   // continua no histórico
  })

  it('HIS-02: erro sem texto mostra mensagem genérica', async () => {
    await openRow({ ...interrupted, id: 'e2', status: 'error', project_path: '/proj/err2', error: null })

    expect(await screen.findByRole('alert')).toHaveTextContent(/^Auditoria falhou\.$/)
  })

  it('HIS-03: Retomar fica desabilitado em voo e não dispara de novo', async () => {
    let finish: (v: AuditSummary) => void = () => {}
    vi.mocked(client.resumeAudit).mockReturnValue(new Promise((r) => { finish = r }))
    render(<App />)

    const btn = await screen.findByRole('button', { name: 'Retomar auditoria de /proj/beta' })
    fireEvent.click(btn)
    await waitFor(() => expect(btn).toBeDisabled())
    expect(btn).toHaveTextContent('Retomando…')
    fireEvent.click(btn)
    expect(client.resumeAudit).toHaveBeenCalledTimes(1)

    finish({ ...interrupted, status: 'running' })
    await waitFor(() => expect(sse.connectAuditStream).toHaveBeenCalledTimes(1))
  })
})

describe('App — Retomar: recuperação e outra auditoria em voo (HIS-03)', () => {
  it('após falha, o botão volta a "Retomar" habilitado e pode tentar de novo', async () => {
    vi.mocked(client.resumeAudit).mockRejectedValueOnce(new Error('credencial ausente'))
    render(<App />)

    const btn = await screen.findByRole('button', { name: 'Retomar auditoria de /proj/beta' })
    fireEvent.click(btn)
    expect(await screen.findByRole('alert')).toHaveTextContent('credencial ausente')
    await waitFor(() => expect(btn).not.toBeDisabled())
    expect(btn).toHaveTextContent('Retomar')

    vi.mocked(client.resumeAudit).mockResolvedValueOnce({ ...interrupted, status: 'running' })
    fireEvent.click(btn)
    await waitFor(() => expect(client.resumeAudit).toHaveBeenCalledTimes(2))
  })

  it('com uma retomada em voo, Retomar de OUTRA auditoria não dispara outra requisição', async () => {
    const other: AuditSummary = { ...interrupted, id: 'i2', project_path: '/proj/gama' }
    vi.mocked(client.listAudits).mockResolvedValue([interrupted, other])
    vi.mocked(client.resumeAudit).mockReturnValue(new Promise(() => {}))   // fica em voo
    render(<App />)

    fireEvent.click(await screen.findByRole('button', { name: 'Retomar auditoria de /proj/beta' }))
    const otherBtn = screen.getByRole('button', { name: 'Retomar auditoria de /proj/gama' })
    expect(otherBtn).not.toBeDisabled()          // só o da auditoria em voo fica desabilitado
    fireEvent.click(otherBtn)

    expect(client.resumeAudit).toHaveBeenCalledTimes(1)
    expect(client.resumeAudit).toHaveBeenCalledWith('i1')
  })
})

// Spec: .specs/features/report-chat-and-sarif/spec.md — UI-02 (ligação App → ChatDock)
describe('App — chat da auditoria aberta', () => {
  it('o ChatDock pergunta sobre a auditoria concluída que está aberta', async () => {
    const done: AuditSummary = { ...interrupted, id: 'c1', status: 'completed',
      project_path: '/proj/ok', health_score: 90, counts: {} }
    vi.mocked(client.listAudits).mockResolvedValue([done])
    vi.mocked(client.getAudit).mockResolvedValue(done)
    vi.mocked(client.getFindings).mockResolvedValue({ findings: [], dimension_summaries: [],
      health_score: 90, executive_summary: 'ok', stack_profile: {} as never })
    vi.mocked(client.chatAudit).mockResolvedValue('Resposta.')
    render(<App />)

    fireEvent.click(await screen.findByText('/proj/ok'))
    const box = await screen.findByRole('textbox', { name: 'Pergunta sobre o resultado' })
    fireEvent.change(box, { target: { value: 'Q?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }))

    await waitFor(() => expect(client.chatAudit).toHaveBeenCalledWith('c1', 'Q?', []))
  })
})
