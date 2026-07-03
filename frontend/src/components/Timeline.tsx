import type { ReactNode } from 'react'

import type { AuditUIState, DimensionProgress } from '../state/auditReducer'
import type { StackProfile } from '../types'
import ClarifyForm from './ClarifyForm'

interface Props {
  state: AuditUIState
  onClarifySubmit: (answers: Record<string, string>) => void
}

/** Etapas fixas do pipeline — ordem espelha o grafo (por isso a numeração). */
const STEPS = [
  { key: 'discovery', label: '01 · Descoberta', nodes: ['discovery'] },
  { key: 'clarify', label: '02 · Esclarecimentos', nodes: ['plan_questions', 'clarify'] },
  { key: 'planning', label: '03 · Plano', nodes: ['planning'] },
  { key: 'audit', label: '04 · Investigação', nodes: ['audit'] },
  { key: 'verify', label: '05 · Verificação de evidência', nodes: ['verify'] },
  { key: 'adversarial', label: '06 · Contraprova adversarial', nodes: ['adversarial'] },
  { key: 'synthesis', label: '07 · Consolidação', nodes: ['synthesis'] },
  { key: 'report', label: '08 · Relatório', nodes: ['report'] },
] as const

type StepStatus = 'pending' | 'active' | 'done'

function StackChips({ profile }: { profile: StackProfile }) {
  const chips = [
    ...Object.entries(profile.languages ?? {}).map(([lang, n]) => `${lang} (${n})`),
    ...(profile.frameworks ?? []),
    ...(profile.package_managers ?? []),
    `${profile.total_files ?? 0} arquivos · ~${profile.total_loc ?? 0} LOC`,
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
  const done = d.status === 'done' || d.status === 'empty'
  const icon = done ? '✓' : d.status === 'error' ? '✗' : '◌'
  const tone = done
    ? 'text-emerald-400'
    : d.status === 'error'
      ? 'text-sev-critical'
      : 'text-[color:var(--stamp)] animate-pulse'
  return (
    <li className="flex items-baseline gap-2 text-sm">
      <span className={`font-mono ${tone}`}>{icon}</span>
      <span className="font-mono">{d.dimension}</span>
      <span className="eyebrow">
        {d.index}/{d.total}
      </span>
      {d.status === 'done' && (
        <span className="eyebrow">
          {d.findings_count ?? 0} achado{(d.findings_count ?? 0) === 1 ? '' : 's'}
        </span>
      )}
      {d.status === 'empty' && <span className="eyebrow">sem resultado estruturado</span>}
      {d.status === 'error' && <span className="eyebrow !text-sev-critical">{d.message}</span>}
      {d.status === 'start' && <span className="eyebrow">investigando…</span>}
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
    <li className={`relative pl-6 ${status === 'pending' ? 'opacity-40' : ''}`}>
      <span aria-hidden className={`absolute left-0 top-1.5 h-2 w-2 rounded-full border ${marker}`} />
      <p className="eyebrow mb-1.5">{label}</p>
      {status !== 'pending' && children ? <div className="card">{children}</div> : null}
    </li>
  )
}

/** Conversa da auditoria como livro-razão: uma entrada por etapa do grafo. */
export default function Timeline({ state, onClarifySubmit }: Props) {
  const done = new Set(state.phasesDone)

  const stepStatus = (i: number): StepStatus => {
    const step = STEPS[i]
    if (step.nodes.every((n) => done.has(n))) return 'done'
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
        switch (step.key) {
          case 'discovery':
            return (
              <Entry key={step.key} label={step.label} status={status}>
                {state.stackProfile ? (
                  <>
                    <p className="mb-2 text-sm">Stack detectada:</p>
                    <StackChips profile={state.stackProfile} />
                  </>
                ) : (
                  <p className="text-sm text-[color:var(--dim)]">
                    {status === 'done' ? 'Concluída.' : 'Varrendo o projeto…'}
                  </p>
                )}
              </Entry>
            )
          case 'clarify':
            return (
              <Entry key={step.key} label={step.label} status={status}>
                {state.pendingClarify ? (
                  <ClarifyForm questions={state.pendingClarify} onSubmit={onClarifySubmit} />
                ) : state.clarifyAnswered ? (
                  <p className="text-sm text-[color:var(--dim)]">
                    ✓ Respostas enviadas — retomando a auditoria.
                  </p>
                ) : (
                  <p className="text-sm text-[color:var(--dim)]">
                    {status === 'done' ? 'Sem perguntas — seguiu direto.' : 'Preparando perguntas…'}
                  </p>
                )}
              </Entry>
            )
          case 'audit':
            return (
              <Entry key={step.key} label={step.label} status={status}>
                {state.dimensionOrder.length > 0 ? (
                  <ul className="space-y-1.5">
                    {state.dimensionOrder.map((name) => (
                      <DimensionRow key={name} d={state.dimensions[name]} />
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-[color:var(--dim)]">Preparando investigadores…</p>
                )}
              </Entry>
            )
          case 'verify':
            return (
              <Entry key={step.key} label={step.label} status={status}>
                {state.verification ? (
                  <ul className="space-y-1 text-sm">
                    <li>
                      <span className="font-mono text-emerald-400">✓</span>{' '}
                      {state.verification.verified} com evidência confirmada
                    </li>
                    <li className="text-[color:var(--dim)]">
                      {state.verification.unverified} sem evidência (confiança rebaixada)
                    </li>
                    <li className="text-sev-critical">
                      {state.verification.rejected} descartados (alucinação)
                    </li>
                  </ul>
                ) : (
                  <p className="text-sm text-[color:var(--dim)]">
                    {status === 'done' ? 'Concluída.' : 'Conferindo evidências no disco…'}
                  </p>
                )}
              </Entry>
            )
          case 'adversarial':
            return (
              <Entry key={step.key} label={step.label} status={status}>
                {state.adversarial ? (
                  <ul className="space-y-1 text-sm">
                    <li>
                      <span className="font-mono text-emerald-400">✓</span>{' '}
                      {state.adversarial.confirmed} confirmados pelo juiz
                    </li>
                    <li className="text-[color:var(--dim)]">
                      {state.adversarial.uncertain} incertos · de {state.adversarial.judged} julgados
                    </li>
                    <li className="text-sev-critical">
                      {state.adversarial.refuted} refutados (falso positivo)
                    </li>
                  </ul>
                ) : (
                  <p className="text-sm text-[color:var(--dim)]">
                    {status === 'done'
                      ? 'Sem contraprova adversarial (desativada — AUDITOR_ADVERSARIAL_VERIFY).'
                      : 'Aguardando julgamento cético…'}
                  </p>
                )}
              </Entry>
            )
          default:
            return <Entry key={step.key} label={step.label} status={status} />
        }
      })}
      {state.error && (
        <li className="relative pl-6">
          <span aria-hidden className="absolute left-0 top-1.5 h-2 w-2 rounded-full bg-sev-critical" />
          <p className="eyebrow mb-1.5 !text-sev-critical">Falha</p>
          <div className="card">
            <p className="text-sm text-sev-critical">{state.error}</p>
          </div>
        </li>
      )}
    </ol>
  )
}
