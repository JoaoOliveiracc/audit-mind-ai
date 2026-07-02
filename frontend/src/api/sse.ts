import type {
  ClarificationEvent,
  CompletedEvent,
  ErrorEvent,
  InvestigatorEvent,
  PhaseEvent,
} from '../types'

export interface StreamHandlers {
  onPhase: (e: PhaseEvent) => void
  onInvestigator: (e: InvestigatorEvent) => void
  onClarification: (e: ClarificationEvent) => void
  onCompleted: (e: CompletedEvent) => void
  onError: (message: string) => void
}

export interface AuditStream {
  close: () => void
}

/** Assina o SSE da auditoria e despacha os eventos nomeados tipados.
 *
 * Quem consome DEVE chamar ``close()`` ao receber ``completed``/``error`` —
 * senão o EventSource reconecta e o backend faz replay dos eventos.
 */
export function connectAuditStream(auditId: string, h: StreamHandlers): AuditStream {
  const es = new EventSource(`/audits/${auditId}/stream`)

  const on = <T>(name: string, fn: (data: T) => void) =>
    es.addEventListener(name, (ev) => {
      try {
        fn(JSON.parse((ev as MessageEvent).data) as T)
      } catch {
        /* ignora frame malformado */
      }
    })

  on<PhaseEvent>('phase', h.onPhase)
  on<InvestigatorEvent>('investigator', h.onInvestigator)
  on<ClarificationEvent>('clarification', h.onClarification)
  on<CompletedEvent>('completed', h.onCompleted)
  on<ErrorEvent>('error', (e) => h.onError(e.message))

  es.onerror = () => {
    // Conexão perdida com o backend (EventSource tenta reconectar sozinho).
    if (es.readyState === EventSource.CLOSED) {
      h.onError('Conexão com o servidor perdida.')
    }
  }

  return { close: () => es.close() }
}
