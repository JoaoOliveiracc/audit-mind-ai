import { scoreTier } from '../state/score'

const TIER_COLOR: Record<string, string> = {
  good: 'text-emerald-400 border-emerald-400',
  warn: 'text-sev-medium border-sev-medium',
  bad: 'text-sev-critical border-sev-critical',
}

const TIER_LABEL: Record<string, string> = {
  good: 'saudável',
  warn: 'atenção',
  bad: 'crítico',
}

/** Assinatura visual: carimbo do score de saúde (0–100). */
export default function HealthStamp({ score }: { score: number }) {
  const tier = scoreTier(score)
  return (
    <div
      className={`stamp ${TIER_COLOR[tier]}`}
      role="img"
      aria-label={`Pontuação de saúde: ${score} de 100 (${TIER_LABEL[tier]})`}
    >
      <span className="font-mono text-4xl font-bold leading-none">{score}</span>
      <span className="eyebrow mt-1 !text-[9px] !text-current">/100 · {TIER_LABEL[tier]}</span>
    </div>
  )
}
