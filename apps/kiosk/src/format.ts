/** Date and time formatting, all local, all deterministic. */

const WEEKDAY_LONG = [
  'Sunday',
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
]
const WEEKDAY_SHORT = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTH_SHORT = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
]
const MONTH_LONG = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
]

/**
 * "2026-09-23" as a local date. `new Date(iso)` would read it as UTC and land
 * on the day before, west of Greenwich.
 */
export function parseApiDate(iso: string): Date {
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year, (month ?? 1) - 1, day ?? 1)
}

/** 12-hour, no seconds: "3:30". */
export function clock12(when: Date): string {
  const hours = when.getHours() % 12 === 0 ? 12 : when.getHours() % 12
  const minutes = when.getMinutes()
  return `${hours}:${minutes < 10 ? `0${minutes}` : minutes}`
}

function clockParts(value: string): { text: string; suffix: string } | null {
  const [rawHours, rawMinutes] = value.split(':').map(Number)
  if (!Number.isFinite(rawHours) || !Number.isFinite(rawMinutes)) {
    return null
  }
  const suffix = rawHours < 12 ? 'am' : 'pm'
  const hours = rawHours % 12 === 0 ? 12 : rawHours % 12
  return { text: `${hours}:${rawMinutes < 10 ? `0${rawMinutes}` : rawMinutes}`, suffix }
}

/** "am" or "pm" for the hour, kept apart from clock12 so it can be styled. */
export function meridiem(when: Date): string {
  return when.getHours() < 12 ? 'am' : 'pm'
}

/**
 * The time out of an API timestamp: "2026-09-30T06:58" -> "6:58". Sunrise and
 * sunset arrive as local wall-clock strings, so only the text after T matters.
 */
export function clockIso(iso: string | null | undefined): string {
  if (!iso) {
    return ''
  }
  const time = iso.split('T')[1]
  if (!time) {
    return ''
  }
  const parts = clockParts(time.slice(0, 5))
  return parts ? parts.text : ''
}

export function weekdayLong(when: Date): string {
  return WEEKDAY_LONG[when.getDay()]
}

/** "22 September" */
export function dateLong(when: Date): string {
  return `${when.getDate()} ${MONTH_LONG[when.getMonth()]}`
}

/** "June 2024" from an API date, for a photo caption. Empty when unknown. */
export function monthYear(iso: string | null | undefined): string {
  if (!iso) {
    return ''
  }
  const when = parseApiDate(iso)
  const month = MONTH_LONG[when.getMonth()]
  return month ? `${month} ${when.getFullYear()}` : ''
}

/** "Wed 23 Sep" */
export function dateShort(when: Date): string {
  return `${WEEKDAY_SHORT[when.getDay()]} ${when.getDate()} ${MONTH_SHORT[when.getMonth()]}`
}

/**
 * "4:00–4:45 pm", or "11:30 am–1:00 pm" when the range straddles noon. The
 * suffix is only repeated when it changes, which keeps the row short.
 */
export function timeRange(start: string | null, end: string | null): string {
  if (!start) {
    return ''
  }
  const from = clockParts(start)
  if (!from) {
    return ''
  }
  const to = end ? clockParts(end) : null
  if (!to) {
    return `${from.text} ${from.suffix}`
  }
  if (from.suffix === to.suffix) {
    return `${from.text}–${to.text} ${to.suffix}`
  }
  return `${from.text} ${from.suffix}–${to.text} ${to.suffix}`
}

/** "Sam", "Sam and Ria", "Sam, Ria and Jo". */
export function nameList(names: string[]): string {
  if (names.length <= 1) {
    return names[0] ?? ''
  }
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`
}

/** Whole degrees with the ring: 79 -> "79°". */
export function degrees(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : `${Math.round(value)}°`
}
