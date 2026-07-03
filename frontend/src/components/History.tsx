import type { AuditSummary } from '../types'

const STATUS_LABEL: Record<string, string> = {
  started: 'iniciada',
  running: 'em execução',
  waiting_input: 'aguardando resposta',
  completed: 'concluída',
  error: 'erro',
}

const STATUS_TONE: Record<string, string> = {
  completed: 'text-emerald-400',
  error: 'text-sev-critical',
  running: 'text-[color:var(--stamp)]',
  waiting_input: 'text-[color:var(--stamp)]',
}

interface Props {
  audits: AuditSummary[]
  onOpen: (a: AuditSummary) => void
}

/** Histórico de auditorias locais — clique reabre os achados (ou o stream, se em curso). */
export default function History({ audits, onOpen }: Props) {
  if (audits.length === 0) return null
  return (
    <section className="space-y-2">
      <p className="eyebrow">Histórico · {audits.length}</p>
      <ul className="space-y-1.5">
        {audits.map((a) => (
          <li key={a.id}>
            <button
              type="button"
              onClick={() => onOpen(a)}
              className="card flex w-full items-center justify-between gap-4 text-left transition-colors hover:border-[color:var(--stamp)]"
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate font-mono text-sm">{a.project_path}</span>
                {a.goal && (
                  <span className="block truncate text-xs text-[color:var(--dim)]">{a.goal}</span>
                )}
              </span>
              <span className={`eyebrow shrink-0 ${STATUS_TONE[a.status] ?? ''}`}>
                {STATUS_LABEL[a.status] ?? a.status}
                {a.health_score != null && (
                  <span className="text-[color:var(--dim)]"> · {a.health_score}/100</span>
                )}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
