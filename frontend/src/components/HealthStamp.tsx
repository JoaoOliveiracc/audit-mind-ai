import { useI18n } from '../i18n/I18nProvider'
import { scoreTier } from '../state/score'

const TIER_COLOR: Record<string, string> = {
  good: 'text-emerald-400 border-emerald-400',
  warn: 'text-sev-medium border-sev-medium',
  bad: 'text-sev-critical border-sev-critical',
}

/** Assinatura visual: carimbo do score de saúde (0–100). */
export default function HealthStamp({ score }: { score: number }) {
  const { t } = useI18n()
  const tier = scoreTier(score)
  const tierLabel = t.common.tier[tier]
  // "100" (3 dígitos) esbarra no anel no tamanho cheio — encolhe pra caber centralizado.
  const numberSize = score >= 100 ? 'text-[2rem]' : 'text-4xl'
  return (
    <div
      className={`stamp ${TIER_COLOR[tier]}`}
      role="img"
      aria-label={t.health.label(score, tierLabel)}
    >
      <span className={`font-mono font-bold leading-none tabular-nums ${numberSize}`}>{score}</span>
      <span className="eyebrow mt-1 !text-[9px] !tracking-[0.12em] !text-current">
        /100 · {tierLabel}
      </span>
    </div>
  )
}
