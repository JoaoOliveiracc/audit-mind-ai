// Faixas da pontuação de saúde — mesmos limiares do CLI (>=75 / >=50).
export type ScoreTier = 'good' | 'warn' | 'bad'

export function scoreTier(score: number): ScoreTier {
  if (score >= 75) return 'good'
  if (score >= 50) return 'warn'
  return 'bad'
}

export const SEVERITY_LABEL: Record<string, string> = {
  critical: 'Crítico',
  high: 'Alto',
  medium: 'Médio',
  low: 'Baixo',
  info: 'Info',
}

export const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low', 'info'] as const
