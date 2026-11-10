// Spec: .specs/features/report-chat-and-sarif/spec.md — UI-02, UI-03
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import * as client from '../api/client'
import ChatDock from './ChatDock'

vi.mock('../api/client', () => ({ chatAudit: vi.fn() }))

const input = () => screen.getByRole('textbox', { name: 'Pergunta sobre o resultado' })
const send = () => screen.getByRole('button', { name: 'Enviar' })

async function ask(text: string) {
  fireEvent.change(input(), { target: { value: text } })
  fireEvent.click(send())
  await waitFor(() => expect(input()).not.toBeDisabled())
}

afterEach(() => vi.clearAllMocks())

describe('ChatDock', () => {
  it('UI-02: envia a pergunta e mostra pergunta + resposta em Markdown', async () => {
    vi.mocked(client.chatAudit).mockResolvedValueOnce('O mais grave é **Senha hardcoded**.')
    render(<ChatDock auditId="a1" />)

    await ask('Qual o mais grave?')

    expect(client.chatAudit).toHaveBeenCalledWith('a1', 'Qual o mais grave?', [])
    expect(screen.getByText('Qual o mais grave?')).toBeInTheDocument()
    expect(screen.getByText('Senha hardcoded').tagName).toBe('STRONG')
    expect(input()).toHaveValue('')
  })

  it('UI-02: reenvia o histórico (últimas 10 trocas, em ordem)', async () => {
    vi.mocked(client.chatAudit).mockImplementation(async (_id, q) => `R:${q}`)
    render(<ChatDock auditId="a1" />)

    await ask('Q1')
    await ask('Q2')
    expect(vi.mocked(client.chatAudit).mock.calls[1][2]).toEqual([
      { role: 'user', content: 'Q1' }, { role: 'assistant', content: 'R:Q1' },
    ])
    for (const q of ['Q3', 'Q4', 'Q5', 'Q6', 'Q7']) await ask(q)
    const calls = vi.mocked(client.chatAudit).mock.calls
    const history = calls[calls.length - 1][2]
    expect(history).toHaveLength(10)                    // 12 mensagens antes de Q7 → últimas 10
    expect(history[0]).toEqual({ role: 'user', content: 'Q2' })       // Q1 e R:Q1 caíram
    expect(history[history.length - 1]).toEqual({ role: 'assistant', content: 'R:Q6' })
  })

  it('UI-03: pergunta vazia não é enviada', () => {
    render(<ChatDock auditId="a1" />)
    fireEvent.change(input(), { target: { value: '   ' } })
    expect(send()).toBeDisabled()
    fireEvent.click(send())
    expect(client.chatAudit).not.toHaveBeenCalled()
  })

  it('UI-03: desabilita enquanto espera a resposta', async () => {
    vi.mocked(client.chatAudit).mockReturnValue(new Promise(() => {}))
    render(<ChatDock auditId="a1" />)
    fireEvent.change(input(), { target: { value: 'Q' } })
    fireEvent.click(send())

    await waitFor(() => expect(input()).toBeDisabled())
    expect(send()).toBeDisabled()
  })

  it('UI-03: erro da API aparece e a pergunta fica no campo', async () => {
    vi.mocked(client.chatAudit).mockRejectedValueOnce(new Error('Falha ao consultar o LLM: rate limit'))
    render(<ChatDock auditId="a1" />)
    await ask('Q?')

    expect(screen.getByRole('alert')).toHaveTextContent('Falha ao consultar o LLM: rate limit')
    expect(input()).toHaveValue('Q?')
  })
})
