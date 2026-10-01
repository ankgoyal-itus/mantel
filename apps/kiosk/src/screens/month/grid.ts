import type { MonthDay } from '../../api/types'

/**
 * Laying a month out as weeks of seven days, and deciding what each cell
 * draws. Kept apart from the component so the rules can be read and tested
 * without a DOM.
 */

export const DAYS_IN_WEEK = 7

export type Cell = {
  date: string
  day: number
  inMonth: boolean
  data: MonthDay | null
}

/** "2026-10" and a day number, as the API spells dates. */
export function isoDate(year: number, month: number, day: number): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${year}-${pad(month)}-${pad(day)}`
}

export function parseYm(ym: string): { year: number; month: number } {
  const [year, month] = ym.split('-').map(Number)
  return { year, month }
}

export function shiftMonth(ym: string, by: number): string {
  const { year, month } = parseYm(ym)
  const zeroBased = month - 1 + by
  const shiftedYear = year + Math.floor(zeroBased / 12)
  const shiftedMonth = ((zeroBased % 12) + 12) % 12
  return isoDate(shiftedYear, shiftedMonth + 1, 1).slice(0, 7)
}

export function monthName(ym: string): string {
  const { year, month } = parseYm(ym)
  const names = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ]
  return `${names[month - 1]} ${year}`
}

/**
 * How many week rows a month needs: five for most, six when it starts late in
 * a week and runs long, four for a February that starts on a Sunday.
 *
 * It used to be six always, so the grid kept its height between months. The
 * cost was a sixth row that was all next month's days in most months — a
 * row of dimmed numbers, and every real day an inch shorter for it. The grid
 * fills the same height either way; only the rows in it change.
 */
export function weeksIn(ym: string): number {
  const { year, month } = parseYm(ym)
  const lead = new Date(year, month - 1, 1).getDay()
  const length = new Date(year, month, 0).getDate()
  return Math.ceil((lead + length) / DAYS_IN_WEEK)
}

/** The month's weeks of seven, starting on the Sunday on or before the first. */
export function cellsFor(ym: string, days: readonly MonthDay[]): Cell[] {
  const { year, month } = parseYm(ym)
  const byDate = new Map(days.map((day) => [day.date, day]))
  const first = new Date(year, month - 1, 1)
  const start = new Date(year, month - 1, 1 - first.getDay())

  const cells: Cell[] = []
  for (let index = 0; index < weeksIn(ym) * DAYS_IN_WEEK; index += 1) {
    const when = new Date(start.getFullYear(), start.getMonth(), start.getDate() + index)
    const date = isoDate(when.getFullYear(), when.getMonth() + 1, when.getDate())
    cells.push({
      date,
      day: when.getDate(),
      inMonth: when.getMonth() === month - 1,
      data: byDate.get(date) ?? null,
    })
  }
  return cells
}

/** The masa and samvat line under the month name, from whatever the grid has. */
export function masaLine(days: readonly MonthDay[], vikram: number | null): string {
  const names: string[] = []
  for (const day of days) {
    if (!names.includes(day.masa)) {
      names.push(day.masa)
    }
  }
  const masa = names.join(' · ')
  return vikram === null ? masa : `${masa} · Vikram Samvat ${vikram}`
}

/** A weekday with no school, which is what the hatch marks. */
export function isHatched(day: MonthDay | null): boolean {
  if (day === null || day.school.is_school_day) {
    return false
  }
  const weekend = day.weekday === 'sat' || day.weekday === 'sun'
  return !weekend
}
