import { useEffect, useReducer, useRef, useState } from 'react'

import {
  createAudit,
  deleteAudit,
  getAudit,
  getFindings,
  getDefaults,
  getProviders,
  listAudits,
  resumeAudit,
  submitAnswers,
} from './api/client'
import { connectAuditStream, type AuditStream } from './api/sse'
import ChatDock from './components/ChatDock'
import History from './components/History'
import LanguageToggle from './components/LanguageToggle'
import ResultsPanel from './components/ResultsPanel'
import StartForm from './components/StartForm'
import Timeline from './components/Timeline'
import { errorNotice, noticeText, useI18n } from './i18n/I18nProvider'
import { auditReducer, initialState } from './state/auditReducer'
import type { AuditSummary, CreateAuditRequest, Finding, Notice, ProviderInfo } from './types'

/** Conta achados por severidade (fallback quando o resumo não traz `counts`). */
function countBySeverity(findings: Finding[]): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const f of findings) counts[f.severity] = (counts[f.severity] ?? 0) + 1
  return counts
}

export default function App() {
  const { t } = useI18n()
  const [state, dispatch] = useReducer(auditReducer, initialState)
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [vulnScanDefault, setVulnScanDefault] = useState(false)
  const [history, setHistory] = useState<AuditSummary[]>([])
  // Guardado como aviso (não texto) para acompanhar a troca de idioma (LOC-03).
  const [startError, setStartError] = useState<Notice | null>(null)
  const [auditId, setAuditId] = useState<string | null>(null)
  const [projectPath, setProjectPath] = useState<string | null>(null)
  /** Auditoria com retomada em voo (desabilita o botão; evita 409 de clique duplo). */
  const [resumingId, setResumingId] = useState<string | null>(null)
  const streamRef = useRef<AuditStream | null>(null)

  const refreshHistory = () => listAudits().then(setHistory).catch(() => setHistory([]))

  useEffect(() => {
    getProviders().then(setProviders).catch(() => setProviders([]))
    getDefaults()
      .then((d) => setVulnScanDefault(d.vuln_scan))
      .catch(() => setVulnScanDefault(false))
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
          .catch((err) => dispatch({ type: 'ERROR', message: errorNotice(err) }))
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
      setStartError(errorNotice(err))
    }
  }

  const handleClarify = async (answers: Record<string, string>) => {
    if (!auditId) return
    try {
      await submitAnswers(auditId, answers)
      dispatch({ type: 'CLARIFY_SUBMITTED' })
    } catch (err) {
      dispatch({ type: 'ERROR', message: errorNotice(err) })
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

  /** Exclui uma auditoria do histórico; erros da API (ex.: 409 em execução) aparecem no alerta. */
  const handleDeleteAudit = async (summary: AuditSummary) => {
    setStartError(null)
    try {
      await deleteAudit(summary.id)
    } catch (err) {
      setStartError(errorNotice(err))
    }
    refreshHistory()
  }

  /** Retoma uma auditoria interrompida e conecta ao stream ao vivo. */
  const handleResumeAudit = async (summary: AuditSummary) => {
    if (resumingId) return
    setResumingId(summary.id)
    streamRef.current?.close()
    setStartError(null)
    try {
      const a = await resumeAudit(summary.id)
      setAuditId(a.id)
      setProjectPath(a.project_path)
      dispatch({ type: 'START' })
      openStream(a.id)
    } catch (err) {
      setStartError(errorNotice(err))
      refreshHistory()
    } finally {
      setResumingId(null)
    }
  }

  /** Reabre uma auditoria do histórico: completa → carrega achados; em curso → reconecta o stream. */
  const handleOpenAudit = async (summary: AuditSummary) => {
    streamRef.current?.close()
    setStartError(null)
    // Revalida o status: a lista pode estar defasada (auditoria concluiu desde então).
    const a = await getAudit(summary.id).catch(() => summary)
    // Sem runner vivo, o stream daria 404 ("Conexão perdida"): orienta em vez de conectar.
    if (a.status === 'interrupted') {
      setStartError({ code: 'audit_interrupted' })
      return
    }
    if (a.status === 'error') {
      setStartError({ code: 'audit_failed', detail: a.error })
      return
    }
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
        setStartError(errorNotice(err))
      }
    } else {
      // running / waiting_input: o runner (vivo) faz replay do log acumulado.
      dispatch({ type: 'START' })
      openStream(a.id)
    }
  }

  return (
    <div className="mx-auto flex min-h-full max-w-3xl flex-col gap-6 px-4 py-8">
      <header className="flex items-baseline justify-between border-b border-[color:var(--line)] pb-4">
        <div>
          <h1 className="font-mono text-lg font-bold tracking-tight">
            Audit Mind AI<span className="text-[color:var(--stamp)]">_</span>
          </h1>
          <p className="eyebrow mt-1">{t.app.tagline}</p>
        </div>
        <div className="flex items-center gap-3">
          {projectPath && (
            <span className="hidden font-mono text-xs text-[color:var(--dim)] sm:block">
              {projectPath}
            </span>
          )}
          {projectPath && !running && state.status !== 'idle' && (
            <button type="button" className="btn !text-xs" onClick={handleReset}>
              {t.app.newAudit}
            </button>
          )}
          <LanguageToggle />
        </div>
      </header>

      <main className="flex-1 space-y-6">
        {state.status === 'idle' && (
          <>
            <StartForm providers={providers} busy={false} onStart={handleStart} vulnScanDefault={vulnScanDefault} />
            {startError && (
              <p className="card break-words text-sm text-sev-critical" role="alert">
                {noticeText(t, startError)}
              </p>
            )}
            <History audits={history} onOpen={handleOpenAudit} onDelete={handleDeleteAudit}
              onResume={handleResumeAudit}
              busyId={resumingId}
            />
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
            <ChatDock auditId={auditId} />
          </>
        )}
      </main>
    </div>
  )
}
