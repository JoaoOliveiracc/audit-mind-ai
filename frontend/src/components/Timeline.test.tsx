// Spec: .specs/features/investigator-budget/spec.md — UI-01
import { render, screen } from '@testing-library/react'

import { auditReducer, initialState } from '../state/auditReducer'
import type { InvestigatorEvent } from '../types'
import Timeline from './Timeline'

function stateWith(...events: InvestigatorEvent[]) {
  let s = auditReducer(initialState, { type: 'START' })
  for (const event of events) s = auditReducer(s, { type: 'INVESTIGATOR', event })
  return s
}

const ev = (dimension: string, status: InvestigatorEvent['status'], findings_count?: number) =>
  ({ type: 'investigator', dimension, status, index: 1, total: 2, findings_count }) as InvestigatorEvent

describe('Timeline — dimensão parcial (UI-01)', () => {
  it('mostra o rótulo de parcial, a contagem de achados e o ícone de concluída', () => {
    render(<Timeline state={stateWith(ev('security', 'partial', 3))} onClarifySubmit={() => {}} />)

    const row = screen.getByText('security').closest('li') as HTMLElement
    expect(row).toHaveTextContent('parcial — orçamento esgotado')
    expect(row).toHaveTextContent('3 achados')
    expect(row).toHaveTextContent('✓')
    expect(row).not.toHaveTextContent('investigando…')
  })

  it('dimensão concluída normalmente não mostra o rótulo de parcial', () => {
    render(<Timeline state={stateWith(ev('quality', 'done', 1))} onClarifySubmit={() => {}} />)

    const row = screen.getByText('quality').closest('li') as HTMLElement
    expect(row).toHaveTextContent('1 achado')
    expect(row).not.toHaveTextContent('parcial')
  })
})

describe('Timeline — varredura de dependências (G48)', () => {
  const phase = (s: ReturnType<typeof auditReducer>, node: string) =>
    auditReducer(s, { type: 'PHASE', event: { type: 'phase', node, label: node } } as never)

  it('a investigação só conclui depois do nó dependency_scan', () => {
    let s = auditReducer(initialState, { type: 'START' })
    for (const n of ['discovery', 'plan_questions', 'clarify', 'planning', 'audit']) s = phase(s, n)
    const { unmount } = render(<Timeline state={s} onClarifySubmit={() => {}} />)
    expect(screen.getByText('04 · Investigação').closest('li')).not.toHaveAttribute('data-status', 'done')
    unmount()
    s = phase(s, 'dependency_scan')
    render(<Timeline state={s} onClarifySubmit={() => {}} />)
    expect(screen.getByText('04 · Investigação').closest('li')).toHaveAttribute('data-status', 'done')
  })
})

describe('Timeline — retomada de auditoria anterior ao G48', () => {
  it('etapa concluída quando uma etapa posterior já rodou, mesmo sem o evento dependency_scan', () => {
    let s = auditReducer(initialState, { type: 'START' })
    for (const node of ['discovery', 'plan_questions', 'clarify', 'planning', 'audit', 'verify'])
      s = auditReducer(s, { type: 'PHASE', event: { type: 'phase', node, label: node } } as never)
    render(<Timeline state={s} onClarifySubmit={() => {}} />)
    expect(screen.getByText('04 · Investigação').closest('li')).toHaveAttribute('data-status', 'done')
  })
})
