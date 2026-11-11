// Spec: .specs/features/report-chat-and-sarif/spec.md — UI-01
import { render, screen } from '@testing-library/react'

import type { FindingsPayload } from '../types'
import ResultsPanel from './ResultsPanel'

const payload: FindingsPayload = {
  findings: [],
  dimension_summaries: [],
  health_score: 100,
  executive_summary: 'ok',
  stack_profile: {} as FindingsPayload['stack_profile'],
}

describe('ResultsPanel — exportação', () => {
  it('UI-01: oferece o download do SARIF', () => {
    render(<ResultsPanel auditId="a1" payload={payload} counts={{}} />)

    const link = screen.getByRole('link', { name: 'Download SARIF' })
    expect(link).toHaveAttribute('href', '/audits/a1/report?format=sarif')
    expect(link).toHaveAttribute('download', 'audit.sarif')
  })
})

describe('ResultsPanel — status da varredura de dependências (RPT-01)', () => {
  it('mostra a linha de status e os motivos de varredura incompleta', () => {
    render(
      <ResultsPanel
        auditId="a1"
        counts={{}}
        payload={{
          ...payload,
          dependency_scan_status: {
            headline: 'Varredura de dependências incompleta',
            incomplete: true,
            reasons: ['querybatch: timeout'],
          },
        }}
      />,
    )
    const status = screen.getByRole('status', { name: 'Dependencies' })
    expect(status).toHaveTextContent('Varredura de dependências incompleta')
    expect(status).toHaveTextContent('querybatch: timeout')
  })

  it('auditoria sem o campo (anterior ao G48) não mostra a linha', () => {
    render(<ResultsPanel auditId="a1" payload={payload} counts={{}} />)
    expect(screen.queryByRole('status', { name: 'Dependencies' })).not.toBeInTheDocument()
  })
})
