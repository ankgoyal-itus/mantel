import { type Day, type KidDay, type MealSlot, type Weather, isContested } from '../../api/types'
import Avatar from '../../components/Avatar'
import Icon from '../../components/icons/Icon'
import { copy } from '../../copy'
import { dateShort, degrees, parseApiDate } from '../../format'
import { kidVars } from '../../kidVars'
import { isOut, mealName } from '../../out'
import { dayOffNote, vegReason } from './badges'

type SlotKey = 'breakfast' | 'lunch' | 'dinner'

/** Three meals. A snack is a detail the half-card has no row for. */
const SLOTS: SlotKey[] = ['breakfast', 'lunch', 'dinner']

const LABELS: Record<SlotKey, string> = {
  breakfast: copy.meals.breakfast,
  lunch: copy.meals.lunch,
  dinner: copy.meals.dinner,
}

/** The school's own words for a short day, as school-events.yaml matches them. */
const MINIMUM_DAY = /minimum day|early release|early dismissal/i

/** What the head says about school, when it is not an ordinary school day. */
export function schoolChip(day: Day): string | null {
  if (!day.is_school_day) {
    // Never "No school" on a Saturday or a Sunday.
    return dayOffNote(day) === null ? null : copy.tomorrow.noSchool
  }
  return day.school_note && MINIMUM_DAY.test(day.school_note) ? copy.tomorrow.minimumDay : null
}

/** Everything on the day's calendar: the family's rows and each child's. */
export function eventCount(day: Day): number {
  return day.kids.reduce((sum, kid) => sum + kid.agenda.length, day.family_agenda.length)
}

/**
 * One meal as a line: the slot, the dish, and whatever is left for the note.
 *
 * The dish is the row. It keeps its natural width and ellipsises only when
 * it alone would overrun; the note takes the room over and is not drawn at
 * all under 120px of it, because half a note is a note nobody can use. A
 * child who picked the meal is on the end, as their own face.
 */
function MealRow({
  label,
  slot,
  kids,
  veg = false,
}: {
  label: string
  slot: MealSlot
  kids: KidDay[]
  /** A vegetarian day: an out meal keeps the leaf, so the reminder goes
      with the booking. */
  veg?: boolean
}) {
  const out = isOut(slot.id)
  // Out, the place is the name ("Out · Taqueria Luna") and there is no note.
  const note = out
    ? null
    : (slot.note ?? (slot.kids_protein !== 'veg' ? copy.meals.kidsEat(slot.kids_protein) : null))
  // Two children chose different dishes: both faces, and who decides —
  // not one child's choice shown as if it had won.
  const contested = isContested(slot)
  const pickers = slot.picked_by
    .map((id) => kids.find((kid) => kid.id === id))
    .filter((kid): kid is KidDay => kid !== undefined)

  return (
    <li className="dp-meal">
      <span className="dp-meal-label">{label}</span>
      {out ? <Icon name="storefront" size={20} className="meal-out-glyph" /> : null}
      <span className="meal-name clamp-1">{mealName(slot)}</span>
      {out && veg ? <Icon name="leaf" size={18} className="meal-out-leaf" /> : null}
      <span className="hide-under-120">
        {note ? <span className="dp-meal-note clamp-1">{note}</span> : null}
      </span>
      {contested ? <span className="dp-decide">{copy.day.parentsDecide}</span> : null}
      {pickers.length > 0 ? (
        <span className={contested ? 'dp-picks dp-picks-contested' : 'dp-picks'}>
          {pickers.map((kid) => (
            <span
              key={kid.id}
              className="dp-pick"
              style={kidVars(kid.id, kid.color)}
              aria-label={copy.picker.pick([kid.name])}
            >
              <Avatar name={kid.name} avatar={kid.avatar} size={16} />
            </span>
          ))}
        </span>
      ) : null}
    </li>
  )
}

/**
 * One day as a card: a head line, then its three meals.
 *
 * Today and tomorrow sit side by side at the foot of the dashboard. The
 * agenda lists these used to carry are gone: today's family rows are the
 * strip at the top of the screen, each child's are on their card, and
 * tomorrow's are one tap away behind the count in its head — which is the
 * question a wall is asked about tomorrow ("is there anything?") answered
 * without spending the meals' rows on it.
 */
export default function DayPlan({
  day,
  label,
  weather = null,
  showDate = false,
  onOpenList,
}: {
  day: Day
  label: string
  /** Tomorrow's high and low; today's are already in the header. */
  weather?: Weather | null
  /** Tomorrow says which day it is, and what it is like. */
  showDate?: boolean
  /** The events chip: the list, open at this day. */
  onOpenList?: (date: string) => void
}) {
  const forecast = showDate && weather ? weather.tomorrow : null
  const school = showDate ? schoolChip(day) : null
  const events = showDate ? eventCount(day) : 0
  const veg = showDate ? null : vegReason(day.diet)

  return (
    <section className="dp-card">
      <h3 className="dp-head">
        <span className="dp-label">{label}</span>
        {/* The date and the veg note are the first things to go. Each takes
            what the rest of the line leaves and is not drawn at all when
            that is too little to be read. */}
        {showDate ? (
          <span className="hide-under-120">
            <span className="dp-date clamp-1">{`· ${dateShort(parseApiDate(day.date))}`}</span>
          </span>
        ) : (
          <span className="hide-under-140">
            {veg ? (
              <span className="dp-veg clamp-1">{`${copy.meals.vegDay} · ${veg}`}</span>
            ) : null}
          </span>
        )}
        {forecast ? (
          <span className="dp-temps">{`${degrees(forecast.high)} / ${degrees(forecast.low)}`}</span>
        ) : null}
        {/* A label, so an outline: filled colour is for status and action. */}
        {school ? <span className="dp-chip dp-chip-school clamp-1">{school}</span> : null}
        {/* A way to the list, so it reads as a link: the calendar glyph and
            the count in the muted ink, not a filled pill. */}
        {events > 0 ? (
          <button type="button" className="dp-events" onClick={() => onOpenList?.(day.date)}>
            <Icon name="calendar" size={18} className="dp-events-glyph" />
            {copy.tomorrow.events(events)}
          </button>
        ) : null}
      </h3>

      {/* Always the three meals, so the card is the same shape every day:
          an empty one says "—" rather than the row not being there, which
          read as a meal that had been forgotten. */}
      <ul className="dp-meals">
        {SLOTS.map((key) => {
          const slot = day.meals[key]
          return slot ? (
            <MealRow
              key={key}
              label={LABELS[key]}
              slot={slot}
              kids={day.kids}
              veg={!day.diet.non_veg_ok}
            />
          ) : (
            <li key={key} className="dp-meal">
              <span className="dp-meal-label">{LABELS[key]}</span>
              <span className="meal-name dp-meal-empty">{copy.meals.empty}</span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
