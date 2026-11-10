// Spec: .specs/features/vuln-scan/spec.md — UI-01
import { fireEvent, render, screen } from '@testing-library/react'

import StartForm from './StartForm'

const LABEL = 'Verificar dependências vulneráveis (envia nomes e versões ao OSV.dev)'

function setup() {
  const onStart = vi.fn()
  render(<StartForm providers={[]} busy={false} onStart={onStart} />)
  fireEvent.change(screen.getByLabelText('Caminho do projeto'), { target: { value: '/proj/a' } })
  return onStart
}

describe('StartForm — varredura de dependências (UI-01)', () => {
  it('checkbox visível sem abrir opções avançadas e desligado por padrão', () => {
    setup()
    expect(screen.getByRole('checkbox', { name: LABEL })).not.toBeChecked()
  })

  it('desligado: envia vuln_scan false', () => {
    const onStart = setup()
    fireEvent.click(screen.getByRole('button', { name: 'Iniciar auditoria' }))
    expect(onStart).toHaveBeenCalledWith(expect.objectContaining({ project_path: '/proj/a', vuln_scan: false }))
  })

  it('marcado: envia vuln_scan true', () => {
    const onStart = setup()
    fireEvent.click(screen.getByRole('checkbox', { name: LABEL }))
    fireEvent.click(screen.getByRole('button', { name: 'Iniciar auditoria' }))
    expect(onStart).toHaveBeenCalledWith(expect.objectContaining({ vuln_scan: true }))
  })
})

describe('StartForm — padrão do servidor (AUDITOR_VULN_SCAN)', () => {
  it('parte do padrão do servidor quando ele chega depois da montagem', () => {
    const onStart = vi.fn()
    const { rerender } = render(<StartForm providers={[]} busy={false} onStart={onStart} />)
    rerender(<StartForm providers={[]} busy={false} onStart={onStart} vulnScanDefault />)
    expect(screen.getByRole('checkbox', { name: LABEL })).toBeChecked()
    fireEvent.change(screen.getByLabelText('Caminho do projeto'), { target: { value: '/proj/a' } })
    fireEvent.click(screen.getByRole('button', { name: 'Iniciar auditoria' }))
    expect(onStart).toHaveBeenCalledWith(expect.objectContaining({ vuln_scan: true }))
  })

  it('a escolha do usuário não é sobrescrita pelo padrão tardio', () => {
    const onStart = vi.fn()
    const { rerender } = render(<StartForm providers={[]} busy={false} onStart={onStart} />)
    fireEvent.click(screen.getByRole('checkbox', { name: LABEL }))   // liga
    fireEvent.click(screen.getByRole('checkbox', { name: LABEL }))   // desliga de novo
    rerender(<StartForm providers={[]} busy={false} onStart={onStart} vulnScanDefault />)
    expect(screen.getByRole('checkbox', { name: LABEL })).not.toBeChecked()
  })
})
