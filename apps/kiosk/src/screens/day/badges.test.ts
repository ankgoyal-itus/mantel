import { describe, expect, it } from 'vitest'

import type { Day, DayDiet, Observance } from '../../api/types'
import { badgeFor, dayOffNote, vegReason } from './badges'
import { schoolChip } from './DayPlan'
import { TODAY, TOMORROW } from './fixtures'

function observance(name: string): Observance {
  return { name, kind: 'festival', calendar_id: 'india_holidays' }
}

function day(partial: Partial<Day>): Day {
  return { ...TODAY, ...partial }
}

describe('the day badge', () => {
  it('is empty on an ordinary school day', () => {
    expect(badgeFor(day({ is_school_day: true, school_note: null, observances: [] }))).toBe('')
  })

  it('names a festival', () => {
    expect(badgeFor(day({ observances: [observance('Diwali/Deepavali')] }))).toBe(
      'Diwali/Deepavali',
    )
  })

  it('names the day once when the closure repeats the holiday', () => {
    // The district calls it "No School ... - Veterans Day", so the derived
    // note and the holiday are the same words. Saying both reads as a stutter.
    const badge = badgeFor(
      day({
        observances: [observance('Veterans Day')],
        is_school_day: false,
        school_note: 'Veterans Day',
      }),
    )
    expect(badge).toBe('Veterans Day · No school')
  })

  it('keeps a closure that says something the holiday does not', () => {
    const badge = badgeFor(
      day({ observances: [], is_school_day: false, school_note: 'Thanksgiving Break' }),
    )
    expect(badge).toBe('Thanksgiving Break')
  })

  it('keeps a minimum day, which is still a school day', () => {
    const badge = badgeFor(
      day({ is_school_day: true, school_note: 'Minimum day (TK-5)', observances: [] }),
    )
    expect(badge).toBe('Minimum day (TK-5)')
  })

  it('falls back when a closure has no name', () => {
    expect(badgeFor(day({ is_school_day: false, school_note: null, observances: [] }))).toBe(
      'No school',
    )
  })
})

describe('the veg day tag', () => {
  const diet = (partial: Partial<DayDiet>): DayDiet => ({
    non_veg_ok: false,
    reasons: [],
    ...partial,
  })

  it('says nothing on a meat day', () => {
    expect(vegReason(diet({ non_veg_ok: true }))).toBeNull()
  })

  it('says nothing when only the weekday rule applies', () => {
    // Everyone in the house already knows Tuesday is vegetarian.
    expect(vegReason(diet({ reasons: ['Tuesday'] }))).toBeNull()
  })

  it('names the festival when there is one', () => {
    expect(vegReason(diet({ reasons: ['Dussehra'] }))).toBe('Dussehra')
  })

  it('names it even when the weekday would have allowed meat', () => {
    expect(vegReason(diet({ reasons: ['Sharad Navratri · day 5 of 10'] }))).toBe(
      'Sharad Navratri · day 5 of 10',
    )
  })
})

const SATURDAY = { ...TOMORROW, weekday: 'sat' as const, is_school_day: false, school_note: null }

describe('"No school"', () => {
  it('is never said for a Saturday or a Sunday', () => {
    expect(dayOffNote(SATURDAY)).toBeNull()
    expect(dayOffNote({ ...SATURDAY, weekday: 'sun' })).toBeNull()
    // Even when a feed writes the words itself.
    expect(dayOffNote({ ...SATURDAY, school_note: 'No school' })).toBeNull()
    // Not on Tomorrow's chip, nor in the header's badge.
    expect(schoolChip(SATURDAY)).toBeNull()
    expect(badgeFor({ ...SATURDAY, observances: [] })).toBe('')
  })

  it('is still news on a weekday, and a weekend keeps its own note', () => {
    const tuesday = { ...SATURDAY, weekday: 'tue' as const }
    expect(dayOffNote(tuesday)).toBe('No school')
    expect(schoolChip(tuesday)).toBe('No school')
    expect(dayOffNote({ ...SATURDAY, school_note: 'Saturday robotics meet' })).toBe(
      'Saturday robotics meet',
    )
  })
})
