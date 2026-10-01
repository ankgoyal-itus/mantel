import { describe, expect, it } from 'vitest'

import type { DayPicks, PickRow, SlotView } from '../../api/types'
import { weekMarks } from './myWeek'

const START = new Date(2026, 8, 24) // Thursday 24 September 2026

function iso(offset: number): string {
  const day = new Date(START)
  day.setDate(day.getDate() + offset)
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(
    day.getDate(),
  ).padStart(2, '0')}`
}

function row(kid: string, dish: string, extra: Partial<PickRow> = {}): PickRow {
  return {
    id: 1, kid_id: kid, date: iso(0), slot: 'dinner', dish_id: dish, kids_protein: 'veg',
    status: 'chosen', decided_by: null, decided_at: null, moved_to: null, created_at: '',
    note: null, name: dish, treat: false, ...extra,
  }
}

function slot(date: string, picks: PickRow[], contested = false): SlotView {
  return { date, slot: 'dinner', plan: null, picks, resolved: null, contested, locked: false,
    decided: false }
}

function week(dinners: Record<number, { picks: PickRow[]; contested?: boolean }>): DayPicks[] {
  return Array.from({ length: 7 }, (_, offset) => {
    const date = iso(offset)
    const dinner = dinners[offset]
    return {
      date,
      breakfast: slot(date, []),
      lunch: slot(date, []),
      dinner: slot(date, dinner?.picks ?? [], dinner?.contested ?? false),
    }
  })
}

describe('the My week dots', () => {
  it('fills a day with a pick, rings a contested one, and leaves the rest', () => {
    const marks = weekMarks(
      week({
        0: { picks: [row('kabir', 'makhani'), row('mira', 'egg')], contested: true },
        2: { picks: [row('kabir', 'poha')] },
      }),
      'kabir',
    )
    expect(marks.dots).toEqual(['contested', 'empty', 'filled', 'empty', 'empty', 'empty', 'empty'])
    expect(marks.notice).toEqual({ kind: 'contested' })
  })

  it('says where a decided pick landed', () => {
    // Alternate: Mira's egg curry moved to Saturday, decided by a parent.
    const marks = weekMarks(
      week({ 2: { picks: [row('mira', 'egg', { decided_by: 'parent' })] } }),
      'mira',
    )
    expect(marks.notice).toEqual({ kind: 'yours', weekday: 'Saturday' })
  })

  it('has nothing to say on an ordinary week', () => {
    expect(weekMarks(week({ 1: { picks: [row('kabir', 'poha')] } }), 'kabir').notice).toBeNull()
    expect(weekMarks(week({}), 'kabir').dots.every((dot) => dot === 'empty')).toBe(true)
  })
})
