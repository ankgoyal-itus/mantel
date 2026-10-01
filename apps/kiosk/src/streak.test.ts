import { describe, expect, it } from 'vitest'

import { flameFor, flameSize } from './streak'

describe('the flame', () => {
  it('starts at three days and grows twice', () => {
    expect(flameFor(0)).toBe('none')
    expect(flameFor(2)).toBe('none')
    expect(flameFor(3)).toBe('small')
    expect(flameFor(6)).toBe('small')
    expect(flameFor(7)).toBe('medium')
    expect(flameFor(13)).toBe('medium')
    expect(flameFor(14)).toBe('large')
    expect(flameFor(400)).toBe('large')
  })

  it('never goes backwards as the run gets longer', () => {
    const order = ['none', 'small', 'medium', 'large']
    let last = 0
    for (let days = 0; days <= 30; days += 1) {
      const at = order.indexOf(flameFor(days))
      expect(at).toBeGreaterThanOrEqual(last)
      last = at
    }
  })

  it('draws nothing at all without a run', () => {
    expect(flameSize('none', false)).toBe(0)
    expect(flameSize('none', true)).toBe(0)
  })

  it('is bigger at each step, and bigger again in kid mode', () => {
    for (const big of [false, true]) {
      const small = flameSize('small', big)
      const medium = flameSize('medium', big)
      const large = flameSize('large', big)
      expect(small).toBeLessThan(medium)
      expect(medium).toBeLessThan(large)
    }
    expect(flameSize('small', false)).toBeLessThan(flameSize('small', true))
    expect(flameSize('large', false)).toBeLessThan(flameSize('large', true))
  })
})
