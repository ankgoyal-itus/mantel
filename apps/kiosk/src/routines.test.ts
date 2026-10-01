import { describe, expect, it } from 'vitest'

import { nearness, relativeTime, routineAt } from './routines'

/** Minutes past local midnight, as the cards count the day. */
function at(hour: number, minute = 0): number {
  return hour * 60 + minute
}

describe('which routine is open', () => {
  it('follows the hour', () => {
    expect(routineAt(at(6, 30))).toBe('morning')
    expect(routineAt(at(10, 59))).toBe('morning')
    expect(routineAt(at(11))).toBe('afternoon')
    expect(routineAt(at(16, 59))).toBe('afternoon')
    expect(routineAt(at(17))).toBe('evening')
    expect(routineAt(at(23, 30))).toBe('evening')
  })

  it('never leaves the day without one', () => {
    for (let hour = 0; hour < 24; hour += 1) {
      expect(['morning', 'afternoon', 'evening']).toContain(routineAt(at(hour)))
    }
  })
})

describe('how near a thing is', () => {
  it('counts down inside the hour', () => {
    expect(relativeTime(at(15, 40), '16:00', '16:45')).toBe('in 20 min')
    expect(relativeTime(at(15, 59), '16:00', '16:45')).toBe('in a minute')
  })

  it('says now while it is running', () => {
    expect(relativeTime(at(16, 0), '16:00', '16:45')).toBe('now')
    expect(relativeTime(at(16, 44), '16:00', '16:45')).toBe('now')
  })

  it('says done once it is over', () => {
    expect(relativeTime(at(16, 45), '16:00', '16:45')).toBe('done')
    expect(relativeTime(at(20, 0), '16:00', '16:45')).toBe('done')
  })

  it('leaves anything further out to the clock', () => {
    expect(relativeTime(at(9, 0), '16:00', '16:45')).toBeNull()
    expect(relativeTime(at(14, 59), '16:00', '16:45')).toBeNull()
    expect(relativeTime(at(15, 0), '16:00', '16:45')).toBe('in 60 min')
  })

  it('treats an item with no end as a moment', () => {
    expect(relativeTime(at(16, 0), '16:00', null)).toBe('now')
    expect(relativeTime(at(16, 1), '16:00', null)).toBe('done')
  })

  it('shrugs at a row with no time at all', () => {
    expect(relativeTime(at(12), null, null)).toBeNull()
    expect(nearness(at(12), null, null)).toEqual({ kind: 'later' })
  })
})
