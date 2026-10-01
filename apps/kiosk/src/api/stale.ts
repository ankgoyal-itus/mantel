/** How old the data on screen is, as the chip shows it. */

export type StaleLevel = 'fresh' | 'amber' | 'red'

export const AMBER_AFTER_MS = 15 * 60000
export const RED_AFTER_MS = 60 * 60000

/**
 * Amber means "trust this less": either the last poll failed, so we are
 * serving a cached copy, or the data has simply aged past fifteen minutes.
 * Red is an hour old regardless of whether anything reported an error.
 */
export function staleLevel(ageMs: number, failing: boolean): StaleLevel {
  if (ageMs >= RED_AFTER_MS) {
    return 'red'
  }
  if (failing || ageMs >= AMBER_AFTER_MS) {
    return 'amber'
  }
  return 'fresh'
}

/** "updated 12:05", or "no data yet" before the first successful poll. */
export function updatedLabel(lastUpdated: number | null): string {
  if (lastUpdated === null) {
    return 'no data yet'
  }
  const when = new Date(lastUpdated)
  const hours = when.getHours()
  const minutes = when.getMinutes()
  return `updated ${hours}:${minutes < 10 ? `0${minutes}` : minutes}`
}
