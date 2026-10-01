import { useEffect, useState } from 'react'

import { getAbout, getCalendars, getHealth, reloadBoth } from '../../api/parent'
import type { About, CalendarRow, Health } from '../../api/types'
import Icon from '../../components/icons/Icon'
import QrCode from '../../components/QrCode'
import { copy } from '../../copy'
import { Card, Pane, Row, Toast } from './ui'

/** "ok (3m ago), 120 events" is fine; anything not starting ok is not. */
function healthy(value: string | undefined): boolean {
  return (value ?? '').startsWith('ok')
}

function HealthRow({ label, value }: { label: string; value: string | undefined }) {
  const good = healthy(value)
  return (
    <Row
      label={
        <span className="pp-feed">
          <span className={good ? 'pp-dot pp-dot-ok' : 'pp-dot pp-dot-error'} aria-hidden="true" />
          {label}
        </span>
      }
      note={value ?? '—'}
    >
      <span className={good ? 'pp-state pp-state-ok' : 'pp-state pp-state-error'}>
        {good ? copy.parent.about.ok : copy.parent.about.notOk}
      </span>
    </Row>
  )
}

/**
 * The machine: what version is running, whether everything it depends on
 * answered, how the second iPad finds it, and the two things a parent does
 * when something is off — reload both screens, or open the diagnostics.
 */
export default function AboutSection() {
  const [about, setAbout] = useState<About | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [feeds, setFeeds] = useState<CalendarRow[]>([])
  const [note, setNote] = useState({ text: '', bad: false })

  useEffect(() => {
    let cancelled = false
    getAbout()
      .then((found) => !cancelled && setAbout(found))
      .catch(() => undefined)
    getHealth()
      .then((found) => !cancelled && setHealth(found))
      .catch(() => undefined)
    getCalendars()
      .then((found) => !cancelled && setFeeds(found))
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [])

  const reload = () => {
    reloadBoth()
      .then(() => setNote({ text: copy.parent.about.reloadAsked, bad: false }))
      .catch((failure: Error) => setNote({ text: failure.message, bad: true }))
  }

  return (
    <Pane
      title={copy.parent.sections.about.title}
      description={about ? copy.parent.about.version(about.version) : undefined}
    >
      <Card title={copy.parent.about.health}>
        <HealthRow label={copy.parent.about.weather} value={health?.weather} />
        {feeds.map((feed) => (
          <HealthRow
            key={feed.id}
            label={copy.parent.about.calendar(
              feed.name ?? copy.parent.events.feeds[feed.id] ?? feed.id,
            )}
            value={health?.calendars[feed.id]}
          />
        ))}
        <HealthRow label={copy.parent.about.ledger} value={health?.ledger} />
        <HealthRow label={copy.parent.about.schoolYear} value={health?.school_year} />
        <HealthRow label={copy.parent.about.dietDays} value={health?.diet_days} />
      </Card>

      <Card title={copy.parent.about.secondIpad}>
        <div className="pp-lan">
          <div className="pp-lan-text">
            <p className="pp-row-label">{copy.parent.about.lanUrl}</p>
            <p className="pp-lan-url">{about?.lan_url ?? '—'}</p>
            <p className="pp-row-note">{copy.parent.about.lanNote}</p>
          </div>
          {about ? <QrCode text={about.lan_url} label={copy.parent.about.qr(about.lan_url)} /> : null}
        </div>
      </Card>

      <Card title={copy.parent.about.tools}>
        <Row label={copy.parent.about.reload} note={copy.parent.about.reloadNote}>
          <button type="button" className="pp-button" onClick={reload}>
            <Icon name="refresh" size={20} />
            {copy.parent.about.reloadShort}
          </button>
        </Row>
        <Row label={copy.parent.about.diagnostics} note={copy.parent.about.diagnosticsNote}>
          <a className="pp-button" href="/diag">
            {copy.parent.about.open}
          </a>
        </Row>
        <Row label={copy.parent.about.service} note={about?.launchd ?? '—'} />
      </Card>

      <Toast text={note.text} bad={note.bad} />
    </Pane>
  )
}
