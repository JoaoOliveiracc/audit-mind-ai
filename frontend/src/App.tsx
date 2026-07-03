import { useEffect, useReducer, useRef, useState } from 'react'

import {
  createAudit,
  getAudit,
  getFindings,
  getProviders,
  listAudits,
  submitAnswers,
} from './api/client'
import { connectAuditStream, type AuditStream } from './api/sse'
import ChatDock from './components/ChatDock'
import History from './components/History'
import ResultsPanel from './components/ResultsPanel'
import StartForm from './components/StartForm'
import Timeline from './components/Timeline'
import { auditReducer, initialState } from './state/auditReducer'
import type { AuditSummary, CreateAuditRequest, Finding, ProviderInfo } from './types'

/** Conta achados por severidade (fallback quando o resumo não traz `counts`). */
function countBySeverity(findings: Finding[]): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const f of findings) counts[f.severity] = (counts[f.severity] ?? 0) + 1
  return counts
}

export default function App() {
  const [state, dispatch] = useReducer(auditReducer, initialState)
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [history, setHistory] = useState<AuditSummary[]>([])
  const [startError, setStartError] = useState<string | null>(null)
  const [auditId, setAuditId] = useState<string | null>(null)
  const [projectPath, setProjectPath] = useState<string | null>(null)
  const streamRef = useRef<AuditStream | null>(null)

  const refreshHistory = () => listAudits().then(setHistory).catch(() => setHistory([]))

  useEffect(() => {
    getProviders().then(setProviders).catch(() => setProviders([]))
    refreshHistory()
    return () => streamRef.current?.close()
  }, [])

  const running = state.status === 'running' || state.status === 'awaiting_clarify'

  const openStream = (id: string) => {
    streamRef.current = connectAuditStream(id, {
      onPhase: (e) => {
        dispatch({ type: 'PHASE', event: e })
        if (e.node === 'discovery') {
          // O evento phase não carrega dados; o snapshot do estado do grafo traz o stack profile.
          getFindings(id)
            .then((p) => dispatch({ type: 'SNAPSHOT', stackProfile: p.stack_profile }))
            .catch(() => {})
        }
      },
      onInvestigator: (e) => dispatch({ type: 'INVESTIGATOR', event: e }),
      onVerification: (e) => dispatch({ type: 'VERIFICATION', event: e }),
      onAdversarial: (e) => dispatch({ type: 'ADVERSARIAL', event: e }),
      onClarification: (e) => dispatch({ type: 'CLARIFY', questions: e.questions }),
      onCompleted: (e) => {
        streamRef.current?.close() // evita replay na reconexão automática do EventSource
        dispatch({ type: 'COMPLETED', event: e })
        getFindings(id)
          .then((p) => dispatch({ type: 'RESULTS', payload: p }))
          .catch((err) => dispatch({ type: 'ERROR', message: String(err) }))
      },
      onError: (message) => {
        streamRef.current?.close()
        dispatch({ type: 'ERROR', message })
      },
    })
  }

  const handleStart = async (req: CreateAuditRequest) => {
    setStartError(null)
    try {
      const summary = await createAudit(req)
      setAuditId(summary.id)
      setProjectPath(req.project_path)
      dispatch({ type: 'START' })
      openStream(summary.id)
    } catch (err) {
      setStartError(err instanceof Error ? err.message : String(err))
    }
  }

  const handleClarify = async (answers: Record<string, string>) => {
    if (!auditId) return
    try {
      await submitAnswers(auditId, answers)
      dispatch({ type: 'CLARIFY_SUBMITTED' })
    } catch (err) {
      dispatch({ type: 'ERROR', message: err instanceof Error ? err.message : String(err) })
    }
  }

  const handleReset = () => {
    streamRef.current?.close()
    streamRef.current = null
    setAuditId(null)
    setProjectPath(null)
    dispatch({ type: 'RESET' })
    refreshHistory()
  }

  /** Reabre uma auditoria do histórico: completa → carrega achados; em curso → reconecta o stream. */
  const handleOpenAudit = async (summary: AuditSummary) => {
    streamRef.current?.close()
    setStartError(null)
    // Revalida o status: a lista pode estar defasada (auditoria concluiu desde então).
    const a = await getAudit(summary.id).catch(() => summary)
    setAuditId(a.id)
    setProjectPath(a.project_path)
    if (a.status === 'completed') {
      try {
        const payload = await getFindings(a.id)
        const counts = a.counts ?? countBySeverity(payload.findings)
        dispatch({
          type: 'COMPLETED',
          event: { health_score: a.health_score ?? payload.health_score ?? 0, counts },
        })
        dispatch({ type: 'RESULTS', payload })
      } catch (err) {
        setStartError(err instanceof Error ? err.message : String(err))
      }
    } else {
      // running / waiting_input / error: o runner faz replay do log acumulado.
      dispatch({ type: 'START' })
      openStream(a.id)
    }
  }

  return (
    <div className="mx-auto flex min-h-full max-w-3xl flex-col gap-6 px-4 py-8">
      <header className="flex items-baseline justify-between border-b border-[color:var(--line)] pb-4">
        <div>
          <h1 className="font-mono text-lg font-bold tracking-tight">
            Auditor-IA<span className="text-[color:var(--stamp)]">_</span>
          </h1>
          <p className="eyebrow mt-1">dossiê de auditoria · agente LangGraph</p>
        </div>
        {projectPath && (
          <div className="flex items-center gap-3">
            <span className="hidden font-mono text-xs text-[color:var(--dim)] sm:block">
              {projectPath}
            </span>
            {!running && state.status !== 'idle' && (
              <button type="button" className="btn !text-xs" onClick={handleReset}>
                Nova auditoria
              </button>
            )}
          </div>
        )}
      </header>

      <main className="flex-1 space-y-6">
        {state.status === 'idle' && (
          <>
            <StartForm providers={providers} busy={false} onStart={handleStart} />
            {startError && (
              <p className="card break-words text-sm text-sev-critical" role="alert">
                {startError}
              </p>
            )}
            <History audits={history} onOpen={handleOpenAudit} />
          </>
        )}

        {state.status !== 'idle' && <Timeline state={state} onClarifySubmit={handleClarify} />}

        {state.status === 'finished' && state.results && auditId && state.completed && (
          <>
            <ResultsPanel
              auditId={auditId}
              payload={state.results}
              counts={state.completed.counts}
            />
            <ChatDock />
          </>
        )}
      </main>
    </div>
  )
}
