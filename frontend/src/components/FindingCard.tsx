import { useState } from 'react'

import { SEVERITY_LABEL } from '../state/score'
import type { Finding } from '../types'

const SEV_CLASS: Record<string, string> = {
  critical: 'text-sev-critical border-sev-critical',
  high: 'text-sev-high border-sev-high',
  medium: 'text-sev-medium border-sev-medium',
  low: 'text-sev-low border-sev-low',
  info: 'text-sev-info border-sev-info',
}

/** Um achado da auditoria: severidade, local, evidência e recomendação. */
export default function FindingCard({ finding }: { finding: Finding }) {
  const [open, setOpen] = useState(false)
  const sev = SEV_CLASS[finding.severity] ?? SEV_CLASS.info
  const location = finding.file
    ? `${finding.file}${finding.line ? `:${finding.line}` : ''}`
    : null

  return (
    <article className="card !p-0 overflow-hidden">
      <button
        type="button"
        className="flex w-full items-start gap-3 p-3 text-left hover:bg-[color:var(--ink)]"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span
          className={`eyebrow mt-0.5 shrink-0 rounded border px-1.5 py-0.5 !text-current ${sev}`}
        >
          {SEVERITY_LABEL[finding.severity] ?? finding.severity}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium">{finding.title}</span>
          <span className="eyebrow mt-0.5 block">
            {finding.dimension}
            {location && <span className="ml-2 normal-case">{location}</span>}
            <span className="ml-2">confiança {(finding.confidence * 100).toFixed(0)}%</span>
          </span>
        </span>
        <span className="eyebrow mt-1 shrink-0">{open ? '−' : '+'}</span>
      </button>

      {open && (
        <div className="space-y-3 border-t border-[color:var(--line)] p-3 text-sm">
          <p>{finding.description}</p>
          {finding.evidence && (
            <pre className="overflow-x-auto rounded bg-[color:var(--ink)] p-2 font-mono text-xs text-[color:var(--dim)]">
              {finding.evidence}
            </pre>
          )}
          <p>
            <span className="eyebrow mr-2">Recomendação</span>
            {finding.recommendation}
          </p>
        </div>
      )}
    </article>
  )
}
