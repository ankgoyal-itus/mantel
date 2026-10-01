import { describe, expect, it } from 'vitest'

import type { Day } from '../../api/types'
import { TODAY, TOMORROW } from '../day/fixtures'
import { type Filter, daysFrom, filterOf, visible } from './rows'

const AGENDA: Day[] = [TODAY, TOMORROW]

function on(...filters: Filter[]): Set<Filter> {
  return new Set(filters)
}

describe('flattening the agenda', () => {
  it('gives every kid row and family row a chip', () => {
    const [first] = daysFrom(AGENDA)
    const chips = new Set(first.rows.map((row) => row.filter))
    expect(chips.has('mira')).toBe(true)
    expect(chips.has('family')).toBe(true)
  })

  it('files a school event under School, whoever it belongs to', () => {
    const entry = {
      start: '09:00',
      end: '10:00',
      title: 'Assembly',
      where: null,
      note: null,
      source: 'school',
      source_kind: 'school',
      all_day: false,
      calendar_id: 'bayside',
    }
    expect(filterOf(entry, 'mira')).toBe('school')
  })

  it('keeps the place and the all-day flag', () => {
    const [first] = daysFrom(AGENDA)
    const piano = first.rows.find((row) => row.title === 'Piano')
    expect(piano?.where).toBe("Ms. Lee's")
    const allDay = first.rows.find((row) => row.title === 'Picture day')
    expect(allDay?.time).toBeNull()
  })
})

describe('the filter', () => {
  const days = daysFrom(AGENDA)

  it('shows everything when nothing is chosen', () => {
    const shown = visible(days, on())
    expect(shown.length).toBe(days.length)
  })

  it('hides the rows that are not chosen', () => {
    const shown = visible(days, on('mira'))
    for (const day of shown) {
      expect(day.rows.every((row) => row.filter === 'mira')).toBe(true)
    }
  })

  it('shows more than one at a time', () => {
    const shown = visible(days, on('mira', 'family'))
    const chips = new Set(shown.flatMap((day) => day.rows.map((row) => row.filter)))
    expect([...chips].sort()).toEqual(['family', 'mira'])
  })

  it('skips a day with nothing left in it', () => {
    // Sixty day headers with nothing under them is not a list.
    const quiet = visible(days, on('kabir'))
    expect(quiet.every((day) => day.rows.length > 0 || day.observances.length > 0)).toBe(true)
    expect(quiet.length).toBeLessThan(days.length)
  })

  it('filters the observances by their own chips', () => {
    const festivals = visible(days, on('festival'))
    expect(festivals.some((day) => day.observances.some((o) => o.kind === 'festival'))).toBe(true)

    const holidays = visible(days, on('holiday'))
    expect(holidays.every((day) => day.observances.every((o) => o.kind !== 'festival'))).toBe(true)
  })
})

describe('a day read in order', () => {
  const entry = (title: string, start: string | null, source = 'calendar') => ({
    start,
    end: null,
    title,
    where: null,
    note: null,
    source,
    source_kind: source === 'school' ? 'school' : 'kid',
    all_day: start === null,
    calendar_id: 'x',
  })
  const sunday: Day = {
    ...TODAY,
    weekday: 'sun',
    kids: [
      { ...TODAY.kids[0], agenda: [entry('Soccer', '10:30'), entry('Minimum day', null, 'school')] },
      { ...TODAY.kids[1], agenda: [entry('Minimum day', null, 'school')] },
    ],
    family_agenda: [entry('Temple [Kabir]', '09:10')],
  }
  const [day] = daysFrom([sunday])

  it('puts all-day rows first, then runs by start time', () => {
    expect(day.rows.map((row) => row.time)).toEqual([null, '09:10', '10:30'])
  })

  it('draws a school row both feeds carried once, as the family’s', () => {
    const minimum = day.rows.filter((row) => row.title === 'Minimum day')
    expect(minimum).toHaveLength(1)
    expect(minimum[0].owner).toBeNull()
  })

  it('turns a [Name] suffix into a tag', () => {
    const temple = day.rows.find((row) => row.time === '09:10')
    expect(temple?.title).toBe('Temple')
    expect(temple?.tag).toBe('Kabir')
    expect(temple?.owner).toBeNull()
  })

  it('keeps a kid’s own row theirs', () => {
    expect(day.rows.find((row) => row.title === 'Soccer')?.owner).toBe(TODAY.kids[0].id)
  })
})
