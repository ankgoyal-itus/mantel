import { describe, expect, it } from 'vitest'

import { AMBER_AFTER_MS, RED_AFTER_MS, staleLevel, updatedLabel } from './stale'

describe('stale level', () => {
  it('is fresh while polls succeed and the data is young', () => {
    expect(staleLevel(0, false)).toBe('fresh')
    expect(staleLevel(AMBER_AFTER_MS - 1, false)).toBe('fresh')
  })

  it('turns amber as soon as a poll fails', () => {
    expect(staleLevel(0, true)).toBe('amber')
  })

  it('turns amber on age alone', () => {
    expect(staleLevel(AMBER_AFTER_MS, false)).toBe('amber')
  })

  it('turns red after an hour, failing or not', () => {
    expect(staleLevel(RED_AFTER_MS, false)).toBe('red')
    expect(staleLevel(RED_AFTER_MS, true)).toBe('red')
  })
})

describe('updated label', () => {
  it('pads the minutes', () => {
    expect(updatedLabel(new Date(2026, 8, 29, 12, 5).getTime())).toBe('updated 12:05')
    expect(updatedLabel(new Date(2026, 8, 29, 9, 30).getTime())).toBe('updated 9:30')
  })

  it('says so before the first poll', () => {
    expect(updatedLabel(null)).toBe('no data yet')
  })
})
