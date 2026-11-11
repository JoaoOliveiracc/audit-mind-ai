// Spec: .specs/features/audit-retention/spec.md — UI-01, UI-02
import { fireEvent, render, screen } from '@testing-library/react'

import type { AuditSummary } from '../types'
import History from './History'

const audit: AuditSummary = {
  id: 'a1',
  status: 'completed',
  project_path: '/proj/alpha',
  created_at: '2026-11-10T10:00:00+00:00',
  health_score: 80,
}

function setup(audits: AuditSummary[] = [audit]) {
  const onOpen = vi.fn()
  const onDelete = vi.fn()
  const onResume = vi.fn()
  render(<History audits={audits} onOpen={onOpen} onDelete={onDelete} onResume={onResume} />)
  return { onOpen, onDelete, onResume }
}

describe('History — exclusão', () => {
  it('UI-01: clicar em excluir não abre a auditoria e pede confirmação', () => {
    const { onOpen, onDelete } = setup()

    fireEvent.click(screen.getByRole('button', { name: 'Delete audit of /proj/alpha' }))

    expect(onOpen).not.toHaveBeenCalled()
    expect(onDelete).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Confirm deletion' })).toBeInTheDocument()
  })

  it('UI-02: só a confirmação chama onDelete com a auditoria', () => {
    const { onOpen, onDelete } = setup()

    fireEvent.click(screen.getByRole('button', { name: 'Delete audit of /proj/alpha' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm deletion' }))

    expect(onDelete).toHaveBeenCalledTimes(1)
    expect(onDelete).toHaveBeenCalledWith(audit)
    expect(onOpen).not.toHaveBeenCalled()
  })

  it('UI-02: cancelar volta ao estado inicial sem excluir', () => {
    const { onDelete } = setup()

    fireEvent.click(screen.getByRole('button', { name: 'Delete audit of /proj/alpha' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(onDelete).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: 'Confirm deletion' })).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Delete audit of /proj/alpha' }),
    ).toBeInTheDocument()
  })

  it('UI-01: clicar na linha continua abrindo a auditoria', () => {
    const { onOpen } = setup()

    fireEvent.click(screen.getByText('/proj/alpha'))

    expect(onOpen).toHaveBeenCalledWith(audit)
  })
})

// Spec: .specs/features/api-hardening/spec.md — UI-01, UI-02
describe('History — retomada', () => {
  const interrupted: AuditSummary = {
    ...audit, id: 'i1', status: 'interrupted', project_path: '/proj/beta', health_score: null,
  }

  it('UI-01: interrompida mostra o rótulo e o botão Retomar; outros status não', () => {
    setup([audit, interrupted])

    expect(screen.getByText('interrupted')).toBeInTheDocument()
    const buttons = screen.getAllByRole('button', { name: /^Resume audit of / })
    expect(buttons).toHaveLength(1)
    expect(buttons[0]).toHaveAccessibleName('Resume audit of /proj/beta')
  })

  it('UI-02: Retomar chama onResume com a auditoria e não abre', () => {
    const { onOpen, onResume, onDelete } = setup([interrupted])

    fireEvent.click(screen.getByRole('button', { name: 'Resume audit of /proj/beta' }))

    expect(onResume).toHaveBeenCalledTimes(1)
    expect(onResume).toHaveBeenCalledWith(interrupted)
    expect(onOpen).not.toHaveBeenCalled()
    expect(onDelete).not.toHaveBeenCalled()
  })
})

describe('History — Retomar só para interrompidas (UI-01)', () => {
  it.each(['started', 'running', 'waiting_input', 'completed', 'error'])(
    'status %s não mostra Retomar',
    (status) => {
      setup([{ ...audit, status }])
      expect(screen.queryByRole('button', { name: /^Resume audit of / })).not.toBeInTheDocument()
    },
  )
})
