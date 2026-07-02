import { useMemo, useState } from 'react'
import Markdown from 'react-markdown'

import { reportUrl } from '../api/client'
import { SEVERITY_LABEL, SEVERITY_ORDER } from '../state/score'
import type { FindingsPayload } from '../types'
import FindingCard from './FindingCard'
import HealthStamp from './HealthStamp'

interface Props {
  auditId: string
  payload: FindingsPayload
  counts: Record<string, number>
}

/** Painel final: carimbo do score, resumo executivo, filtros e achados. */
export default function ResultsPanel({ auditId, payload, counts }: Props) {
  const results = payload
  const [sevFilter, setSevFilter] = useState<string | null>(null)
  const [dimFilter, setDimFilter] = useState<string | null>(null)

  const dims = useMemo(
    () => [...new Set(results.findings.map((f) => f.dimension))].sort(),
    [results.findings],
  )
  const filtered = results.findings.filter(
    (f) =>
      (sevFilter === null || f.severity === sevFilter) &&
      (dimFilter === null || f.dimension === dimFilter),
  )

  return (
    <section className="space-y-5">
      <div className="card flex flex-col items-start gap-5 sm:flex-row sm:items-center">
        <HealthStamp score={results.health_score ?? 0} />
        <div className="min-w-0 flex-1">
          <p className="eyebrow mb-2">Parecer do auditor</p>
          <div className="space-y-1.5 text-sm [&_h1]:text-base [&_h1]:font-semibold [&_h2]:text-sm [&_h2]:font-semibold [&_h3]:text-sm [&_h3]:font-medium [&_code]:font-mono [&_code]:text-xs [&_li]:ml-4 [&_li]:list-disc [&_strong]:text-[color:var(--stamp)]">
            <Markdown>{results.executive_summary || '_(resumo não gerado)_'}</Markdown>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="eyebrow mr-1">
          {results.findings.length} achado{results.findings.length === 1 ? '' : 's'}
        </span>
        {SEVERITY_ORDER.map((sev) => {
          const n = counts[sev] ?? 0
          if (n === 0) return null
          const active = sevFilter === sev
          return (
            <button
              key={sev}
              type="button"
              className={`btn !px-2 !py-0.5 !text-xs ${active ? '!border-[color:var(--stamp)] !text-[color:var(--stamp)]' : ''}`}
              onClick={() => setSevFilter(active ? null : sev)}
              aria-pressed={active}
            >
              {SEVERITY_LABEL[sev]} · {n}
            </button>
          )
        })}
        {dims.length > 1 && (
          <select
            className="field !w-auto !py-1 text-xs"
            value={dimFilter ?? ''}
            onChange={(e) => setDimFilter(e.target.value || null)}
            aria-label="Filtrar por dimensão"
          >
            <option value="">todas as dimensões</option>
            {dims.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="space-y-2">
        {filtered.map((f, i) => (
          <FindingCard key={`${f.dimension}-${f.title}-${i}`} finding={f} />
        ))}
        {filtered.length === 0 && (
          <p className="card text-sm text-[color:var(--dim)]">
            Nenhum achado com esses filtros.
          </p>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <a
          className="btn btn-primary"
          href={reportUrl(auditId, 'html')}
          target="_blank"
          rel="noreferrer"
        >
          Abrir relatório HTML
        </a>
        <a className="btn" href={reportUrl(auditId, 'md')} download="auditoria.md">
          Baixar Markdown
        </a>
      </div>
    </section>
  )
}
