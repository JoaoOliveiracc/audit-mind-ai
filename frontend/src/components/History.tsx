import { useState } from 'react'

import { labelOf, useI18n } from '../i18n/I18nProvider'
import type { AuditSummary } from '../types'

const STATUS_TONE: Record<string, string> = {
  completed: 'text-emerald-400',
  error: 'text-sev-critical',
  running: 'text-[color:var(--stamp)]',
  waiting_input: 'text-[color:var(--stamp)]',
}

interface Props {
  audits: AuditSummary[]
  onOpen: (a: AuditSummary) => void
  /** Exclusão (metadados + checkpoints + relatórios) — chamada só após confirmação inline. */
  onDelete: (a: AuditSummary) => void
  /** Retomada de auditoria `interrupted` (órfã após restart da API). */
  onResume: (a: AuditSummary) => void
  /** Id com retomada em voo: o botão Retomar fica desabilitado ("Retomando…"). */
  busyId?: string | null
}

/** Histórico de auditorias locais — clique reabre os achados (ou o stream, se em curso). */
export default function History({ audits, onOpen, onDelete, onResume, busyId = null }: Props) {
  const { t } = useI18n()
  const [confirmingId, setConfirmingId] = useState<string | null>(null)
  if (audits.length === 0) return null
  return (
    <section className="space-y-2">
      <p className="eyebrow">{t.history.title(audits.length)}</p>
      <ul className="space-y-1.5">
        {audits.map((a) => (
          <li key={a.id} className="flex items-stretch gap-1.5">
            <button
              type="button"
              onClick={() => onOpen(a)}
              className="card flex min-w-0 flex-1 items-center justify-between gap-4 text-left transition-colors hover:border-[color:var(--stamp)]"
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate font-mono text-sm">{a.project_path}</span>
                {a.goal && (
                  <span className="block truncate text-xs text-[color:var(--dim)]">{a.goal}</span>
                )}
              </span>
              <span className={`eyebrow shrink-0 ${STATUS_TONE[a.status] ?? ''}`}>
                {labelOf(t.common.status, a.status)}
                {a.health_score != null && (
                  <span className="text-[color:var(--dim)]"> · {a.health_score}/100</span>
                )}
              </span>
            </button>
            {a.status === 'interrupted' && (
              <button
                type="button"
                className="btn shrink-0 !px-2 !text-xs"
                aria-label={t.history.resumeLabel(a.project_path)}
                title={t.history.resumeTitle}
                disabled={busyId === a.id}
                onClick={() => onResume(a)}
              >
                {busyId === a.id ? t.history.resuming : t.history.resume}
              </button>
            )}
            {confirmingId === a.id ? (
              <span className="flex shrink-0 items-center gap-1">
                <button
                  type="button"
                  className="btn !px-2 !text-xs !border-sev-critical !text-sev-critical"
                  onClick={() => {
                    setConfirmingId(null)
                    onDelete(a)
                  }}
                >
                  {t.history.confirmDelete}
                </button>
                <button
                  type="button"
                  className="btn !px-2 !text-xs"
                  onClick={() => setConfirmingId(null)}
                >
                  {t.common.cancel}
                </button>
              </span>
            ) : (
              <button
                type="button"
                className="btn shrink-0 !px-2 !text-xs"
                aria-label={t.history.deleteLabel(a.project_path)}
                title={t.history.deleteTitle}
                onClick={() => setConfirmingId(a.id)}
              >
                {t.history.delete}
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
