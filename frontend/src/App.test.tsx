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
