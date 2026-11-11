import type { ReactNode } from 'react'

import type { AuditUIState, DimensionProgress } from '../state/auditReducer'
import { noticeText, useI18n } from '../i18n/I18nProvider'
import type { StackProfile } from '../types'
import ClarifyForm from './ClarifyForm'

interface Props {
  state: AuditUIState
  onClarifySubmit: (answers: Record<string, string>) => void
}

/** Etapas fixas do pipeline — ordem espelha o grafo (por isso a numeração); rótulos no catálogo. */
const STEPS = [
  { key: 'discovery', nodes: ['discovery'] },
  { key: 'clarify', nodes: ['plan_questions', 'clarify'] },
  { key: 'planning', nodes: ['planning'] },
  { key: 'audit', nodes: ['audit', 'dependency_scan'] }, // G48: varredura de deps logo após o audit
  { key: 'verify', nodes: ['verify'] },
  { key: 'adversarial', nodes: ['adversarial'] },
  { key: 'synthesis', nodes: ['synthesis'] },
  { key: 'report', nodes: ['report'] },
] as const

type StepStatus = 'pending' | 'active' | 'done'

function StackChips({ profile }: { profile: StackProfile }) {
  const { t } = useI18n()
  const chips = [
    ...Object.entries(profile.languages ?? {}).map(([lang, n]) => `${lang} (${n})`),
    ...(profile.frameworks ?? []),
    ...(profile.package_managers ?? []),
    t.timeline.filesAndLoc(profile.total_files ?? 0, profile.total_loc ?? 0),
  ]
  return (
    <div className="flex flex-wrap gap-1.5">
      {chips.map((c) => (
        <span
          key={c}
          className="rounded border border-[color:var(--line)] px-1.5 py-0.5 font-mono text-xs text-[color:var(--dim)]"
        >
          {c}
        </span>
      ))}
    </div>
  )
}

function DimensionRow({ d }: { d: DimensionProgress }) {
  const { t } = useI18n()
  const done = d.status === 'done' || d.status === 'partial' || d.status === 'empty'
  const icon = done ? '✓' : d.status === 'error' ? '✗' : '◌'
  const tone = d.status === 'partial'
    ? 'text-sev-medium'
    : done
    ? 'text-emerald-400'
    : d.status === 'error'
      ? 'text-sev-critical'
      : 'text-[color:var(--stamp)] animate-pulse'
  return (
    <li className="text-sm">
      <div className="flex items-baseline gap-2">
        <span className={`font-mono ${tone}`}>{icon}</span>
        <span className="font-mono">{d.dimension}</span>
        <span className="eyebrow">
          {d.index}/{d.total}
        </span>
        {(d.status === 'done' || d.status === 'partial') && (
          <span className="eyebrow">{t.common.findings(d.findings_count ?? 0)}</span>
        )}
        {d.status === 'partial' && (
          <span className="eyebrow !text-sev-medium">{t.timeline.partial}</span>
        )}
        {d.status === 'empty' && <span className="eyebrow">{t.timeline.emptyResult}</span>}
        {d.status === 'error' && <span className="eyebrow !text-sev-critical">{t.timeline.failed}</span>}
        {d.status === 'start' && <span className="eyebrow">{t.timeline.investigating}</span>}
      </div>
      {d.status === 'error' && d.message && (
        <p className="mt-1 max-w-full whitespace-pre-wrap break-words rounded bg-[color:var(--ink)] p-2 font-mono text-xs leading-relaxed text-sev-critical">
          {d.message}
        </p>
      )}
    </li>
  )
}

function Entry({
  label,
  status,
  children,
}: {
  label: string
  status: StepStatus
  children?: ReactNode
}) {
  const marker =
    status === 'done'
      ? 'border-emerald-400 bg-emerald-400'
      : status === 'active'
        ? 'border-[color:var(--stamp)] bg-[color:var(--stamp)] animate-pulse'
        : 'border-[color:var(--line)] bg-[color:var(--ink)]'
  return (
    <li data-status={status} className={`relative pl-6 ${status === 'pending' ? 'opacity-40' : ''}`}>
      <span aria-hidden className={`absolute left-0 top-1.5 h-2 w-2 rounded-full border ${marker}`} />
      <p className="eyebrow mb-1.5">{label}</p>
      {status !== 'pending' && children ? <div className="card">{children}</div> : null}
    </li>
  )
}

/** Conversa da auditoria como livro-razão: uma entrada por etapa do grafo. */
export default function Timeline({ state, onClarifySubmit }: Props) {
  const { t } = useI18n()
  const done = new Set(state.phasesDone)

  const stepStatus = (i: number): StepStatus => {
    const step = STEPS[i]
    // Concluída também se uma etapa posterior já rodou (ex.: retomada de auditoria anterior ao
    // G48, que nunca emite `dependency_scan`).
    if (step.nodes.every((n) => done.has(n)) || STEPS.slice(i + 1).some((s) => s.nodes.some((n) => done.has(n))))
      return 'done'
    const prevDone = i === 0 || STEPS[i - 1].nodes.every((n) => done.has(n))
    const started =
      prevDone ||
      step.nodes.some((n) => done.has(n)) ||
      (step.key === 'audit' && state.dimensionOrder.length > 0)
    if (state.status === 'error') return step.nodes.some((n) => done.has(n)) ? 'done' : 'pending'
    return started && state.status !== 'idle' ? 'active' : 'pending'
  }

  return (
    <ol className="relative ml-1 space-y-5 border-l border-[color:var(--line)] pl-4">
      {STEPS.map((step, i) => {
        const status = stepStatus(i)
        const label = t.timeline.steps[step.key]
        switch (step.key) {
          case 'discovery':
            return (
              <Entry key={step.key} label={label} status={status}>
                {state.stackProfile ? (
                  <>
                    <p className="mb-2 text-sm">{t.timeline.stackDetected}</p>
                    <StackChips profile={state.stackProfile} />
                  </>
                ) : (
                  <p className="text-sm text-[color:var(--dim)]">
                    {status === 'done' ? t.timeline.done : t.timeline.scanning}
                  </p>
                )}
              </Entry>
            )
          case 'clarify':
            return (
              <Entry key={step.key} label={label} status={status}>
                {state.pendingClarify ? (
                  <ClarifyForm questions={state.pendingClarify} onSubmit={onClarifySubmit} />
                ) : state.clarifyAnswered ? (
                  <p className="text-sm text-[color:var(--dim)]">
                    {t.timeline.answered}
                  </p>
                ) : (
                  <p className="text-sm text-[color:var(--dim)]">
                    {status === 'done' ? t.timeline.noQuestions : t.timeline.preparingQuestions}
                  </p>
                )}
              </Entry>
            )
          case 'audit':
            return (
              <Entry key={step.key} label={label} status={status}>
                {state.dimensionOrder.length > 0 ? (
                  <ul className="space-y-1.5">
                    {state.dimensionOrder.map((name) => (
                      <DimensionRow key={name} d={state.dimensions[name]} />
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-[color:var(--dim)]">{t.timeline.preparingInvestigators}</p>
                )}
              </Entry>
            )
          case 'verify':
            return (
              <Entry key={step.key} label={label} status={status}>
                {state.verification ? (
                  <ul className="space-y-1 text-sm">
                    <li>
                      <span className="font-mono text-emerald-400">✓</span>{' '}
                      {t.timeline.verified(state.verification.verified)}
                    </li>
                    <li className="text-[color:var(--dim)]">
                      {t.timeline.unverified(state.verification.unverified)}
                    </li>
                    <li className="text-sev-critical">
                      {t.timeline.rejected(state.verification.rejected)}
                    </li>
                  </ul>
                ) : (
                  <p className="text-sm text-[color:var(--dim)]">
                    {status === 'done' ? t.timeline.done : t.timeline.checkingEvidence}
                  </p>
                )}
              </Entry>
            )
          case 'adversarial':
            return (
              <Entry key={step.key} label={label} status={status}>
                {state.adversarial ? (
                  <ul className="space-y-1 text-sm">
                    <li>
                      <span className="font-mono text-emerald-400">✓</span>{' '}
                      {t.timeline.confirmed(state.adversarial.confirmed)}
                    </li>
                    <li className="text-[color:var(--dim)]">
                      {t.timeline.uncertainOf(state.adversarial.uncertain, state.adversarial.judged)}
                    </li>
                    <li className="text-sev-critical">
                      {t.timeline.refuted(state.adversarial.refuted)}
                    </li>
                  </ul>
                ) : (
                  <p className="text-sm text-[color:var(--dim)]">
                    {status === 'done' ? t.timeline.adversarialOff : t.timeline.awaitingJudge}
                  </p>
                )}
              </Entry>
            )
          default:
            return <Entry key={step.key} label={label} status={status} />
        }
      })}
      {state.error && (
        <li className="relative pl-6">
          <span aria-hidden className="absolute left-0 top-1.5 h-2 w-2 rounded-full bg-sev-critical" />
          <p className="eyebrow mb-1.5 !text-sev-critical">{t.timeline.failure}</p>
          <div className="card">
            <p className="whitespace-pre-wrap break-words text-sm text-sev-critical">
              {noticeText(t, state.error)}
            </p>
          </div>
        </li>
      )}
    </ol>
  )
}
