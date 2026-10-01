import { describe, expect, it } from 'vitest'

import type { PickOption } from '../../api/types'
import { defaultProtein, sameAsYesterday, surpriseMe } from './picks'

function option(id: string, extra: Partial<PickOption> = {}): PickOption {
  return {
    id,
    name: id,
    treat: false,
    cost: 0,
    proteins: ['veg'],
    pickable: true,
    why: null,
    cuisine: 'indian',
    yesterday: false,
    ...extra,
  }
}

/** What the API sends on a veg day with a treat already spent this week. */
const OFFERED: PickOption[] = [
  option('dal_chawal', { yesterday: true }),
  option('rajma', { proteins: ['veg', 'chicken'] }),
  option('egg_curry', { pickable: false, why: 'not on a veg day' }),
  option('pizza', { treat: true, pickable: false, why: 'two treats a week is the deal' }),
  option('dosa', { pickable: false, why: 'we had this in the last few days' }),
]

describe('same as yesterday', () => {
  it('offers it when it is still allowed', () => {
    expect(sameAsYesterday(OFFERED)?.id).toBe('dal_chawal')
  })

  it('offers nothing when yesterday is now blocked', () => {
    // Which is every dinner: the four-day repeat rule has already ruled it
    // out before the list reaches us.
    const dinner = OFFERED.map((one) =>
      one.yesterday ? { ...one, pickable: false, why: 'we had this in the last few days' } : one,
    )
    expect(sameAsYesterday(dinner)).toBeNull()
  })

  it('offers nothing when there was no yesterday', () => {
    expect(sameAsYesterday(OFFERED.map((one) => ({ ...one, yesterday: false })))).toBeNull()
  })
})

describe('surprise me', () => {
  it('never lands on something the day forbids', () => {
    // Every roll across the range, not one: the guard is that the pool is
    // the allowed list, so this should hold for all of them.
    for (let roll = 0; roll < 1; roll += 0.01) {
      const picked = surpriseMe(OFFERED, roll)
      expect(picked).not.toBeNull()
      expect(picked?.pickable).toBe(true)
      expect(['egg_curry', 'pizza', 'dosa']).not.toContain(picked?.id)
    }
  })

  it('reaches every allowed dish and no others', () => {
    const seen = new Set<string>()
    for (let roll = 0; roll < 1; roll += 0.001) {
      seen.add(surpriseMe(OFFERED, roll)?.id ?? '')
    }
    expect([...seen].sort()).toEqual(['dal_chawal', 'rajma'])
  })

  it('stays inside the list at the edges of the roll', () => {
    expect(surpriseMe(OFFERED, 0)?.id).toBe('dal_chawal')
    expect(surpriseMe(OFFERED, 0.999999)?.id).toBe('rajma')
    expect(surpriseMe(OFFERED, 1)?.id).toBe('rajma')
  })

  it('offers nothing when the day allows nothing', () => {
    expect(surpriseMe(OFFERED.map((one) => ({ ...one, pickable: false })), 0.5)).toBeNull()
    expect(surpriseMe([], 0.5)).toBeNull()
  })
})

describe('how to cook it', () => {
  it('takes veg where veg is on the table', () => {
    expect(defaultProtein(option('rajma', { proteins: ['veg', 'chicken'] }))).toBe('veg')
  })

  it('takes what the day left standing otherwise', () => {
    expect(defaultProtein(option('curry', { proteins: ['chicken'] }))).toBe('chicken')
    expect(defaultProtein(option('curry', { proteins: [] }))).toBeNull()
  })
})
