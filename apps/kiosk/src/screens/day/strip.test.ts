import { describe, expect, it } from 'vitest'

import { MORE_PILL, pillsThatFit } from './strip'

describe('the family strip', () => {
  it('draws every pill when they fit', () => {
    expect(pillsThatFit([200, 180], 500, 8)).toBe(2)
    expect(pillsThatFit([], 500, 8)).toBe(0)
  })

  it('replaces the last pill that would fit with a count of the rest', () => {
    // 586 with the gaps, in 420: the first two fit (388), but the second
    // gives way to "+2" rather than the third being cut off after it.
    expect(200 + 8 + 180).toBeLessThanOrEqual(420)
    expect(pillsThatFit([200, 180, 190], 420, 8)).toBe(1)
    expect(200 + 8 + MORE_PILL).toBeLessThanOrEqual(420)
  })

  it('keeps as many whole pills as leave room for the count', () => {
    expect(pillsThatFit([150, 150, 150, 150, 150], 600, 8)).toBe(3)
  })

  it('can come down to the count alone', () => {
    expect(pillsThatFit([400, 400], 300, 8)).toBe(0)
  })
})
