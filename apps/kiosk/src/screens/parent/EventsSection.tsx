import { useCallback, useEffect, useId, useMemo, useState } from 'react'

import { getCalendars, getSchoolEvents, putSchoolEvents, refreshSources } from '../../api/parent'
import type { CalendarRow, Kid, Series } from '../../api/types'
import Avatar from '../../components/Avatar'
import Icon from '../../components/icons/Icon'
import { copy } from '../../copy'
import { kidVars } from '../../kidVars'
import { ageSaid } from './said'
import { Card, Pane, Row, Toast, Toggle } from './ui'

/** What a feed is called on this screen. A child's is their name. */
function feedName(row: CalendarRow, kids: Kid[]): string {
  if (row.kind === 'kid') {
    return kids.find((kid) => kid.id === row.kid)?.name ?? row.id
  }
  return row.name ?? copy.parent.events.feeds[row.id] ?? row.id
}

/** Which school a series comes from: the feed its first event was read from. */
function schoolOf(item: Series): string {
  return item.events[0]?.calendar_id ?? ''
}

/** "Tue 29 Sep", the next time a series happens. */
function dateLabel(value: string | null): string {
  if (!value) {
    return ''
  }
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString('en-US', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

/**
 * Where the calendar comes from, and which school events reach the wall.
 *
 * The feeds first, each with whether it answered and when — the answer to
 * "why is his practice not showing". A child's feed with no URL in .env
 * is not an error, it is a thing not set up yet, and says where the URL goes.
 * Then the school events: hundreds a term and almost none of them ours, so a
 * row per series, grouped by school, and a toggle per child.
 */
export default function EventsSection({ kids }: { kids: Kid[] }) {
  const [rows, setRows] = useState<CalendarRow[] | null>(null)
  const [series, setSeries] = useState<Series[]>([])
  const [filter, setFilter] = useState('')
  const [saving, setSaving] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  // Whether a series nobody has chosen reaches the wall. The file's default
  // is hide, and the API does not echo it back, so this starts there.
  const [showUnmatched, setShowUnmatched] = useState(false)
  const [note, setNote] = useState({ text: '', bad: false })
  const searchId = useId()

  const loadFeeds = useCallback(() => {
    getCalendars()
      .then(setRows)
      .catch(() => setRows([]))
  }, [])

  useEffect(() => {
    loadFeeds()
    getSchoolEvents()
      .then(setSeries)
      .catch(() => setNote({ text: copy.parent.events.failed, bad: true }))
  }, [loadFeeds])

  const refresh = () => {
    setRefreshing(true)
    refreshSources()
      .then(() => setNote({ text: copy.parent.events.refreshed, bad: false }))
      .catch(() => setNote({ text: copy.parent.events.refreshFailed, bad: true }))
      .finally(() => {
        setRefreshing(false)
        loadFeeds()
      })
  }

  const shown = useMemo(() => {
    const needle = filter.trim().toLowerCase()
    return needle
      ? series.filter((item) => item.title.toLowerCase().includes(needle))
      : series
  }, [series, filter])

  // A school's heading is its feed's name, as the feed list above says it.
  const schoolName = (id: string) => {
    const row = rows?.find((one) => one.id === id)
    return row ? feedName(row, kids) : (copy.parent.events.feeds[id] ?? id)
  }
  const schools = useMemo(() => {
    const found = new Map<string, Series[]>()
    for (const item of shown) {
      const school = schoolOf(item)
      found.set(school, [...(found.get(school) ?? []), item])
    }
    return [...found.entries()]
  }, [shown])

  const toggle = (item: Series, kidId: string) => {
    const next = item.shown_to.includes(kidId)
      ? item.shown_to.filter((id) => id !== kidId)
      : [...item.shown_to, kidId]
    setSaving(item.series)
    putSchoolEvents({ series: item.series, kids: next })
      .then((saved) => {
        setSeries(saved)
        setNote({ text: copy.parent.settings.saved, bad: false })
      })
      .catch((failure: Error) => setNote({ text: copy.parent.settings.notSaved(failure.message), bad: true }))
      .finally(() => setSaving(null))
  }

  const flipDefault = (next: boolean) => {
    setShowUnmatched(next)
    putSchoolEvents({ default: next ? 'show' : 'hide' })
      .then((saved) => {
        setSeries(saved)
        setNote({ text: copy.parent.settings.saved, bad: false })
      })
      .catch((failure: Error) => {
        setShowUnmatched(!next)
        setNote({ text: copy.parent.settings.notSaved(failure.message), bad: true })
      })
  }

  return (
    <Pane
      title={copy.parent.sections.events.title}
      description={copy.parent.sections.events.description}
      action={
        <button type="button" className="pp-button" onClick={refresh} disabled={refreshing}>
          <Icon name="refresh" size={20} />
          {refreshing ? copy.parent.events.refreshing : copy.parent.events.refresh}
        </button>
      }
    >
      <Card title={copy.parent.events.calendars}>
        {rows === null ? (
          <p className="pp-muted">{copy.parent.loading}</p>
        ) : (
          rows.map((row) => (
            <Row
              key={row.id}
              label={
                <span className="pp-feed">
                  <span className={`pp-dot pp-dot-${row.state}`} aria-hidden="true" />
                  {feedName(row, kids)}
                </span>
              }
              note={
                row.state === 'not_configured'
                  ? row.env
                    ? copy.parent.events.addSecret(row.env)
                    : copy.parent.events.notSetUp
                  : row.fetched_at
                    ? copy.parent.events.fetched(ageSaid(row.fetched_at), row.detail)
                    : row.state === 'error'
                      ? row.detail
                      : copy.parent.events.never
              }
            >
              <span className={`pp-state pp-state-${row.state}`}>
                {copy.parent.events.states[row.state]}
              </span>
            </Row>
          ))
        )}
      </Card>

      <Card title={copy.parent.events.schoolTitle}>
        <p className="pp-description">{copy.parent.events.help}</p>
        <Row label={copy.parent.events.unmatched}>
          <Toggle
            label={copy.parent.events.unmatched}
            checked={showUnmatched}
            onChange={flipDefault}
          />
        </Row>
        <label className="pp-field" htmlFor={searchId}>
          <span className="pp-row-label">{copy.parent.events.search}</span>
          <input
            id={searchId}
            className="pp-input"
            type="search"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          />
        </label>
        {schools.length === 0 ? <p className="pp-muted">{copy.parent.events.none}</p> : null}
        {schools.map(([school, items]) => (
          <div key={school} className="pp-school">
            <h3 className="pp-school-head">{schoolName(school)}</h3>
            {items.map((item) => (
              <Row
                key={item.series}
                label={<span className="clamp-1">{item.title}</span>}
                note={`${copy.parent.events.count(item.count)}${
                  item.next_date ? ` · ${copy.parent.events.next(dateLabel(item.next_date))}` : ''
                }`}
              >
                {item.always ? (
                  <span className="pp-locked">
                    <Icon name="lock" size={20} />
                    {copy.parent.events.always}
                  </span>
                ) : (
                  <span className="pp-kid-toggles">
                    {kids.map((kid) => {
                      const on = item.shown_to.includes(kid.id)
                      return (
                        <button
                          key={kid.id}
                          type="button"
                          role="switch"
                          aria-checked={on}
                          aria-label={copy.parent.events.showTo(item.title, kid.name)}
                          className={on ? 'pp-kid-toggle pp-kid-toggle-on' : 'pp-kid-toggle'}
                          style={kidVars(kid.id, kid.color)}
                          disabled={saving === item.series}
                          onClick={() => toggle(item, kid.id)}
                        >
                          <Avatar name={kid.name} avatar={kid.avatar} size={24} />
                          <span>{kid.name}</span>
                        </button>
                      )
                    })}
                  </span>
                )}
              </Row>
            ))}
          </div>
        ))}
      </Card>

      <Toast text={note.text} bad={note.bad} />
    </Pane>
  )
}
