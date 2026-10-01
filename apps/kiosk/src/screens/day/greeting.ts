/**
 * The line under the date, when there is one.
 *
 * Two windows only, at the two ends of the day a child is actually in front
 * of this screen: getting ready, and being sent to bed. The rest of the day
 * it says nothing, because a greeting that is always there is furniture, and
 * the space it takes belongs to the pill that says what kind of day it is.
 *
 * The evening window closes at the night start from settings rather than at a
 * fixed hour: after that the night screen is up and has its own way of saying
 * the same thing.
 */
const MORNING_FROM = 6 * 60
const MORNING_TO = 9 * 60
const EVENING_FROM = 20 * 60

/** "22:00" as minutes past midnight, or null. */
function minutes(value: string | null | undefined): number | null {
  if (!value) {
    return null
  }
  const [hours, mins] = value.split(':').map(Number)
  if (!Number.isFinite(hours) || !Number.isFinite(mins)) {
    return null
  }
  return hours * 60 + mins
}

export type Greeting = 'morning' | 'night' | null

export function greetingAt(now: Date, nightStart: string | null | undefined): Greeting {
  const at = now.getHours() * 60 + now.getMinutes()
  if (at >= MORNING_FROM && at < MORNING_TO) {
    return 'morning'
  }
  const end = minutes(nightStart) ?? 22 * 60
  if (at >= EVENING_FROM && at < end) {
    return 'night'
  }
  return null
}
