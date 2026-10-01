import type { AgendaEntry } from '../../api/types'

/**
 * Where an item sits relative to now. Exactly one item per list is accented:
 * whatever is running, or else whatever is up next.
 */
export type ItemStatus = 'past' | 'now' | 'next' | 'later'

export type ClassifiedEntry = { entry: AgendaEntry; status: ItemStatus }

export function minutesFromClock(value: string | null): number | null {
  if (!value) {
    return null
  }
  const [hours, minutes] = value.split(':').map(Number)
  if (!Number.isFinite(hours) || !Number.isFinite(minutes)) {
    return null
  }
  return hours * 60 + minutes
}

export function minutesOfDay(when: Date): number {
  return when.getHours() * 60 + when.getMinutes()
}

/** All-day items first, then by start time. */
function ordered(entries: AgendaEntry[]): AgendaEntry[] {
  return [...entries].sort((a, b) => {
    if (a.all_day !== b.all_day) {
      return a.all_day ? -1 : 1
    }
    return (minutesFromClock(a.start) ?? 0) - (minutesFromClock(b.start) ?? 0)
  })
}

export function classifyAgenda(entries: AgendaEntry[], now: number): ClassifiedEntry[] {
  const sorted = ordered(entries)
  const statuses: ItemStatus[] = sorted.map((entry) => {
    if (entry.all_day) {
      return 'later'
    }
    const start = minutesFromClock(entry.start)
    if (start === null) {
      return 'later'
    }
    const end = minutesFromClock(entry.end) ?? start
    if (now >= end) {
      return 'past'
    }
    if (now >= start) {
      return 'now'
    }
    return 'later'
  })

  // Nothing running? The first thing still to come gets the accent instead.
  if (!statuses.includes('now')) {
    const upcoming = statuses.findIndex(
      (status, index) => status === 'later' && !sorted[index].all_day,
    )
    if (upcoming >= 0) {
      statuses[upcoming] = 'next'
    }
  }

  return sorted.map((entry, index) => ({ entry, status: statuses[index] }))
}

export function isAccented(status: ItemStatus): boolean {
  return status === 'now' || status === 'next'
}
