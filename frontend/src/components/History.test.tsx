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

function setup() {
  const onOpen = vi.fn()
  const onDelete = vi.fn()
  render(<History audits={[audit]} onOpen={onOpen} onDelete={onDelete} />)
  return { onOpen, onDelete }
}

describe('History — exclusão', () => {
  it('UI-01: clicar em excluir não abre a auditoria e pede confirmação', () => {
    const { onOpen, onDelete } = setup()

    fireEvent.click(screen.getByRole('button', { name: 'Excluir auditoria de /proj/alpha' }))

    expect(onOpen).not.toHaveBeenCalled()
    expect(onDelete).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Confirmar exclusão' })).toBeInTheDocument()
  })

  it('UI-02: só a confirmação chama onDelete com a auditoria', () => {
    const { onOpen, onDelete } = setup()

    fireEvent.click(screen.getByRole('button', { name: 'Excluir auditoria de /proj/alpha' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar exclusão' }))

    expect(onDelete).toHaveBeenCalledTimes(1)
    expect(onDelete).toHaveBeenCalledWith(audit)
    expect(onOpen).not.toHaveBeenCalled()
  })

  it('UI-02: cancelar volta ao estado inicial sem excluir', () => {
    const { onDelete } = setup()

    fireEvent.click(screen.getByRole('button', { name: 'Excluir auditoria de /proj/alpha' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

    expect(onDelete).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: 'Confirmar exclusão' })).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Excluir auditoria de /proj/alpha' }),
    ).toBeInTheDocument()
  })

  it('UI-01: clicar na linha continua abrindo a auditoria', () => {
    const { onOpen } = setup()

    fireEvent.click(screen.getByText('/proj/alpha'))

    expect(onOpen).toHaveBeenCalledWith(audit)
  })
})
