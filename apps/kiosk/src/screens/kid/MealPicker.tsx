import { useCallback, useEffect, useRef, useState } from 'react'

import { pickMeal, pickOptions, weekPicks } from '../../api/points'
import type { DayPicks, KidDay, MealSlotName, PickOption, Protein, SlotView } from '../../api/types'
import Avatar from '../../components/Avatar'
import DishList from '../../components/DishList'
import PlaceField from '../../components/PlaceField'
import Icon from '../../components/icons/Icon'
import Illustration from '../../components/illustrations/Illustration'
import { copy } from '../../copy'
import { kidVars } from '../../kidVars'
import { cleanPlace, mealName } from '../../out'
import { defaultProtein, sameAsYesterday, surpriseMe } from './picks'

const SLOTS: MealSlotName[] = ['breakfast', 'lunch', 'dinner']

const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

/** How long a cell just filled keeps its tint. Matches pick-tint in kid.css. */
const TINT_MS = 300

function weekdayOf(date: string): string {
  const [year, month, day] = date.split('-').map(Number)
  return WEEKDAYS[new Date(year, month - 1, day).getDay()]
}

/** "Thu 24", the head of a column. */
function headOf(date: string): string {
  const [year, month, day] = date.split('-').map(Number)
  return `${weekdayOf(date).slice(0, 3)} ${new Date(year, month - 1, day).getDate()}`
}

type Open = { date: string; slot: MealSlotName }

/**
 * A child's week of meals: seven days from today, three meals each.
 *
 * Each cell is the plan in the muted ink, or their own pick in their colour,
 * with the other child's face when they picked too. A ring where the two of
 * them want different things — "Mom or Dad picks" — and a lock where it is
 * too late to change. A cell opens the list for that one meal, already
 * narrowed to what that day's diet allows; choosing writes the pick and comes
 * back to the week with the cell filled.
 *
 * Picks are free. Nothing here costs a point.
 */
export default function MealPicker({
  kid,
  other,
  onDone,
  onChanged,
}: {
  kid: KidDay
  other: KidDay | null
  onDone: () => void
  onChanged: () => void
}) {
  const [week, setWeek] = useState<DayPicks[] | null>(null)
  const [open, setOpen] = useState<Open | null>(null)
  const [options, setOptions] = useState<PickOption[]>([])
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [fresh, setFresh] = useState<string | null>(null)
  // Dinner out, asked for: where, before it goes to Mom or Dad.
  const [asking, setAsking] = useState<string | null>(null)
  const tint = useRef<number | null>(null)

  const load = useCallback(() => {
    weekPicks(7)
      .then(setWeek)
      .catch(() => setWeek([]))
  }, [])

  useEffect(() => {
    load()
    return () => {
      if (tint.current !== null) {
        window.clearTimeout(tint.current)
      }
    }
  }, [load])

  useEffect(() => {
    if (!open) {
      return
    }
    let cancelled = false
    pickOptions(kid.id, open.slot, open.date)
      .then((loaded) => !cancelled && setOptions(loaded))
      .catch(() => !cancelled && setOptions([]))
    return () => {
      cancelled = true
    }
  }, [kid.id, open])

  const choose = (option: PickOption, protein: Protein, place: string | null = null) => {
    if (!open) {
      return
    }
    const cell = `${open.date}-${open.slot}`
    setBusy(true)
    setAsking(null)
    pickMeal(kid.id, open.date, open.slot, option.id, protein, place)
      .then((slotNow) => {
        const names = slotNow.resolved?.picked_by ?? []
        setNote(
          option.treat
            ? copy.picker.treatAsked(option.name)
            : names.length > 1
              ? copy.picker.bothChose(option.name)
              : copy.picker.chose(option.name),
        )
        setOpen(null)
        setFresh(cell)
        if (tint.current !== null) {
          window.clearTimeout(tint.current)
        }
        tint.current = window.setTimeout(() => setFresh(null), TINT_MS)
        load()
        onChanged()
      })
      .catch((failure: Error) => setNote(failure.message || copy.picker.notThatOne))
      .finally(() => setBusy(false))
  }

  /** A tile picks the dish the way the day allows, without a second tap. */
  const chooseDefault = (option: PickOption) => {
    const protein = defaultProtein(option)
    if (protein) {
      choose(option, protein)
    }
  }

  if (open) {
    // Dinner out is a tile of its own, never one of the dishes: not in the
    // list, not a thing Surprise me can land on, and not in the count.
    const dishes = options.filter((option) => !option.out)
    const out = options.find((option) => option.out) ?? null
    const again = sameAsYesterday(dishes)
    return (
      <div className="shop">
        <div className="shop-bar">
          <h2 className="shop-title">
            {copy.picker.slotTitle(weekdayOf(open.date), open.slot)}
          </h2>
          <button type="button" className="kid-done" onClick={() => setOpen(null)}>
            {copy.picker.back}
          </button>
        </div>

        {/* The common case in one tap, above the thirty dishes below it. */}
        <div className="fast">
          {again ? (
            <button
              type="button"
              className="fast-tile"
              disabled={busy}
              onClick={() => chooseDefault(again)}
            >
              <Icon name="clock" size={28} className="fast-glyph" />
              <span className="fast-name">{copy.picker.again}</span>
              <span className="fast-what">{again.name}</span>
            </button>
          ) : null}
          <button
            type="button"
            className="fast-tile"
            disabled={busy || dishes.every((option) => !option.pickable)}
            onClick={() => {
              const lucky = surpriseMe(dishes, Math.random())
              if (lucky) {
                chooseDefault(lucky)
              }
            }}
          >
            <Icon name="star" size={28} className="fast-glyph" />
            <span className="fast-name">{copy.picker.surprise}</span>
          </button>
          {out ? (
            // A treat: it goes to Mom or Dad, like any other.
            <button
              type="button"
              className="fast-tile fast-tile-out"
              disabled={busy || !out.pickable}
              onClick={() => setAsking(asking === null ? '' : null)}
            >
              <Icon name="storefront" size={28} className="fast-glyph meal-out-glyph" />
              <span className="fast-name">{copy.out.dinner}</span>
              <span className="fast-what">{out.pickable ? copy.out.decide : out.why}</span>
            </button>
          ) : null}
        </div>

        {out && asking !== null ? (
          <div className="out-ask">
            <PlaceField value={asking} onChange={setAsking} />
            <button
              type="button"
              className="kid-action out-ask-go"
              disabled={busy}
              onClick={() => choose(out, 'veg', cleanPlace(asking))}
            >
              {copy.out.ask}
            </button>
          </div>
        ) : null}

        <div className="pick-head">
          <span className="pick-count">
            {copy.picker.howMany(
              dishes.filter((option) => !option.also).length,
              copy.meals[open.slot].toLowerCase(),
            )}
          </span>
        </div>

        <div className="pick-scroll">
          <DishList
            options={dishes}
            busy={busy}
            alsoName={copy.picker.alsoGood(open.slot)}
            onChoose={choose}
          />
        </div>
        {dishes.length === 0 ? (
          <p className="empty empty-drawn">
            <Illustration name="plate" size={40} />
            {copy.picker.nothing}
          </p>
        ) : null}
        {note ? <p className="shop-note">{note}</p> : null}
      </div>
    )
  }

  const pickedAny = (week ?? []).some((day) =>
    SLOTS.some((slot) => day[slot].picks.some((pick) => pick.kid_id === kid.id)),
  )

  return (
    <div className="shop">
      <div className="shop-bar">
        <h2 className="shop-title">{copy.picker.week}</h2>
        <button type="button" className="kid-done" onClick={onDone}>
          {copy.shop.back}
        </button>
      </div>
      {week !== null && !pickedAny ? <p className="shop-nudge">{copy.day.nothingPicked}</p> : null}

      <div className="week-strip">
        {/* Which meal each row is, down the left. */}
        <div className="week-labels" aria-hidden="true">
          <span className="week-head" />
          {SLOTS.map((slot) => (
            <span key={slot} className="week-label">
              {copy.meals[slot]}
            </span>
          ))}
        </div>
        {(week ?? []).map((day) => (
          <div key={day.date} className="week-day">
            <span className="week-head">{headOf(day.date)}</span>
            {SLOTS.map((slot) => (
              <WeekCell
                key={slot}
                view={day[slot]}
                kid={kid}
                other={other}
                fresh={fresh === `${day.date}-${slot}`}
                onOpen={() => {
                  if (day[slot].locked || day[slot].decided) {
                    setNote(copy.picker.locked)
                    return
                  }
                  setNote('')
                  setOpen({ date: day.date, slot })
                }}
              />
            ))}
          </div>
        ))}
      </div>
      {note ? <p className="shop-note">{note}</p> : null}
    </div>
  )
}

/** One meal of the week, as a button a child can tap. */
function WeekCell({
  view,
  kid,
  other,
  fresh,
  onOpen,
}: {
  view: SlotView
  kid: KidDay
  other: KidDay | null
  fresh: boolean
  onOpen: () => void
}) {
  const live = (id: string) =>
    view.picks.find(
      (pick) => pick.kid_id === id && (pick.status === 'chosen' || pick.status === 'proposed'),
    )
  const mine = live(kid.id)
  const theirs = other ? live(other.id) : undefined
  const locked = view.locked || view.decided
  // Out, a cell reads "Out · Taqueria Luna"; the place rides in the note.
  const what = mine
    ? mealName({ id: mine.dish_id, name: mine.name, note: mine.note })
    : view.resolved
      ? mealName(view.resolved)
      : view.plan
        ? mealName(view.plan)
        : '—'

  const classes = ['week-cell']
  if (mine) {
    classes.push('week-cell-mine')
  }
  if (view.contested) {
    classes.push('week-cell-contested')
  }
  if (locked) {
    classes.push('week-cell-locked')
  }
  if (fresh) {
    classes.push('week-cell-fresh')
  }

  return (
    <button
      type="button"
      className={classes.join(' ')}
      aria-label={copy.picker.cellLabel(
        weekdayOf(view.date),
        view.slot,
        view.contested ? copy.picker.parentsPick : what,
      )}
      onClick={onOpen}
    >
      <span className="week-what clamp-2">{what}</span>
      <span className="week-marks">
        {theirs && other ? (
          <span className="week-other" style={kidVars(other.id, other.color)}>
            <Avatar name={other.name} avatar={other.avatar} size={16} />
          </span>
        ) : null}
        {locked ? <Icon name="lock" size={16} className="week-lock" /> : null}
      </span>
      {view.contested ? <span className="week-caption clamp-2">{copy.picker.parentsPick}</span> : null}
    </button>
  )
}
