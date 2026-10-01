import { describe, expect, it } from 'vitest'

import type { DietDay } from '../../api/types'
import { addDays, columnHead, dietLine, mondayOf, spanSaid } from './week'

function day(date: string, nonVegOk: boolean, reasons: string[] = []): DietDay {
  return { date, non_veg_ok: nonVegOk, reasons }
}

describe('the week grid', () => {
  it('starts on the Monday', () => {
    expect(mondayOf('2026-09-23')).toBe('2026-09-21')
    expect(mondayOf('2026-09-21')).toBe('2026-09-21')
    expect(mondayOf('2026-09-27')).toBe('2026-09-21')
    expect(addDays('2026-09-28', 7)).toBe('2026-10-05')
    expect(columnHead('2026-09-24')).toBe('Thu 24')
  })

  it('says a span across a month end', () => {
    expect(spanSaid('2026-10-11', '2026-10-19')).toBe('Oct 11–19')
    expect(spanSaid('2026-09-29', '2026-10-03')).toBe('Sep 29–Oct 3')
  })
})

describe('the diet line', () => {
  it('names the veg days and the festival with its whole span', () => {
    const days = [
      day('2026-10-12', true),
      day('2026-10-13', false, ['Tuesday']),
      day('2026-10-14', false, ['Wednesday']),
      day('2026-10-15', true),
      day('2026-10-16', true),
      day('2026-10-17', false, ['Sharad Navratri · day 7 of 10']),
      day('2026-10-18', false, ['Sharad Navratri · day 8 of 10']),
      // Outside the week, but part of the festival.
      day('2026-10-11', false, ['Sharad Navratri · day 1 of 10']),
      day('2026-10-19', false, ['Sharad Navratri · day 9 of 10']),
    ]
    expect(dietLine(days, '2026-10-12')).toBe(
      'Veg days: Tue, Wed, Sat, Sun · Sharad Navratri Oct 11–19',
    )
  })

  it('says nothing about a week with no veg days', () => {
    expect(dietLine([day('2026-10-12', true)], '2026-10-12')).toBeNull()
  })
})
