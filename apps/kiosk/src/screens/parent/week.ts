import type { DietDay } from '../../api/types'

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** The weekday rules the diet service names by day. Not festivals. */
const RULE_DAYS = new Set([
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
])

/** A date as the API spells it, in local time. */
export function iso(day: Date): string {
  const month = `${day.getMonth() + 1}`.padStart(2, '0')
  const date = `${day.getDate()}`.padStart(2, '0')
  return `${day.getFullYear()}-${month}-${date}`
}

export function fromIso(value: string): Date {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day)
}

export function addDays(value: string, days: number): string {
  const day = fromIso(value)
  day.setDate(day.getDate() + days)
  return iso(day)
}

/** The Monday on or before this day: the week starts on a school day. */
export function mondayOf(value: string): string {
  const day = fromIso(value)
  const back = (day.getDay() + 6) % 7
  return addDays(value, -back)
}

/** "Mon 22", the head of a column. */
export function columnHead(value: string): string {
  const day = fromIso(value)
  return `${WEEKDAYS[day.getDay()]} ${day.getDate()}`
}

/** "Sep 22 – 28" or "Sep 29 – Oct 5". */
export function spanSaid(first: string, last: string): string {
  const a = fromIso(first)
  const b = fromIso(last)
  if (a.getMonth() === b.getMonth()) {
    return a.getDate() === b.getDate()
      ? `${MONTHS[a.getMonth()]} ${a.getDate()}`
      : `${MONTHS[a.getMonth()]} ${a.getDate()}–${b.getDate()}`
  }
  return `${MONTHS[a.getMonth()]} ${a.getDate()}–${MONTHS[b.getMonth()]} ${b.getDate()}`
}

/** "Sharad Navratri · day 1 of 10" is Sharad Navratri; "Tuesday" is a rule. */
function festivalOf(reason: string): string | null {
  const name = reason.split(' · ')[0].trim()
  return name && !RULE_DAYS.has(name) ? name : null
}

/**
 * The week's diet, in one line: which days are vegetarian, and the festivals
 * that make any of them so, each with its whole span — which is read from
 * the days around the week too, because Navratri does not start on a Monday.
 *
 * "Veg days: Tue, Wed, Sat · Navratri Oct 11–19", or null in a week with
 * nothing to say.
 */
export function dietLine(days: DietDay[], weekStart: string): string | null {
  const weekEnd = addDays(weekStart, 6)
  const inWeek = days.filter((day) => day.date >= weekStart && day.date <= weekEnd)
  const veg = inWeek.filter((day) => !day.non_veg_ok)
  if (veg.length === 0) {
    return null
  }
  const parts = [`Veg days: ${veg.map((day) => WEEKDAYS[fromIso(day.date).getDay()]).join(', ')}`]

  const named = new Set(veg.flatMap((day) => day.reasons.map(festivalOf)).filter(Boolean))
  for (const name of named) {
    const covered = days
      .filter((day) => day.reasons.some((reason) => festivalOf(reason) === name))
      .map((day) => day.date)
      .sort()
    if (covered.length > 0) {
      parts.push(`${name} ${spanSaid(covered[0], covered[covered.length - 1])}`)
    }
  }
  return parts.join(' · ')
}
