import { describe, expect, it } from 'vitest'

import type { InvestigatorEvent } from '../types'
import { auditReducer, initialState } from './auditReducer'

const inv = (partial: Partial<InvestigatorEvent> & Pick<InvestigatorEvent, 'dimension' | 'status'>) =>
  ({
    type: 'INVESTIGATOR' as const,
    event: { type: 'investigator', index: 1, total: 2, ...partial } as InvestigatorEvent,
  })

describe('auditReducer', () => {
  it('START coloca em running e limpa estado anterior', () => {
    const s = auditReducer({ ...initialState, error: 'x' }, { type: 'START' })
    expect(s.status).toBe('running')
    expect(s.error).toBeNull()
  })

  it('registra fases concluídas sem duplicar', () => {
    let s = auditReducer(initialState, { type: 'PHASE', event: { node: 'discovery', label: 'D', status: 'done' } })
    s = auditReducer(s, { type: 'PHASE', event: { node: 'discovery', label: 'D', status: 'done' } })
    expect(s.phasesDone).toEqual(['discovery'])
  })

  it('snapshot guarda o stack profile', () => {
    const s = auditReducer(initialState, { type: 'SNAPSHOT', stackProfile: { languages: { Python: 3 } } })
    expect(s.stackProfile?.languages?.Python).toBe(3)
  })

  it('rastreia investigadores em ordem, com status e contagem', () => {
    let s = auditReducer(initialState, inv({ dimension: 'security', status: 'start' }))
    s = auditReducer(s, inv({ dimension: 'security', status: 'done', findings_count: 2 }))
    s = auditReducer(s, inv({ dimension: 'quality', status: 'start', index: 2 }))
    expect(s.dimensionOrder).toEqual(['security', 'quality'])
    expect(s.dimensions.security).toMatchObject({ status: 'done', findings_count: 2 })
  })

  it('clarification pausa; submissão retoma e marca respondido', () => {
    let s = auditReducer(initialState, { type: 'CLARIFY', questions: [{ question: 'Q', rationale: 'R' }] })
    expect(s.status).toBe('awaiting_clarify')
    s = auditReducer(s, { type: 'CLARIFY_SUBMITTED' })
    expect(s.status).toBe('running')
    expect(s.pendingClarify).toBeNull()
    expect(s.clarifyAnswered).toBe(true)
  })

  it('completed finaliza; results anexa o payload de achados', () => {
    let s = auditReducer(initialState, {
      type: 'COMPLETED',
      event: { health_score: 82, counts: { high: 1 } },
    })
    expect(s.status).toBe('finished')
    s = auditReducer(s, {
      type: 'RESULTS',
      payload: {
        findings: [], dimension_summaries: [], health_score: 82,
        executive_summary: 'sum', stack_profile: {},
      },
    })
    expect(s.results?.executive_summary).toBe('sum')
  })

  it('registra erro', () => {
    const s = auditReducer(initialState, { type: 'ERROR', message: 'boom' })
    expect(s.status).toBe('error')
    expect(s.error).toBe('boom')
  })

  it('guarda stats ao vivo de verificação e contraprova', () => {
    let s = auditReducer(initialState, {
      type: 'VERIFICATION',
      event: { type: 'verification', verified: 3, unverified: 1, rejected: 2 },
    })
    expect(s.verification).toMatchObject({ verified: 3, rejected: 2 })
    s = auditReducer(s, {
      type: 'ADVERSARIAL',
      event: { type: 'adversarial', judged: 5, confirmed: 3, refuted: 1, uncertain: 1 },
    })
    expect(s.adversarial).toMatchObject({ confirmed: 3, refuted: 1, judged: 5 })
  })

  it('START limpa stats de verificação/contraprova de um run anterior', () => {
    const dirty = auditReducer(initialState, {
      type: 'VERIFICATION',
      event: { type: 'verification', verified: 1, unverified: 0, rejected: 0 },
    })
    const s = auditReducer(dirty, { type: 'START' })
    expect(s.verification).toBeNull()
    expect(s.adversarial).toBeNull()
  })
})
