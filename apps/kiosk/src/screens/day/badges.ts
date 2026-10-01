import type { Day, DayDiet, Observance } from '../../api/types'
import { copy } from '../../copy'

/**
 * The little pills that say what kind of day it is, and the one rule about
 * them: a day is named once. "Veterans Day · No school" is one badge, not a
 * holiday badge next to a school badge saying the same thing twice.
 */

const WEEKDAY_NAMES = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
]

/** Saturday or Sunday: there is no school to be without. */
export function isWeekend(day: Pick<Day, 'weekday'>): boolean {
  return day.weekday === 'sat' || day.weekday === 'sun'
}

/**
 * What to say about school on a day off, or null when nothing is worth
 * saying. The one rule for every surface — the header, Tomorrow, NIGHT and
 * the list: "No school" is news on a Tuesday and never on a Saturday or a
 * Sunday. A weekend's own note (a Saturday event) still says itself.
 */
export function dayOffNote(day: Pick<Day, 'weekday' | 'is_school_day' | 'school_note'>): string | null {
  if (day.is_school_day) {
    return null
  }
  const note = day.school_note?.trim() || null
  if (isWeekend(day)) {
    return note && note.toLowerCase() !== copy.tomorrow.noSchool.toLowerCase() ? note : null
  }
  return note ?? copy.tomorrow.noSchool
}

export function observanceNames(observances: Observance[]): string[] {
  return observances.map((observance) => observance.name)
}

/** "Diwali", "Veterans Day · No school", or "" when the day is ordinary. */
export function badgeFor(day: Day): string {
  const parts = observanceNames(day.observances)
  const named = new Set(parts.map((part) => part.trim().toLowerCase()))

  if (!day.is_school_day) {
    const note = dayOffNote(day)
    // The district names its closures after the holiday — "No School and
    // District Office Closed - Veterans Day" — so the note and the observance
    // are often the same words. Say the day once, then say it is a day off.
    if (note) {
      parts.push(named.has(note.toLowerCase()) ? copy.tomorrow.noSchool : note)
    }
  } else if (day.school_note) {
    // A minimum day is still a school day, and still worth saying.
    parts.push(day.school_note)
  }
  return parts.join(' · ')
}

/**
 * Whether to tag the meals as vegetarian. A weekday rule needs no tag — the
 * family knows which days those are — but a festival is worth a word, because
 * that is the day someone would otherwise ask about.
 */
export function vegReason(diet: DayDiet): string | null {
  if (diet.non_veg_ok) {
    return null
  }
  const beyondTheWeekday = diet.reasons.filter((reason) => !WEEKDAY_NAMES.includes(reason))
  return beyondTheWeekday.length > 0 ? beyondTheWeekday[0] : null
}

/**
 * Which colour the pill takes. A festival outranks a holiday, because that is
 * the one this house is more likely to be marking.
 */
export function badgeTone(day: Day): 'festival' | 'holiday' | 'school' {
  if (day.observances.some((observance) => observance.kind === 'festival')) {
    return 'festival'
  }
  if (day.observances.length > 0) {
    return 'holiday'
  }
  return 'school'
}
