import { useEffect, useMemo, useRef, useState } from 'react'

import type { Day, Kid, Weekday } from '../api/types'
import Avatar from '../components/Avatar'
import Icon from '../components/icons/Icon'
import { copy } from '../copy'
import { dateShort, parseApiDate, timeRange } from '../format'
import { kidVars } from '../kidVars'
import { dayOffNote } from './day/badges'
import '../styles/list.css'
import { type Filter, type ListDay, daysFrom, filtersFor, visible } from './list/rows'

export type ListScreenProps = {
  agenda: Day[]
  kids: Kid[]
  today: string
  onDone: () => void
  onShowMonth: () => void
  /** Chosen filters, kept for the session by the shell. */
  filters?: Filter[]
  onFiltersChange?: (filters: Filter[]) => void
  /** Open scrolled to this day, when the dashboard asked for one. */
  startDate?: string | null
}

/* A chip is a word and a border, so it takes the ink form of each meaning:
   on paper the colours themselves are too pale to be read at 20px. The dots
   further down stay the colours, because a dot is not read, it is spotted. */
const SHARED_COLOUR: Record<string, string> = {
  family: 'var(--fg)',
  school: 'var(--ink-school)',
  festival: 'var(--ink-festival)',
  holiday: 'var(--ink-holiday)',
}

/** A child's chip is in their ink (shell/kidPalette.ts). */
function chipColour(filter: Filter): string {
  return SHARED_COLOUR[filter] ?? `var(--ink-${filter})`
}

function label(filter: Filter, kids: Kid[]): string {
  const kid = kids.find((k) => k.id === filter)
  return kid ? kid.name : copy.list.filters[filter]
}

function DayBlock({
  day,
  kids,
  start = false,
}: {
  day: ListDay
  kids: Kid[]
  start?: boolean
}) {
  const when = parseApiDate(day.date)
  // "No school" is news on a Tuesday and not on a Saturday: the one rule
  // every surface keeps (badges.ts).
  const note = day.isSchoolDay
    ? day.schoolNote
    : dayOffNote({ weekday: day.weekday as Weekday, is_school_day: false, school_note: day.schoolNote })

  return (
    <section className="li-day" data-start={start || undefined}>
      <header className="li-head">
        <span className="li-date">{dateShort(when)}</span>
        {day.observances.map((observance) => (
          <span
            key={observance.name}
            className="li-mark"
            style={{
              color: observance.kind === 'festival' ? 'var(--ink-festival)' : 'var(--ink-holiday)',
            }}
          >
            {observance.name}
          </span>
        ))}
        {note ? (
          <span className="li-mark" style={{ color: 'var(--ink-school)' }}>
            {note}
          </span>
        ) : null}
      </header>

      {day.rows.map((row) => {
        const owner = kids.find((kid) => kid.id === row.owner) ?? null
        const tagged = row.tag
          ? (kids.find((kid) => kid.name.toLowerCase() === row.tag?.toLowerCase()) ?? null)
          : null
        return (
          <div key={row.key} className="li-row">
            {/* Whose row this is: the kid's face, or the family's glyph for
                something everybody is doing. */}
            <span className="li-who" aria-hidden="true">
              {owner ? (
                <span style={kidVars(owner.id, owner.color)}>
                  <Avatar name={owner.name} avatar={owner.avatar} size={24} />
                </span>
              ) : (
                <Icon name="family" size={24} className="li-family" />
              )}
            </span>
            <span className="li-time">
              {row.time ? timeRange(row.time, null) : copy.list.allDay}
            </span>
            <span className="li-title">{row.title}</span>
            {/* "[Sam]" on the end of a family title, as their initial. */}
            {row.tag ? (
              <span
                className="li-tag"
                style={tagged ? kidVars(tagged.id, tagged.color) : undefined}
                aria-label={row.tag}
              >
                {row.tag.slice(0, 1).toUpperCase()}
              </span>
            ) : null}
            {row.school ? <Icon name="school" size={20} className="li-glyph" /> : null}
            {row.where ? <span className="li-where">{row.where}</span> : null}
          </div>
        )
      })}
    </section>
  )
}

export default function ListScreen({
  agenda,
  kids,
  onDone,
  onShowMonth,
  filters: seeded = [],
  onFiltersChange,
  startDate = null,
}: ListScreenProps) {
  const [on, setOn] = useState<Set<Filter>>(() => new Set(seeded))

  const days = useMemo(() => visible(daysFrom(agenda), on), [agenda, on])
  const scrollRef = useRef<HTMLDivElement | null>(null)

  // Once, as it opens: the day that was asked for at the top of the list.
  useEffect(() => {
    const day = scrollRef.current?.querySelector<HTMLElement>('[data-start]')
    const scroller = scrollRef.current
    if (day && scroller) {
      scroller.scrollTop = day.offsetTop - scroller.offsetTop
    }
  }, [])

  const toggle = (filter: Filter) => {
    const next = new Set(on)
    if (next.has(filter)) {
      next.delete(filter)
    } else {
      next.add(filter)
    }
    setOn(next)
    onFiltersChange?.([...next])
  }

  return (
    <div className="screen list">
      <header className="li-bar">
        <div className="li-segments">
          <button type="button" className="li-segment" onClick={onShowMonth}>
            {copy.list.month}
          </button>
          <button type="button" className="li-segment li-segment-on">
            {copy.list.list}
          </button>
        </div>

        <div className="li-chips">
          <button
            type="button"
            className={on.size === 0 ? 'li-chip li-chip-on' : 'li-chip'}
            onClick={() => {
              setOn(new Set())
              onFiltersChange?.([])
            }}
          >
            {copy.list.all}
          </button>
          {filtersFor(kids.map((kid) => kid.id)).map((filter) => (
            <button
              key={filter}
              type="button"
              className={on.has(filter) ? 'li-chip li-chip-on' : 'li-chip'}
              style={{ ['--chip' as string]: chipColour(filter) }}
              onClick={() => toggle(filter)}
            >
              {label(filter, kids)}
            </button>
          ))}
        </div>

        <button type="button" className="li-done" onClick={onDone}>
          {copy.list.done}
        </button>
      </header>

      {/* The one screen besides the parent's that scrolls, because sixty days
          of agenda is a list and a list is read by scrolling it. */}
      <div className="li-scroll" ref={scrollRef}>
        {days.length === 0 ? (
          <p className="empty li-empty">{copy.list.nothing}</p>
        ) : (
          days.map((day) => (
            <DayBlock key={day.date} day={day} kids={kids} start={day.date === startDate} />
          ))
        )}
      </div>
    </div>
  )
}
