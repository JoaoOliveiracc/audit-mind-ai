import { describe, expect, it } from 'vitest'

import { scoreTier } from './score'

describe('scoreTier', () => {
  it('good para >= 75', () => {
    expect(scoreTier(75)).toBe('good')
    expect(scoreTier(100)).toBe('good')
  })
  it('warn para 50..74', () => {
    expect(scoreTier(74)).toBe('warn')
    expect(scoreTier(50)).toBe('warn')
  })
  it('bad para < 50', () => {
    expect(scoreTier(49)).toBe('bad')
    expect(scoreTier(0)).toBe('bad')
  })
})
