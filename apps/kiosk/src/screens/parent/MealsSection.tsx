import { useCallback, useEffect, useState } from 'react'

import { useLiveNonce } from '../../api/live'
import { decidePick, getDiet, getMeals, mealOptions, setMeal } from '../../api/parent'
import type { Kid, MealCell, MealDay, MealSlotName, PickOption } from '../../api/types'
import Avatar from '../../components/Avatar'
import DishList from '../../components/DishList'
import PlaceField from '../../components/PlaceField'
import Icon from '../../components/icons/Icon'
import { copy } from '../../copy'
import { kidVars } from '../../kidVars'
import { DINNER_OUT, LUNCH_OUT, cleanPlace, isOut, mealName } from '../../out'
import { Card, Pane, Sheet, Toast } from './ui'
import { addDays, columnHead, dietLine, iso } from './week'

const SLOTS: MealSlotName[] = ['breakfast', 'lunch', 'dinner']

/** Days either side of the week read for the diet line, so a festival that
    started last week is said with its real first day. */
const DIET_MARGIN = 10

type Open = { date: string; slot: MealSlotName; cell: MealCell }

/**
 * The week's meals as a grid: seven days across, three meals down.
 *
 * Each cell is what the house is eating, in the page's ink; the plan it
 * replaced underneath, muted, when a child picked something else; the faces
 * of whoever picked it; and a festival-coloured ring when the children chose
 * differently and a parent has to decide. A cell is a button, and the sheet
 * it opens is the kid picker's own list with nothing hidden — a parent may
 * choose anything, and the reasons a child could not stay on as warnings.
 */
export default function MealsSection({
  kids,
  onDecided,
  planOut = 0,
}: {
  kids: Kid[]
  /** A meal was settled, which may have given a reward back. */
  onDecided?: () => void
  /** Bumped by "Plan it" on the family's Dinner out reward: open the next
      free dinner with Dinner out already chosen. */
  planOut?: number
}) {
  // Seven days from today, not from Monday: by Thursday the first half of
  // a Monday week is meals already eaten. The arrow back shows them.
  const today = iso(new Date())
  const [start, setStart] = useState(today)
  const [days, setDays] = useState<MealDay[] | null>(null)
  const [diet, setDiet] = useState<string | null>(null)
  const [open, setOpen] = useState<Open | null>(null)
  const [options, setOptions] = useState<PickOption[]>([])
  const [busy, setBusy] = useState(false)
  // Out, chosen in the open sheet: where, or '' for nowhere said yet. Null
  // while the row is still shut.
  const [place, setPlace] = useState<string | null>(null)
  const [planning, setPlanning] = useState(0)
  const [note, setNote] = useState({ text: '', bad: false })

  const load = useCallback(() => {
    getMeals(start, 7)
      .then(setDays)
      .catch(() => {
        setDays([])
        setNote({ text: copy.parent.meals.failed, bad: true })
      })
    getDiet(addDays(start, -DIET_MARGIN), 7 + 2 * DIET_MARGIN)
      .then((found) => setDiet(dietLine(found, start)))
      .catch(() => setDiet(null))
  }, [start])

  const live = useLiveNonce()
  useEffect(load, [load, live])

  useEffect(() => {
    if (!open) {
      return
    }
    let cancelled = false
    mealOptions(open.date, open.slot)
      .then((found) => !cancelled && setOptions(found))
      .catch(() => !cancelled && setOptions([]))
    return () => {
      cancelled = true
    }
  }, [open])

  /** The pen: a dish as the plan, or the plan (null). A contested cell's
      choices go through decide instead, so the winner keeps their face. */
  /** A cell's sheet; an out cell opens with its place filled in. */
  const openCell = (next: Open) => {
    setOpen(next)
    setPlace(isOut(next.cell.id) ? next.cell.note : null)
  }

  // "Plan it": the next dinner nobody has planned yet, Dinner out chosen.
  if (planOut !== planning && days !== null) {
    // Adjusting state while rendering, once per press.
    setPlanning(planOut)
    const free = days.find((day) => day.date >= today && !day.dinner.name)
    if (free) {
      setOpen({ date: free.date, slot: 'dinner', cell: free.dinner })
      setPlace('')
    }
  }

  const choose = (
    dishId: string | null,
    said: string,
    winnerKidId?: string,
    where: string | null = null,
  ) => {
    if (!open) {
      return
    }
    setBusy(true)
    const call =
      winnerKidId !== undefined
        ? decidePick(open.date, open.slot, winnerKidId)
        : setMeal(open.date, open.slot, dishId, where)
    call
      .then(() => {
        setNote({ text: said, bad: false })
        setOpen(null)
        onDecided?.()
        load()
      })
      .catch((failure: Error) => setNote({ text: failure.message, bad: true }))
      .finally(() => setBusy(false))
  }

  /** Out, and where: from the Save button, or a recent place's chip. */
  const saveOut = (text: string) => {
    if (!open) {
      return
    }
    const where = cleanPlace(text)
    choose(
      open.slot === 'dinner' ? DINNER_OUT : LUNCH_OUT,
      copy.parent.approvals.mealYes(copy.out.label(where)),
      undefined,
      where,
    )
  }

  const face = (id: string) => {
    const kid = kids.find((one) => one.id === id)
    return kid ? (
      <span key={id} className="pp-chip-face" style={kidVars(kid.id, kid.color)}>
        <Avatar name={kid.name} avatar={kid.avatar} size={24} />
      </span>
    ) : null
  }

  return (
    <Pane
      title={copy.parent.sections.meals.title}
      description={copy.parent.sections.meals.description}
      action={
        <div className="pp-week-nav">
          <button
            type="button"
            className="pp-icon-button"
            aria-label={copy.parent.meals.previous}
            onClick={() => setStart(addDays(start, -7))}
          >
            <Icon name="chevron-left" size={22} />
          </button>
          <span className="pp-week-label">
            {start === today ? copy.parent.meals.fromToday : copy.parent.meals.weekOf(columnHead(start))}
          </span>
          <button
            type="button"
            className="pp-icon-button"
            aria-label={copy.parent.meals.next}
            onClick={() => setStart(addDays(start, 7))}
          >
            <Icon name="chevron-right" size={22} />
          </button>
        </div>
      }
    >
      <Card className="pp-week-card">
        <div className="pp-week">
          <div className="pp-week-slots" aria-hidden="true">
            <span className="pp-week-corner" />
            {SLOTS.map((slot) => (
              <span key={slot} className="pp-week-slot">
                {copy.meals[slot]}
              </span>
            ))}
          </div>
          {(days ?? []).map((day) => (
            <div
              key={day.date}
              className={day.date === today ? 'pp-week-day pp-week-today' : 'pp-week-day'}
            >
              <span className="pp-week-head">
                {day.date === today ? copy.parent.meals.today : columnHead(day.date)}
              </span>
              {SLOTS.map((slot) => {
                const cell = day[slot]
                const replaced = !!cell.plan_name && cell.picked_by.length > 0
                return (
                  <button
                    key={slot}
                    type="button"
                    className={cell.contested ? 'pp-cell pp-cell-contested' : 'pp-cell'}
                    aria-label={copy.parent.meals.cellLabel(
                      columnHead(day.date),
                      copy.meals[slot],
                      cell.name || copy.parent.meals.nothing,
                    )}
                    onClick={() => openCell({ date: day.date, slot, cell })}
                  >
                    <span className="pp-cell-slot">{copy.meals[slot]}</span>
                    <span
                      className={cell.name ? 'pp-cell-dish clamp-2' : 'pp-cell-dish pp-cell-empty'}
                    >
                      {isOut(cell.id) ? (
                        <Icon name="storefront" size={18} className="meal-out-glyph" />
                      ) : null}
                      {cell.name ? mealName(cell) : copy.parent.meals.empty}
                    </span>
                    {replaced && !cell.contested ? (
                      <span className="pp-cell-plan clamp-1">{cell.plan_name}</span>
                    ) : null}
                    {cell.picked_by.length > 0 ? (
                      <span className="pp-faces-inline">{cell.picked_by.map(face)}</span>
                    ) : null}
                  </button>
                )
              })}
            </div>
          ))}
        </div>
      </Card>

      {diet ? (
        <p className="pp-diet-line">
          <Icon name="leaf" size={20} />
          <span>{diet}</span>
        </p>
      ) : null}

      <Toast text={note.text} bad={note.bad} />

      {open ? (
        <Sheet
          title={copy.parent.meals.sheetTitle(columnHead(open.date), copy.meals[open.slot])}
          onClose={() => setOpen(null)}
        >
          {open.cell.choices.length > 1 ? (
            <div className="pp-sheet-decide">
              <p className="pp-row-label">{copy.parent.approvals.parentsDecide}</p>
              {open.cell.choices.map((choice) => (
                <button
                  key={choice.id}
                  type="button"
                  className="pp-button pp-button-accent pp-choice"
                  disabled={busy}
                  onClick={() =>
                    choose(choice.id, copy.parent.approvals.mealYes(choice.name), choice.kids[0])
                  }
                >
                  <span className="clamp-1">{choice.name}</span>
                  <span className="pp-faces-inline">{choice.kids.map(face)}</span>
                </button>
              ))}
            </div>
          ) : null}
          {open.cell.plan_name ? (
            <button
              type="button"
              className="pp-plan-row"
              disabled={busy}
              onClick={() => choose(null, copy.parent.approvals.mealPlan)}
            >
              <span className="pp-row-label">{copy.parent.meals.usePlan}</span>
              <span className="pp-row-note">{open.cell.plan_name}</span>
            </button>
          ) : null}
          {open.slot !== 'breakfast' ? (
            // Out first: the one row that is a place, not a dish.
            <div className="pp-out">
              <button
                type="button"
                className="pp-plan-row pp-out-row"
                disabled={busy}
                aria-expanded={place !== null}
                onClick={() => setPlace(place === null ? '' : null)}
              >
                <Icon name="storefront" size={22} className="meal-out-glyph" />
                <span className="pp-row-label">
                  {open.slot === 'dinner' ? copy.out.dinner : copy.out.lunch}
                </span>
              </button>
              {place !== null ? (
                <div className="pp-out-where">
                  <PlaceField value={place} onChange={setPlace} onPick={saveOut} />
                  <button
                    type="button"
                    className="pp-button pp-button-accent"
                    disabled={busy}
                    onClick={() => saveOut(place)}
                  >
                    {copy.out.save}
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}
          <DishList
            options={options.filter((option) => !option.out)}
            busy={busy}
            parent
            alsoName={copy.picker.alsoGood(open.slot)}
            onChoose={(option) => choose(option.id, copy.parent.approvals.mealYes(option.name))}
          />
        </Sheet>
      ) : null}
    </Pane>
  )
}
