import type { DayPicks, PickRow, SlotView } from '../../api/types'

export type Dot = 'empty' | 'filled' | 'contested'

export type WeekMarks = {
  /** One per day from today: what this child has picked there. */
  dots: Dot[]
  /** News worth the headline: a meal waiting on a parent, or where a
      decided pick landed ("Yours is Saturday"). Null on an ordinary day. */
  notice: { kind: 'contested' } | { kind: 'yours'; weekday: string } | null
}

const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

function slotsOf(day: DayPicks): SlotView[] {
  return [day.breakfast, day.lunch, day.dinner]
}

function mine(slot: SlotView, kidId: string): PickRow | undefined {
  return slot.picks.find(
    (pick) => pick.kid_id === kidId && (pick.status === 'chosen' || pick.status === 'proposed'),
  )
}

function weekdayOf(date: string): string {
  const [year, month, day] = date.split('-').map(Number)
  return WEEKDAYS[new Date(year, month - 1, day).getDay()]
}

/**
 * A child's week of picks, as seven dots and at most one piece of news.
 *
 * A dot is filled where they picked anything that day and ringed where one
 * of their picks is contested. The news is, in order: a contested meal of
 * theirs still waiting on a parent, then the soonest pick of theirs a
 * parent (or the clock) decided — which is how a child whose dinner moved
 * to Saturday finds out.
 */
export function weekMarks(week: DayPicks[], kidId: string): WeekMarks {
  const dots: Dot[] = week.slice(0, 7).map((day) => {
    const slots = slotsOf(day)
    if (slots.some((slot) => slot.contested && mine(slot, kidId))) {
      return 'contested'
    }
    return slots.some((slot) => mine(slot, kidId)) ? 'filled' : 'empty'
  })

  const waiting = week.some((day) =>
    slotsOf(day).some((slot) => slot.contested && !slot.locked && mine(slot, kidId)),
  )
  if (waiting) {
    return { dots, notice: { kind: 'contested' } }
  }
  for (const day of week) {
    for (const slot of slotsOf(day)) {
      const pick = mine(slot, kidId)
      if (pick && pick.status === 'chosen' && pick.decided_by !== null) {
        return { dots, notice: { kind: 'yours', weekday: weekdayOf(day.date) } }
      }
    }
  }
  return { dots, notice: null }
}
