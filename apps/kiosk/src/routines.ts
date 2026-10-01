/**
 * The three parts of a child's day, and how near a thing is.
 *
 * A list of eight chores is a list. The same eight under Morning, After
 * school and Evening is a routine, and a child can see where they are in it
 * without reading every row — which is the whole point of the containers.
 *
 * Times are minutes past local midnight, as agenda.ts counts them: the cards
 * already hold the day that way, and a Date here would be a second clock to
 * keep in step with the first.
 */

import { minutesFromClock } from './screens/day/agenda'

export type Routine = 'morning' | 'afternoon' | 'evening'

export const ROUTINES: readonly Routine[] = ['morning', 'afternoon', 'evening']

/** Morning until 11:00, after school until 17:00, evening after that. */
const AFTERNOON_FROM = 11 * 60
const EVENING_FROM = 17 * 60

export function routineAt(at: number): Routine {
  if (at < AFTERNOON_FROM) {
    return 'morning'
  }
  return at < EVENING_FROM ? 'afternoon' : 'evening'
}

/** Within the hour a child asks "how long", not "what time". */
const SOON_MINUTES = 60

export type Nearness =
  | { kind: 'done' }
  | { kind: 'now' }
  | { kind: 'soon'; minutes: number }
  | { kind: 'later' }

export function nearness(at: number, start: string | null, end: string | null): Nearness {
  const from = minutesFromClock(start)
  if (from === null) {
    return { kind: 'later' }
  }
  const to = minutesFromClock(end) ?? from

  if (at >= to && at > from) {
    return { kind: 'done' }
  }
  if (at >= from) {
    return { kind: 'now' }
  }
  const away = from - at
  return away <= SOON_MINUTES ? { kind: 'soon', minutes: away } : { kind: 'later' }
}

/**
 * "in 20 min", "now", "done" — or null when the thing is far enough away
 * that the clock time is the more useful answer.
 */
export function relativeTime(at: number, start: string | null, end: string | null): string | null {
  const near = nearness(at, start, end)
  switch (near.kind) {
    case 'done':
      return 'done'
    case 'now':
      return 'now'
    case 'soon':
      return near.minutes <= 1 ? 'in a minute' : `in ${near.minutes} min`
    case 'later':
      return null
  }
}
