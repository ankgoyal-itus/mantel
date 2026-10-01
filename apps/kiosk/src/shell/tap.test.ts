import { describe, expect, it } from 'vitest'

import { CORNER_PX, planTap, wakes } from './tap'

const MIDDLE = { x: 512, y: 384 }
const CORNER = { x: 10, y: 10 }

describe('a tap on the stage', () => {
  it('is swallowed by the photo frame', () => {
    // The tap that wakes the frame belongs to the frame: passing it through
    // would land it on whatever the day screen has at that spot.
    expect(planTap('FRAME', MIDDLE, [], 1000).consume).toBe(true)
  })

  it('is swallowed by the night screen, unless it is on a night control', () => {
    expect(planTap('NIGHT', MIDDLE, [], 1000).consume).toBe(true)
    expect(planTap('NIGHT', MIDDLE, [], 1000, { live: true }).consume).toBe(false)
    expect(wakes('NIGHT')).toBe(true)
    expect(wakes('NIGHT', true)).toBe(false)
  })

  it('passes through on every other screen', () => {
    expect(planTap('DAY', MIDDLE, [], 1000).consume).toBe(false)
    expect(planTap('PARENT', MIDDLE, [], 1000).consume).toBe(false)
  })

  it('is swallowed for 600ms after a wake', () => {
    expect(planTap('DAY', MIDDLE, [], 1000, { deafUntil: 1600 }).consume).toBe(true)
    expect(planTap('DAY', MIDDLE, [], 1600, { deafUntil: 1600 }).consume).toBe(false)
  })

  it('still wakes the frame while it is being swallowed', () => {
    // consume stops the event; the mode machine is dispatched to regardless,
    // which is what turns FRAME back into DAY or NIGHT.
    const plan = planTap('FRAME', MIDDLE, [], 1000)
    expect(plan.diag).toBe(false)
  })
})

describe('the diagnostics corner', () => {
  it('opens on the third tap inside the window', () => {
    expect(planTap('DAY', CORNER, [], 1000)).toMatchObject({ taps: [1000], diag: false })
    expect(planTap('DAY', CORNER, [1000], 1200)).toMatchObject({ taps: [1000, 1200], diag: false })

    const third = planTap('DAY', CORNER, [1000, 1200], 1400)
    expect(third.diag).toBe(true)
    expect(third.consume).toBe(true)
    expect(third.taps).toEqual([])
  })

  it('forgets taps that were too long ago', () => {
    const stale = planTap('DAY', CORNER, [1000, 1200], 5000)
    expect(stale.diag).toBe(false)
    expect(stale.taps).toEqual([5000])
  })

  it('is only the top-left corner', () => {
    expect(planTap('DAY', { x: CORNER_PX + 1, y: 10 }, [1000, 1200], 1400).diag).toBe(false)
    expect(planTap('DAY', { x: 10, y: CORNER_PX + 1 }, [1000, 1200], 1400).diag).toBe(false)
  })

  it('resets the count when a tap lands elsewhere', () => {
    expect(planTap('DAY', MIDDLE, [1000, 1200], 1400).taps).toEqual([])
  })

  it('opens from the frame too, without waking it first', () => {
    const third = planTap('FRAME', CORNER, [1000, 1200], 1400)
    expect(third.diag).toBe(true)
    expect(third.consume).toBe(true)
  })
})
