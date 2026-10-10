import type { BankAccount, BankRow, KidBank } from '../../api/types'
import { copy } from '../../copy'

/** $15, or $15.50 when there are cents to say. */
export function dollars(cents: number): string {
  const whole = Math.floor(Math.abs(cents) / 100)
  const part = Math.abs(cents) % 100
  return part === 0 ? `$${whole}` : `$${whole}.${String(part).padStart(2, '0')}`
}

/** 2 h 30 min, 1 h, 45 min. */
export function duration(minutes: number): string {
  const hours = Math.floor(Math.abs(minutes) / 60)
  const rest = Math.abs(minutes) % 60
  if (hours && rest) {
    return `${hours} h ${rest} min`
  }
  return hours ? `${hours} h` : `${rest} min`
}

export function amountOf(account: BankAccount, amount: number): string {
  return account === 'cash' ? dollars(amount) : duration(amount)
}

/** Cash-outs go in fives: the whole balance rounded down to the nearest $5. */
export const CASH_STEP_CENTS = 500

/** What the Cash out button offers, and whether it can be tapped. Under the
    minimum it offers the minimum, disabled, with how much more to save. */
export function cashOutOffer(bank: KidBank): { cents: number; ok: boolean; short: number } {
  const min = bank.cash_out_min_cents
  const rounded = Math.floor(bank.cash.available_cents / CASH_STEP_CENTS) * CASH_STEP_CENTS
  if (rounded >= min) {
    return { cents: rounded, ok: true, short: 0 }
  }
  return { cents: min, ok: false, short: Math.max(0, min - bank.cash.available_cents) }
}

/** Whether one Roblox size can be asked for now. */
export function robloxOk(bank: KidBank, minutes: number): boolean {
  return (
    minutes <= bank.roblox.available_minutes && bank.roblox.uses_this_week < bank.roblox.per_week
  )
}

const WEEKDAY: Intl.DateTimeFormatOptions = { weekday: 'short' }

/** One row of the sheet's list: "+$5 · Ice cream day · Tue". */
export function rowLine(row: BankRow): string {
  const sign = row.delta > 0 ? '+' : '−'
  const what =
    row.note ??
    (row.reason_kind === 'cashout' ? copy.bank.cashedOut : row.reason_kind === 'use' ? copy.bank.used : '')
  const at = new Date(row.created_at)
  const when = Number.isNaN(at.getTime()) ? '' : at.toLocaleDateString('en-US', WEEKDAY)
  return [`${sign}${amountOf(row.account, Math.abs(row.delta))}`, what, when]
    .filter(Boolean)
    .join(' · ')
}

/** The DAY card's caption under the balance: "$15 saved · 2 h Roblox", each
    half only when there is something in it. */
export function caption(cashCents: number, robloxMinutes: number): string {
  const parts: string[] = []
  if (cashCents > 0) {
    parts.push(copy.bank.saved(dollars(cashCents)))
  }
  if (robloxMinutes > 0) {
    parts.push(copy.bank.robloxTime(duration(robloxMinutes)))
  }
  return parts.join(' · ')
}

/** The toast after a parent says yes: "+$5 in your piggy bank". */
export function depositSaid(row: BankRow): string {
  return row.account === 'cash'
    ? copy.bank.inPiggy(dollars(row.delta))
    : copy.bank.inRoblox(duration(row.delta))
}
