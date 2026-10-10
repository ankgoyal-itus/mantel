import { useEffect, useId, useRef, useState } from 'react'

import { getKidPins, getSettings, putKidPin, putSettings } from '../../api/parent'
import type { BankSettings, DateRange, KidEdit, ParentSettings, Weekday } from '../../api/types'
import Avatar from '../../components/Avatar'
import { AVATARS } from '../../components/avatars'
import { copy } from '../../copy'
import { Card, Pane, Row, Sheet, Stepper, TOAST_MS, TimeField, Toast, Toggle } from './ui'

const WEEK: Weekday[] = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

type Said = { text: string; bad: boolean }


/** settings.banks when the file has none yet: what the API defaults to. */
const DEFAULT_BANKS: BankSettings = { cash_out_min_cents: 2000, roblox_use_sizes: [30, 60, 120] }

/** The Roblox sizes a parent can offer, three at a time. */
const ROBLOX_SIZES = [15, 30, 45, 60, 90, 120]

/**
 * Everything the house may change from the iPad, grouped as cards.
 *
 * Nothing here has a Save button. A change saves when it is made — a switch
 * as it flips, a stepper once the taps stop, a field when it loses focus —
 * and "Saved" says so for a moment. A write the API refuses keeps the value
 * it had and says why, in the API's own words: a setting that looks changed
 * and is not is the worst thing a settings screen can do.
 */
export default function SettingsSection() {
  const [saved, setSaved] = useState<ParentSettings | null>(null)
  const [draft, setDraft] = useState<ParentSettings | null>(null)
  const [failed, setFailed] = useState(false)
  const [said, setSaid] = useState<Said>({ text: '', bad: false })
  const [pins, setPins] = useState<Record<string, boolean>>({})
  // One write at a time, in the order they were made, so two quick changes
  // cannot land out of order and leave the file on the first.
  const chain = useRef<Promise<unknown>>(Promise.resolve())
  const quiet = useRef<number | null>(null)

  useEffect(() => {
    let cancelled = false
    getSettings()
      .then((loaded) => {
        if (!cancelled) {
          setSaved(loaded)
          setDraft(loaded)
        }
      })
      .catch(() => !cancelled && setFailed(true))
    getKidPins()
      .then((state) => !cancelled && setPins(state.pins))
      .catch(() => undefined)
    return () => {
      cancelled = true
      if (quiet.current !== null) {
        window.clearTimeout(quiet.current)
      }
    }
  }, [])

  const say = (next: Said) => {
    setSaid(next)
    if (quiet.current !== null) {
      window.clearTimeout(quiet.current)
    }
    // "Saved" goes after a moment; a failure stays until something else is said.
    if (!next.bad) {
      quiet.current = window.setTimeout(() => setSaid({ text: '', bad: false }), TOAST_MS)
    }
  }

  if (!draft || !saved) {
    return (
      <Pane title={copy.parent.sections.settings.title}>
        <Card>
          <p className="pp-muted">{failed ? copy.parent.settings.failed : copy.parent.loading}</p>
        </Card>
      </Pane>
    )
  }

  const commit = (patch: Partial<ParentSettings>) => {
    const next = { ...draft, ...patch }
    setDraft(next)
    chain.current = chain.current.then(() =>
      putSettings(next)
        .then((stored) => {
          setSaved(stored)
          setDraft(stored)
          say({ text: copy.parent.settings.saved, bad: false })
        })
        .catch((failure: Error) => {
          setDraft(saved)
          say({ text: copy.parent.settings.notSaved(failure.message), bad: true })
        }),
    )
  }

  const diet = draft.diet
  const points = draft.points
  const banks = draft.banks ?? DEFAULT_BANKS

  const setKid = (id: string, patch: Partial<KidEdit>) =>
    commit({ kids: draft.kids.map((kid) => (kid.id === id ? { ...kid, ...patch } : kid)) })

  const setPin = (kidId: string, pin: string) =>
    putKidPin(kidId, pin)
      .then((state) => {
        setPins(state.pins)
        say({ text: pin ? copy.parent.settings.pinSet : copy.parent.settings.pinCleared, bad: false })
      })
      .catch((failure: Error) => say({ text: copy.parent.settings.notSaved(failure.message), bad: true }))

  return (
    <Pane
      title={copy.parent.sections.settings.title}
      description={copy.parent.sections.settings.description}
    >
      <Card title={copy.parent.settings.groups.night}>
        <TimeField
          label={copy.parent.settings.nightStart}
          value={draft.night_start}
          onCommit={(night_start) => commit({ night_start })}
        />
        <TimeField
          label={copy.parent.settings.nightEnd}
          value={draft.night_end}
          onCommit={(night_end) => commit({ night_end })}
        />
        <Row label={copy.parent.settings.idle} note={copy.parent.settings.idleNote}>
          <Stepper
            label={copy.parent.settings.idle}
            value={draft.idle_minutes}
            min={1}
            max={60}
            unit={copy.parent.settings.min}
            onCommit={(idle_minutes) => commit({ idle_minutes })}
          />
        </Row>
        <Row label={copy.parent.settings.nightIdle}>
          <Stepper
            label={copy.parent.settings.nightIdle}
            value={draft.night_idle_minutes}
            min={1}
            max={60}
            unit={copy.parent.settings.min}
            onCommit={(night_idle_minutes) => commit({ night_idle_minutes })}
          />
        </Row>
        <Row label={copy.parent.settings.frameAtNight}>
          <Toggle
            label={copy.parent.settings.frameAtNight}
            checked={draft.night_frame}
            onChange={(night_frame) => commit({ night_frame })}
          />
        </Row>
      </Card>

      <Card title={copy.parent.settings.groups.photos}>
        <Row label={copy.parent.settings.slide}>
          <Stepper
            label={copy.parent.settings.slide}
            value={draft.slide_seconds}
            min={5}
            max={120}
            step={5}
            unit={copy.parent.settings.sec}
            onCommit={(slide_seconds) => commit({ slide_seconds })}
          />
        </Row>
        <Row label={copy.parent.settings.frameChip}>
          <Toggle
            label={copy.parent.settings.frameChip}
            checked={draft.frame_chip ?? true}
            onChange={(frame_chip) => commit({ frame_chip })}
          />
        </Row>
        <Row label={copy.parent.settings.chipSize}>
          <div className="pp-chips" role="radiogroup" aria-label={copy.parent.settings.chipSize}>
            {(['regular', 'large'] as const).map((size) => (
              <button
                key={size}
                type="button"
                role="radio"
                aria-checked={(draft.frame_chip_size ?? 'regular') === size}
                className={
                  (draft.frame_chip_size ?? 'regular') === size ? 'pp-chip pp-chip-on' : 'pp-chip'
                }
                onClick={() => commit({ frame_chip_size: size })}
              >
                {copy.parent.settings.chipSizes[size]}
              </button>
            ))}
          </div>
        </Row>
      </Card>

      <Card title={copy.parent.settings.groups.calendars}>
        <Row label={copy.parent.settings.refresh} note={copy.parent.settings.refreshNote}>
          <Stepper
            label={copy.parent.settings.refresh}
            value={draft.refresh_minutes}
            min={1}
            max={120}
            unit={copy.parent.settings.min}
            onCommit={(refresh_minutes) => commit({ refresh_minutes })}
          />
        </Row>
      </Card>

      <Card title={copy.parent.settings.groups.diet}>
        <Row label={copy.parent.settings.nonVegDays} note={copy.parent.settings.nonVegNote} />
        <div className="pp-days" role="group" aria-label={copy.parent.settings.nonVegDays}>
          {WEEK.map((day) => {
            const on = diet.non_veg_days.includes(day)
            return (
              <button
                key={day}
                type="button"
                role="switch"
                aria-checked={on}
                aria-label={copy.parent.settings.nonVegOn(copy.parent.settings.weekdays[day])}
                className={on ? 'pp-day pp-day-on' : 'pp-day'}
                onClick={() =>
                  commit({
                    diet: {
                      ...diet,
                      non_veg_days: on
                        ? diet.non_veg_days.filter((one) => one !== day)
                        : WEEK.filter((one) => one === day || diet.non_veg_days.includes(one)),
                    },
                  })
                }
              >
                {copy.parent.settings.weekdays[day]}
              </button>
            )
          })}
        </div>
        {/* One row per festival. settings.yaml names most of them two or
            three ways so the feeds match; a stepper here sets every one of
            those aliases, and none of them is ever drawn. */}
        <p className="pp-description pp-festivals-lead">{copy.parent.settings.festivalsLead}</p>
        <div className="pp-compact">
          <h3 className="pp-compact-head">{copy.parent.settings.festivalsHead}</h3>
        {(diet.groups ?? []).map((group) => (
          <Row key={group.name} label={group.name} note={copy.parent.settings.festivalNote}>
            <Stepper
              label={group.name}
              value={group.span_days}
              min={1}
              max={31}
              unit={copy.parent.settings.days(group.span_days)}
              onCommit={(span_days) =>
                commit({
                  diet: {
                    ...diet,
                    festivals: diet.festivals.map((one) =>
                      group.matches.includes(one.match) ? { ...one, span_days } : one,
                    ),
                  },
                })
              }
            />
          </Row>
        ))}
        </div>
        <ExtraDates
          dates={diet.extra_dates}
          onChange={(extra_dates) => commit({ diet: { ...diet, extra_dates } })}
        />
      </Card>

      <Card title={copy.parent.settings.groups.kids}>
        {draft.kids.map((kid) => (
          <KidSettings
            key={kid.id}
            kid={kid}
            hasPin={pins[kid.id] === true}
            onChange={(patch) => setKid(kid.id, patch)}
            onPin={(pin) => setPin(kid.id, pin)}
          />
        ))}
      </Card>

      <Card title={copy.parent.settings.groups.points}>
        <Row label={copy.parent.settings.streakBonus} note={copy.parent.settings.streakBonusNote}>
          <Stepper
            label={copy.parent.settings.streakBonus}
            value={points.streak_bonus}
            min={0}
            max={200}
            step={5}
            unit={copy.parent.settings.pts}
            onCommit={(streak_bonus) => commit({ points: { ...points, streak_bonus } })}
          />
        </Row>
        <Row label={copy.parent.settings.streakDays}>
          <Stepper
            label={copy.parent.settings.streakDays}
            value={points.streak_days}
            min={1}
            max={31}
            unit={copy.parent.settings.days(points.streak_days)}
            onCommit={(streak_days) => commit({ points: { ...points, streak_days } })}
          />
        </Row>
        <Row label={copy.parent.settings.cashOutMin} note={copy.parent.settings.cashOutMinNote}>
          <Stepper
            label={copy.parent.settings.cashOutMin}
            value={banks.cash_out_min_cents / 100}
            min={5}
            max={200}
            step={5}
            format={(value) => `$${value}`}
            onCommit={(dollars) => commit({ banks: { ...banks, cash_out_min_cents: dollars * 100 } })}
          />
        </Row>
        {/* Six chips do not fit beside the label on a phone: they get their
            own line under it, and wrap. */}
        <Row label={copy.parent.settings.robloxSizes} note={copy.parent.settings.robloxSizesNote} />
        <div className="pp-chips" role="group" aria-label={copy.parent.settings.robloxSizes}>
          {ROBLOX_SIZES.map((minutes) => {
            const on = banks.roblox_use_sizes.includes(minutes)
            // One to three: the last one stays, and a fourth waits for
            // one of the three to be let go.
            const locked = on ? banks.roblox_use_sizes.length <= 1 : banks.roblox_use_sizes.length >= 3
            return (
              <button
                key={minutes}
                type="button"
                role="checkbox"
                aria-checked={on}
                className={on ? 'pp-chip pp-chip-on' : 'pp-chip'}
                disabled={locked}
                onClick={() =>
                  commit({
                    banks: {
                      ...banks,
                      roblox_use_sizes: on
                        ? banks.roblox_use_sizes.filter((size) => size !== minutes)
                        : [...banks.roblox_use_sizes, minutes].sort((a, b) => a - b),
                    },
                  })
                }
              >
                {copy.parent.settings.robloxSize(minutes)}
              </button>
            )
          })}
        </div>
        <Row label={copy.parent.settings.roblox} note={copy.parent.settings.robloxNote}>
          <Stepper
            label={copy.parent.settings.roblox}
            value={points.roblox_per_week}
            min={0}
            max={14}
            onCommit={(roblox_per_week) => commit({ points: { ...points, roblox_per_week } })}
          />
        </Row>
        <Row label={copy.parent.settings.deductions} note={copy.parent.settings.deductionsNote}>
          <Toggle
            label={copy.parent.settings.deductions}
            checked={points.deductions}
            onChange={(deductions) => commit({ points: { ...points, deductions } })}
          />
        </Row>
        <Row label={copy.parent.settings.parentIdle}>
          <Stepper
            label={copy.parent.settings.parentIdle}
            value={points.parent_idle_minutes}
            min={1}
            max={60}
            unit={copy.parent.settings.min}
            onCommit={(parent_idle_minutes) => commit({ points: { ...points, parent_idle_minutes } })}
          />
        </Row>
      </Card>

      <Toast text={said.text} bad={said.bad} />
    </Pane>
  )
}

/** Veg periods no feed carries, named by hand: a list, and a row to add one. */
function ExtraDates({
  dates,
  onChange,
}: {
  dates: DateRange[]
  onChange: (next: DateRange[]) => void
}) {
  const [name, setName] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const ids = { name: useId(), from: useId(), to: useId() }
  const ready = name.trim() !== '' && from !== '' && to !== '' && to >= from

  return (
    <div className="pp-extra">
      <Row label={copy.parent.settings.extraDates} note={copy.parent.settings.extraNote} />
      {dates.map((span, index) => (
        <Row key={`${span.name}-${span.from}`} label={span.name} note={`${span.from} – ${span.to}`}>
          <button
            type="button"
            className="pp-text-button"
            aria-label={copy.parent.settings.remove(span.name)}
            onClick={() => onChange(dates.filter((_, at) => at !== index))}
          >
            {copy.parent.settings.removeShort}
          </button>
        </Row>
      ))}
      <div className="pp-extra-add">
        <label className="pp-field" htmlFor={ids.name}>
          <span className="pp-row-label">{copy.parent.settings.extraName}</span>
          <input
            id={ids.name}
            className="pp-input"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label className="pp-field" htmlFor={ids.from}>
          <span className="pp-row-label">{copy.parent.settings.from}</span>
          <input
            id={ids.from}
            className="pp-input"
            type="date"
            value={from}
            onChange={(event) => setFrom(event.target.value)}
          />
        </label>
        <label className="pp-field" htmlFor={ids.to}>
          <span className="pp-row-label">{copy.parent.settings.to}</span>
          <input
            id={ids.to}
            className="pp-input"
            type="date"
            value={to}
            onChange={(event) => setTo(event.target.value)}
          />
        </label>
        <button
          type="button"
          className="pp-button"
          disabled={!ready}
          onClick={() => {
            onChange([...dates, { name: name.trim(), from, to }])
            setName('')
            setFrom('')
            setTo('')
          }}
        >
          {copy.parent.settings.add}
        </button>
      </div>
    </div>
  )
}

/** One child: name, animal, colour, and the code on their card. */
function KidSettings({
  kid,
  hasPin,
  onChange,
  onPin,
}: {
  kid: KidEdit
  hasPin: boolean
  onChange: (patch: Partial<KidEdit>) => void
  onPin: (pin: string) => Promise<unknown>
}) {
  const [name, setName] = useState(kid.name)
  const [seenName, setSeenName] = useState(kid.name)
  const [colour, setColour] = useState(kid.color)
  const [seenColour, setSeenColour] = useState(kid.color)
  const [picking, setPicking] = useState(false)
  const [pin, setPin] = useState('')
  const ids = { name: useId(), colour: useId(), pin: useId() }

  if (seenName !== kid.name) {
    setSeenName(kid.name)
    setName(kid.name)
  }
  if (seenColour !== kid.color) {
    setSeenColour(kid.color)
    setColour(kid.color)
  }

  return (
    <div className="pp-kid-settings">
      <h3 className="pp-school-head">{kid.name}</h3>
      <Row label={copy.parent.settings.name} htmlFor={ids.name}>
        <input
          id={ids.name}
          className="pp-input pp-input-short"
          value={name}
          maxLength={24}
          onChange={(event) => setName(event.target.value)}
          onBlur={() => {
            if (name.trim() && name.trim() !== kid.name) {
              onChange({ name: name.trim() })
            } else {
              setName(kid.name)
            }
          }}
        />
      </Row>
      <Row label={copy.parent.settings.avatar}>
        <button
          type="button"
          className="pp-avatar-button"
          aria-label={copy.parent.settings.chooseAvatar(kid.name)}
          onClick={() => setPicking(true)}
        >
          <Avatar name={kid.name} avatar={kid.avatar} colour={kid.color} size={24} />
        </button>
      </Row>
      <Row label={copy.parent.settings.colour} htmlFor={ids.colour}>
        <input
          id={ids.colour}
          className="pp-swatch"
          type="color"
          value={colour}
          onChange={(event) => setColour(event.target.value)}
          onBlur={() => {
            if (colour.toLowerCase() !== kid.color.toLowerCase()) {
              onChange({ color: colour })
            }
          }}
        />
      </Row>
      <Row
        label={copy.parent.settings.pin}
        note={hasPin ? copy.parent.settings.pinOn : copy.parent.settings.pinOff}
        htmlFor={ids.pin}
      >
        <input
          id={ids.pin}
          className="pp-input pp-input-pin"
          inputMode="numeric"
          maxLength={4}
          placeholder="0000"
          value={pin}
          onChange={(event) => setPin(event.target.value.replace(/\D/g, '').slice(0, 4))}
        />
        <button
          type="button"
          className="pp-button"
          disabled={pin.length !== 4}
          onClick={() => void onPin(pin).then(() => setPin(''))}
        >
          {copy.parent.settings.setPin}
        </button>
        <button
          type="button"
          className="pp-text-button"
          disabled={!hasPin}
          onClick={() => void onPin('')}
        >
          {copy.parent.settings.clearPin}
        </button>
      </Row>

      {picking ? (
        <Sheet title={copy.parent.settings.chooseAvatar(kid.name)} onClose={() => setPicking(false)}>
          <div className="pp-avatars">
            {AVATARS.map((animal) => (
              <button
                key={animal}
                type="button"
                className={animal === kid.avatar ? 'pp-avatar-choice pp-avatar-on' : 'pp-avatar-choice'}
                aria-label={animal}
                aria-pressed={animal === kid.avatar}
                onClick={() => {
                  setPicking(false)
                  if (animal !== kid.avatar) {
                    onChange({ avatar: animal })
                  }
                }}
              >
                <Avatar name={kid.name} avatar={animal} colour={kid.color} size={56} />
              </button>
            ))}
          </div>
        </Sheet>
      ) : null}
    </div>
  )
}
