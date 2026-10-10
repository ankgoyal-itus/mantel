import { describe, expect, it } from 'vitest'

import type { BankRow, KidBank } from '../../api/types'
import { caption, cashOutOffer, depositSaid, dollars, duration, robloxOk, rowLine } from './bank'

function bank(cents: number, minutes = 0, uses = 0): KidBank {
  return {
    kid_id: 'mira',
    cash: { cents, available_cents: cents, pending: [] },
    roblox: {
      minutes,
      available_minutes: minutes,
      pending: [],
      uses_this_week: uses,
      per_week: 2,
      sizes: [30, 60, 120],
    },
    cash_out_min_cents: 2000,
    recent: [],
  }
}

function row(over: Partial<BankRow>): BankRow {
  return {
    id: 1,
    kid_id: 'mira',
    account: 'cash',
    delta: 500,
    reason_kind: 'deposit',
    reason_ref: null,
    note: null,
    actor: 'parent',
    // Tuesday noon, which is Tuesday in any timezone the tests run in.
    created_at: '2026-10-06T12:00:00-07:00',
    ...over,
  }
}

describe('the bank, said', () => {
  it('says dollars and time the way the card does', () => {
    expect(dollars(1500)).toBe('$15')
    expect(dollars(1550)).toBe('$15.50')
    expect(duration(150)).toBe('2 h 30 min')
    expect(duration(60)).toBe('1 h')
    expect(duration(30)).toBe('30 min')
  })

  it('offers the balance in fives, and the minimum until there is enough', () => {
    expect(cashOutOffer(bank(2350))).toEqual({ cents: 2000, ok: true, short: 0 })
    expect(cashOutOffer(bank(4000))).toEqual({ cents: 4000, ok: true, short: 0 })
    expect(cashOutOffer(bank(1500))).toEqual({ cents: 2000, ok: false, short: 500 })
  })

  it('holds a Roblox size back past the balance or the weekly cap', () => {
    expect(robloxOk(bank(0, 60), 60)).toBe(true)
    expect(robloxOk(bank(0, 60), 120)).toBe(false)
    expect(robloxOk(bank(0, 600, 2), 30)).toBe(false)
  })

  it('writes a row as amount, what and day', () => {
    expect(rowLine(row({ note: 'Ice cream day' }))).toBe('+$5 · Ice cream day · Tue')
    expect(rowLine(row({ delta: -2000, reason_kind: 'cashout', note: null }))).toBe(
      '−$20 · cashed out · Tue',
    )
    expect(rowLine(row({ account: 'roblox', delta: -60, note: 'Roblox' }))).toBe('−1 h · Roblox · Tue')
  })

  it('captions only what there is', () => {
    expect(caption(1500, 120)).toBe('$15 saved · 2 h Roblox')
    expect(caption(0, 90)).toBe('1 h 30 min Roblox')
    expect(caption(0, 0)).toBe('')
  })

  it('says a deposit as where it went', () => {
    expect(depositSaid(row({}))).toBe('+$5 in your piggy bank')
    expect(depositSaid(row({ account: 'roblox', delta: 60 }))).toBe('+1 h in your Roblox bank')
  })
})
