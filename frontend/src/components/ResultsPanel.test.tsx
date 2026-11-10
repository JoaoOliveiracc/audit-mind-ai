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

    const link = screen.getByRole('link', { name: 'Baixar SARIF' })
    expect(link).toHaveAttribute('href', '/audits/a1/report?format=sarif')
    expect(link).toHaveAttribute('download', 'auditoria.sarif')
  })
})
