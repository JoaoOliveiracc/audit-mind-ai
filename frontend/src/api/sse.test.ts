// Spec: .specs/features/web-i18n/spec.md — I18N-01 (erro do cliente vira código, não texto fixo) — fix loop M17
import { connectAuditStream } from './sse'

class FakeEventSource {
  static CLOSED = 2
  static last: FakeEventSource
  readyState = 1
  onerror: (() => void) | null = null
  listeners: Record<string, (ev: MessageEvent) => void> = {}
  constructor(public url: string) {
    FakeEventSource.last = this
  }
  addEventListener(name: string, fn: (ev: MessageEvent) => void) {
    this.listeners[name] = fn
  }
  close() {}
}

const handlers = () => ({
  onPhase: vi.fn(), onInvestigator: vi.fn(), onVerification: vi.fn(), onAdversarial: vi.fn(),
  onClarification: vi.fn(), onCompleted: vi.fn(), onError: vi.fn(),
})

beforeEach(() => vi.stubGlobal('EventSource', FakeEventSource))
afterEach(() => vi.unstubAllGlobals())

describe('connectAuditStream — erros', () => {
  it('conexão fechada emite o código connection_lost (traduzido na UI)', () => {
    const h = handlers()
    connectAuditStream('a1', h)
    FakeEventSource.last.readyState = FakeEventSource.CLOSED
    FakeEventSource.last.onerror?.()
    expect(h.onError).toHaveBeenCalledWith({ code: 'connection_lost' })
  })

  it('reconexão em andamento (não fechada) não emite erro', () => {
    const h = handlers()
    connectAuditStream('a1', h)
    FakeEventSource.last.onerror?.()
    expect(h.onError).not.toHaveBeenCalled()
  })

  it('evento error do servidor repassa a mensagem como veio', () => {
    const h = handlers()
    connectAuditStream('a1', h)
    FakeEventSource.last.listeners.error({ data: JSON.stringify({ message: 'falha no LLM' }) } as MessageEvent)
    expect(h.onError).toHaveBeenCalledWith('falha no LLM')
  })
})
