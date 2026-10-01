import { describe, expect, it } from 'vitest'

import { classifyAgenda, isAccented, minutesFromClock } from './agenda'
import { TODAY } from './fixtures'

const MIRA = TODAY.kids[0].agenda
const at = (hour: number, minute = 0) => hour * 60 + minute

function statuses(now: number): string[] {
  return classifyAgenda(MIRA, now).map(({ entry, status }) => `${entry.title}:${status}`)
}

describe('classifying a day', () => {
  it('puts all-day items first whatever the time', () => {
    expect(classifyAgenda(MIRA, at(7, 30))[0].entry.title).toBe('Picture day')
    expect(classifyAgenda(MIRA, at(20, 30))[0].entry.title).toBe('Picture day')
  })

  it('accents the next item in the morning', () => {
    expect(statuses(at(7, 30))).toEqual([
      'Picture day:later',
      'Assembly:next',
      'Piano:later',
    ])
  })

  it('accents whatever is running', () => {
    expect(statuses(at(9, 30))).toEqual(['Picture day:later', 'Assembly:now', 'Piano:later'])
  })

  it('moves the accent on once an item is over', () => {
    expect(statuses(at(15, 30))).toEqual(['Picture day:later', 'Assembly:past', 'Piano:next'])
  })

  it('accents nothing once the day is done', () => {
    const done = classifyAgenda(MIRA, at(20, 30))
    expect(done.filter(({ status }) => isAccented(status))).toHaveLength(0)
    expect(done.filter(({ status }) => status === 'past')).toHaveLength(2)
  })

  it('never accents more than one item', () => {
    for (let minute = 0; minute < 24 * 60; minute += 15) {
      const accented = classifyAgenda(MIRA, minute).filter(({ status }) => isAccented(status))
      expect(accented.length).toBeLessThanOrEqual(1)
    }
  })

  it('reads clock strings, and shrugs at nonsense', () => {
    expect(minutesFromClock('16:45')).toBe(1005)
    expect(minutesFromClock(null)).toBeNull()
    expect(minutesFromClock('later')).toBeNull()
  })
})
