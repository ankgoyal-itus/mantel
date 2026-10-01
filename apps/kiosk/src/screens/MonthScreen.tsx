import { useCallback, useEffect, useMemo, useState } from 'react'

import { getJson } from '../api/client'
import type { MonthDay, PanchangDay, PanchangMonth } from '../api/types'
import Icon from '../components/icons/Icon'
import { copy } from '../copy'
import { dateLong, parseApiDate } from '../format'
import '../styles/month.css'
import {
  type Cell,
  cellsFor,
  isHatched,
  masaLine,
  monthName,
  shiftMonth,
  weeksIn,
} from './month/grid'

const WEEKDAY_HEADS = copy.month.weekdays

/** The paksha as a half moon: waxing lit on the right, waning on the left. */
const PAKSHA_GLYPH: Record<string, string> = { shukla: '◑', krishna: '◐' }

export type MonthScreenProps = {
  /** "2026-10". The month the calendar opens on. */
  initialYm: string
  today: string
  kidColours: Record<string, string>
  /** The kids' names, for the legend under the grid. */
  kidNames?: Record<string, string>
  onDone: () => void
  /** Switch to the list of the same window. */
  onShowList?: () => void
  /** Injected by the tests; the real one fetches. */
  load?: (ym: string) => Promise<PanchangMonth>
  loadDay?: (date: string) => Promise<PanchangDay>
  /**
   * Months already in hand. The tests render without effects, so the fixture
   * comes in this way; in the browser it starts empty and the effect fills it.
   */
  months?: Record<string, PanchangMonth>
  /** A day already open, for the same reason. */
  day?: PanchangDay | null
  /** Start in panchang mode. Remembered for the session by the shell. */
  panchang?: boolean
  onPanchangChange?: (on: boolean) => void
}

/** Saturday or Sunday, from the API's date. */
function isWeekendDate(date: string): boolean {
  const day = parseApiDate(date).getDay()
  return day === 0 || day === 6
}

function clockOf(iso: string | null): string {
  if (!iso) {
    return '—'
  }
  const at = new Date(iso)
  const hours = at.getHours() % 12 === 0 ? 12 : at.getHours() % 12
  const minutes = String(at.getMinutes()).padStart(2, '0')
  return `${hours}:${minutes} ${at.getHours() < 12 ? 'am' : 'pm'}`
}

function MoonGlyph({ full, className = 'mo-moon' }: { full: boolean; className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <circle
        cx="8"
        cy="8"
        r="5.5"
        fill={full ? 'currentColor' : 'none'}
        stroke="currentColor"
        strokeWidth="1.75"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}

/** The veg leaf: the app's own leaf, from the one line set. */
function LeafGlyph({ className = 'mo-leaf' }: { className?: string }) {
  return <Icon name="leaf" size={16} className={className} />
}

/**
 * The day's dots, at most two: the observance — amber for a festival, purple
 * for a holiday — then grey when the family has something on. Kids are not
 * dots any more: each has a bar in their colour under the number.
 */
export function dotsFor(day: MonthDay): string[] {
  const dots: string[] = []
  if (day.observances.length > 0) {
    dots.push(day.holiday ? 'var(--holiday)' : 'var(--festival)')
  }
  if (day.family) {
    dots.push('var(--muted)')
  }
  return dots
}

/** Kids with something on, in the order the family lists them. */
export function barsFor(day: MonthDay, kidColours: Record<string, string>): string[] {
  const busy = new Set([...(day.kids ?? []), ...day.school_kids])
  return Object.keys(kidColours).filter((kid) => busy.has(kid)).map((kid) => kidColours[kid])
}

/**
 * "Dwadashi ◑": the tithi's name and the paksha's half moon. `short` is for
 * a cell the day panel has narrowed: "Dwad ◑", so the glyph still fits.
 */
export function tithiLabel(day: MonthDay, short = false): string {
  const glyph = PAKSHA_GLYPH[day.paksha] ?? ''
  const name = day.tithi_name || day.tithi_short
  return `${short ? (copy.month.tithiShort[name] ?? name) : name} ${glyph}`.trim()
}

function DayCell({
  cell,
  today,
  selected,
  kidColours,
  panchang,
  onPick,
}: {
  cell: Cell
  today: string
  selected: string | null
  kidColours: Record<string, string>
  /** Family mode is the default; the almanac marks are opt-in. */
  panchang: boolean
  onPick: (date: string) => void
}) {
  const day = cell.data
  const classes = ['mo-cell']
  if (!cell.inMonth) {
    classes.push('mo-out')
  }
  if (cell.date === today) {
    classes.push('mo-today')
  }
  if (cell.date === selected) {
    classes.push('mo-selected')
  }
  if (isHatched(day)) {
    classes.push('mo-noschool')
  }
  if (cell.date < today) {
    classes.push('mo-past')
  }

  const full = day?.flags.includes('purnima') ?? false
  const dark = day?.flags.includes('amavasya') ?? false

  return (
    <button type="button" className={classes.join(' ')} onClick={() => onPick(cell.date)}>
      <span className="mo-number">{cell.day}</span>
      {isHatched(day) && cell.inMonth && !panchang ? (
        <span className="mo-noschool-note">{copy.month.noSchool}</span>
      ) : null}
      {/* A 3px bar per child with something on, in their colour. */}
      {day && cell.inMonth && barsFor(day, kidColours).length > 0 ? (
        <span className="mo-bars" aria-hidden="true">
          {barsFor(day, kidColours).map((colour) => (
            <span key={colour} className="mo-bar" style={{ background: colour }} />
          ))}
        </span>
      ) : null}

      {/* One word and one dot, and everything else in the panel.

          A cell is 90px across. Two observances, a tithi, a moon, a leaf and
          three dots all fitted, in the sense that they did not overflow — and
          the grid stopped being a calendar and became a table of abbreviations
          nobody read. What a day looks like now is: its number, the first
          thing that makes it different, and a dot if somebody has something
          on. The rest is one tap away, which is where it was always legible. */}
      {!panchang && day && cell.inMonth && day.observances.length > 0 ? (
        <span
          className={
            day.holiday ? 'mo-observance-name mo-observance-holiday' : 'mo-observance-name'
          }
        >
          {shortName(day.observances[0])}
        </span>
      ) : null}

      {panchang && day && cell.inMonth ? (
        <span className="mo-tithi" aria-label={tithiLabel(day)}>
          {/* The whole name, or — in a cell too narrow for it, upright —
              the short form with the glyph kept: never an ellipsis. */}
          <span className="mo-tithi-long" aria-hidden="true">
            {tithiLabel(day)}
          </span>
          <span className="mo-tithi-short" aria-hidden="true">
            {tithiLabel(day, true)}
          </span>
        </span>
      ) : null}
      {panchang && cell.inMonth && (full || dark) ? <MoonGlyph full={full} /> : null}
      {panchang && day && cell.inMonth && !day.non_veg_ok ? <LeafGlyph /> : null}
      {day && cell.inMonth && dotsFor(day).length > 0 ? (
        <span className="mo-dots">
          {dotsFor(day).map((colour) => (
            <span key={colour} className="mo-dot" style={{ background: colour }} />
          ))}
        </span>
      ) : null}
    </button>
  )
}

/**
 * What a 90px cell calls an observance.
 *
 * It used to take the last meaty word, on the theory that these names end in
 * the thing itself — and October came out reading "Jayanti", "Festivities",
 * "Saptami", "Columbus": four cells, none of which names a festival anybody
 * in this house would recognise. The last word is the wrong end of most of
 * them, so the names worth having are a map in copy.ts and everything else is
 * the first two words with the feeds' scaffolding taken off the front.
 *
 * The full name is in the panel, one tap away.
 */

/** "First Day of", "Last Day of", a leading "The". */
const SCAFFOLD = /^(?:the\s+|(?:first|last)\s+day\s+of\s+)+/i

/** Words that carry nothing once they are on their own at the end. */
const TRAILING = /\s+(?:day|festivities|festival)$/i

export function shortName(observance: string): string {
  // A comma or a slash starts an alternative name; the first one is the name.
  const whole = observance.replace(/\s*[,/].*$/, '').trim()
  const known = copy.month.short[whole.toLowerCase()]
  if (known) {
    return known
  }

  let rest = whole.replace(SCAFFOLD, '').trim()
  // Only once: "Columbus Day" is the name, and is in the map above.
  rest = rest.replace(TRAILING, '').trim()

  const words = rest.split(/\s+/).filter(Boolean)
  if (words.length === 0) {
    return whole
  }
  return words.slice(0, 2).join(' ')
}

/**
 * What the marks mean, in one row under the grid: whose bar is whose, the
 * dots, the hatch, and the almanac's leaf and moons.
 */
function Legend({
  kidColours,
  kidNames,
}: {
  kidColours: Record<string, string>
  kidNames: Record<string, string>
}) {
  const said = copy.month.legend
  return (
    <div className="mo-legend">
      {Object.entries(kidColours).map(([kid, colour]) => (
        <span key={kid} className="mo-key">
          <span className="mo-key-bar" style={{ background: colour }} />
          {kidNames[kid] ?? kid}
        </span>
      ))}
      <span className="mo-key">
        <span className="mo-dot" style={{ background: 'var(--muted)' }} />
        {said.family}
      </span>
      <span className="mo-key">
        <span className="mo-key-hatch" />
        {said.school}
      </span>
      <span className="mo-key">
        <span className="mo-dot" style={{ background: 'var(--festival)' }} />
        {said.festival}
      </span>
      <span className="mo-key">
        <span className="mo-dot" style={{ background: 'var(--holiday)' }} />
        {said.holiday}
      </span>
      <span className="mo-key">
        <LeafGlyph className="mo-key-glyph mo-key-leaf" />
        {said.veg}
      </span>
      <span className="mo-key">
        <MoonGlyph full={false} className="mo-key-glyph" />
        {said.newMoon}
      </span>
      <span className="mo-key">
        <MoonGlyph full className="mo-key-glyph" />
        {said.fullMoon}
      </span>
    </div>
  )
}

function Panel({ day, showYogaKarana }: { day: PanchangDay; showYogaKarana: boolean }) {
  const meals = ['breakfast', 'lunch', 'dinner'] as const
  const planned = meals.filter((slot) => day.meals[slot])

  return (
    <aside className="mo-panel">
      <h2 className="mo-panel-date">{dateLong(parseApiDate(day.date))}</h2>
      <div className="mo-panel-masa">
        {copy.month.samvat(day.masa.name, day.masa.adhika, day.samvat.vikram)}
      </div>

      <dl className="mo-facts">
        <dt>{copy.month.tithi}</dt>
        <dd>
          {day.tithi.name} <span className="mo-paksha">{day.tithi.paksha}</span>
          {day.tithi.ends_at ? (
            <span className="mo-until">{copy.month.until(clockOf(day.tithi.ends_at))}</span>
          ) : null}
        </dd>
        <dt>{copy.month.nakshatra}</dt>
        <dd>
          {day.nakshatra.name}
          {day.nakshatra.ends_at ? (
            <span className="mo-until">{copy.month.until(clockOf(day.nakshatra.ends_at))}</span>
          ) : null}
        </dd>
        {showYogaKarana ? (
          <>
            <dt>{copy.month.yoga}</dt>
            <dd>{day.yoga.name}</dd>
            <dt>{copy.month.karana}</dt>
            <dd>{day.karana.name}</dd>
          </>
        ) : null}
        <dt>{copy.month.sunrise}</dt>
        <dd>{clockOf(day.sunrise)}</dd>
        <dt>{copy.month.sunset}</dt>
        <dd>{clockOf(day.sunset)}</dd>
        <dt>{copy.month.moonrise}</dt>
        <dd>{clockOf(day.moonrise)}</dd>
      </dl>

      {day.observances.length > 0 ? (
        <div className="mo-panel-block">
          {day.observances.map((observance) => (
            <div key={observance.name} className="mo-observance">
              {observance.name}
            </div>
          ))}
        </div>
      ) : null}

      <div className="mo-panel-block">
        {/* Never "No school" on a Saturday or a Sunday. */}
        {day.school.is_school_day || !isWeekendDate(day.date) || day.school.note ? (
          <div className="mo-school">
            {day.school.is_school_day
              ? (day.school.note ?? copy.month.schoolDay)
              : (day.school.note ?? copy.month.noSchool)}
          </div>
        ) : null}
        {!day.diet.non_veg_ok && day.diet.reasons.length > 0 ? (
          <div className="mo-veg">{copy.month.vegBecause(day.diet.reasons)}</div>
        ) : null}
      </div>

      {planned.length > 0 ? (
        <div className="mo-panel-block mo-meals">
          {planned.map((slot) => (
            <div key={slot} className="mo-meal">
              <span className="mo-meal-label">{slot}</span>
              <span className="mo-meal-name">{day.meals[slot]}</span>
            </div>
          ))}
        </div>
      ) : null}
    </aside>
  )
}

export default function MonthScreen({
  initialYm,
  today,
  kidColours,
  kidNames = {},
  onDone,
  onShowList,
  load,
  loadDay,
  months: seededMonths,
  day: seededDay = null,
  panchang: seededPanchang = false,
  onPanchangChange,
}: MonthScreenProps) {
  const [ym, setYm] = useState(initialYm)
  const [months, setMonths] = useState<Record<string, PanchangMonth>>(seededMonths ?? {})
  const [selected, setSelected] = useState<string | null>(seededDay?.date ?? null)
  const [panel, setPanel] = useState<PanchangDay | null>(seededDay)
  const [panchang, setPanchang] = useState(seededPanchang)

  const fetchMonth = useMemo(
    () => load ?? ((want: string) => getJson<PanchangMonth>(`/api/panchang/month?ym=${want}`)),
    [load],
  )
  const fetchDay = useMemo(
    () => loadDay ?? ((date: string) => getJson<PanchangDay>(`/api/panchang?date=${date}`)),
    [loadDay],
  )

  // One fetch per visible month, kept for the session: paging back and forth
  // through a year should not ask the API the same question twice.
  useEffect(() => {
    if (months[ym]) {
      return
    }
    let cancelled = false
    fetchMonth(ym)
      .then((found) => {
        if (!cancelled) {
          setMonths((held) => ({ ...held, [ym]: found }))
        }
      })
      .catch(() => {
        // Leave the grid empty; the header and the buttons still work.
      })
    return () => {
      cancelled = true
    }
  }, [ym, months, fetchMonth])

  const days = useMemo(() => months[ym]?.days ?? [], [months, ym])
  const cells = useMemo(() => cellsFor(ym, days), [ym, days])

  const pick = useCallback(
    (date: string) => {
      // The same day again closes the panel, which is how you put it away
      // without reaching for Done.
      if (date === selected) {
        setSelected(null)
        setPanel(null)
        return
      }
      setSelected(date)
      setPanel(null)
      fetchDay(date)
        .then(setPanel)
        .catch(() => setPanel(null))
    },
    [selected, fetchDay],
  )

  const vikram = panel?.samvat.vikram ?? null

  return (
    <div className={panel ? 'screen month month-with-panel' : 'screen month'}>
      <div className="mo-main">
        <header className="mo-head">
          <div className="mo-title">
            <h1 className="mo-month">{monthName(ym)}</h1>
            <div className="mo-masa">{masaLine(days, vikram)}</div>
          </div>
          <div className="mo-nav">
            {onShowList ? (
              <div className="li-segments mo-segments">
                <button type="button" className="li-segment li-segment-on">
                  {copy.list.month}
                </button>
                <button type="button" className="li-segment" onClick={onShowList}>
                  {copy.list.list}
                </button>
              </div>
            ) : null}
            <button
              type="button"
              className={panchang ? 'mo-button mo-toggle mo-toggle-on' : 'mo-button mo-toggle'}
              onClick={() => {
                setPanchang(!panchang)
                onPanchangChange?.(!panchang)
              }}
            >
              {copy.month.panchang}
            </button>
            <button type="button" className="mo-button" onClick={() => setYm(shiftMonth(ym, -1))}>
              ‹
            </button>
            <button type="button" className="mo-button" onClick={() => setYm(shiftMonth(ym, 1))}>
              ›
            </button>
            <button type="button" className="mo-button mo-done" onClick={onDone}>
              {copy.month.done}
            </button>
          </div>
        </header>

        <div className="mo-weekdays">
          {WEEKDAY_HEADS.map((name) => (
            <div key={name} className="mo-weekday">
              {name}
            </div>
          ))}
        </div>

        <div className="mo-grid" style={{ gridTemplateRows: `repeat(${weeksIn(ym)}, 1fr)` }}>
          {cells.map((cell) => (
            <DayCell
              key={cell.date}
              cell={cell}
              today={today}
              selected={selected}
              kidColours={kidColours}
              panchang={panchang || cell.date === selected}
              onPick={pick}
            />
          ))}
        </div>

        <Legend kidColours={kidColours} kidNames={kidNames} />
      </div>

      {panel ? <Panel day={panel} showYogaKarana={false} /> : null}
    </div>
  )
}
