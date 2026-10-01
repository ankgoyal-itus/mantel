import { useEffect, useRef, useState } from 'react'

import { sessionLeft, signOut } from '../../api/parent'
import type { Kid, Parent } from '../../api/types'
import Avatar from '../../components/Avatar'
import Fallback from '../../components/Fallback'
import Icon, { type IconName } from '../../components/icons/Icon'
import { copy } from '../../copy'
import { kidVars } from '../../kidVars'
import '../../styles/parent.css'
import AboutSection from './AboutSection'
import ApprovalsSection from './ApprovalsSection'
import EventsSection from './EventsSection'
import MealsSection from './MealsSection'
import PhotosSection from './PhotosSection'
import PointsSection from './PointsSection'
import SettingsSection from './SettingsSection'

export type Section = 'approvals' | 'meals' | 'events' | 'photos' | 'points' | 'settings' | 'about'

export const SECTIONS: { id: Section; glyph: IconName }[] = [
  { id: 'approvals', glyph: 'check' },
  { id: 'meals', glyph: 'meal' },
  { id: 'events', glyph: 'calendar' },
  { id: 'photos', glyph: 'camera' },
  { id: 'points', glyph: 'coin' },
  { id: 'settings', glyph: 'gear' },
  { id: 'about', glyph: 'info' },
]

/** The house's rule when settings have not said: two quiet minutes. */
const DEFAULT_IDLE_MINUTES = 2

/** How often the countdown is re-read from the API, which owns the cookie. */
const SESSION_POLL_MS = 30000

/**
 * Two letters that tell this grown-up apart from the others: "Sa" and "Sh"
 * for Sam and Shreya, never two identical "S" discs. Two letters always,
 * and a third only if two would still collide.
 */
export function initialsFor(name: string, everyone: readonly string[]): string {
  const clean = (value: string) => value.trim()
  const mine = clean(name)
  for (let length = 2; length <= mine.length; length += 1) {
    const prefix = mine.slice(0, length).toLowerCase()
    const shared = everyone.filter(
      (other) => clean(other) !== mine && clean(other).slice(0, length).toLowerCase() === prefix,
    )
    if (shared.length === 0) {
      return mine.slice(0, 1).toUpperCase() + mine.slice(1, length).toLowerCase()
    }
  }
  return mine.slice(0, 2)
}

/**
 * The parent screen: a settings app on the kiosk's own paper.
 *
 * A rail of sections on the left and one section at a time beside it, from
 * 900px up; below that — a phone — the rail becomes a bar of glyphs along the
 * bottom and Done moves to the top corner. It opens on Approvals when
 * anything is waiting, because that is the one thing only a parent can do,
 * and on Meals otherwise.
 *
 * The session is the API's: ten minutes from the PIN, and another ten for a
 * parent still working in the last minute of them. The rail counts it down
 * from what the API says is left rather than keeping a clock of its own.
 */
export default function ParentScreen({
  onDone,
  kids = [],
  parents = [],
  pending = 0,
  idleMinutes = DEFAULT_IDLE_MINUTES,
  onPointsChanged,
  onDashboard,
}: {
  onDone: () => void
  kids?: Kid[]
  /** The rest of the family, for the faces at the top of the rail. */
  parents?: Parent[]
  /** How many things wait, decided before this opened. */
  pending?: number
  /** settings.points.parent_idle_minutes: quiet this long and it closes. */
  idleMinutes?: number
  /** A balance moved: the wall should read the new numbers. */
  onPointsChanged?: () => void
  /** On a phone, the way to the dashboard itself. */
  onDashboard?: () => void
}) {
  const [section, setSection] = useState<Section>(pending > 0 ? 'approvals' : 'meals')
  const [waiting, setWaiting] = useState(pending)
  // "Plan it" presses, which the Meals tab answers by opening a dinner.
  const [planOut, setPlanOut] = useState(0)
  const [left, setLeft] = useState<number | null>(null)
  const [activity, setActivity] = useState(() => Date.now())
  const paneRef = useRef<HTMLDivElement | null>(null)

  const doneRef = useRef(onDone)
  useEffect(() => {
    doneRef.current = onDone
  }, [onDone])

  // Quiet for the house's idle minutes and it closes itself, so the wall
  // never sits on an open session.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      void signOut()
      doneRef.current()
    }, idleMinutes * 60000)
    return () => window.clearTimeout(timer)
  }, [activity, idleMinutes])

  // What the API says is left, re-read after anything happens (an action in
  // the last minute will have extended it) and every half minute besides.
  useEffect(() => {
    let cancelled = false
    const read = () => {
      void sessionLeft().then((seconds) => {
        if (!cancelled) {
          setLeft(seconds)
        }
      })
    }
    read()
    const timer = window.setInterval(read, SESSION_POLL_MS)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [activity])

  // A session that has run out has run out: back to the wall.
  useEffect(() => {
    if (left === 0) {
      doneRef.current()
    }
  }, [left])

  const close = () => {
    void signOut()
    onDone()
  }

  const open = (next: Section) => {
    setSection(next)
    paneRef.current?.scrollTo({ top: 0 })
  }

  const minutes = left === null ? null : Math.max(1, Math.ceil(left / 60))
  const title = copy.parent.sections[section].title

  return (
    <div
      className="pp"
      onPointerDown={() => setActivity(Date.now())}
      onKeyDown={() => setActivity(Date.now())}
    >
      <nav className="pp-rail" aria-label={copy.parent.title}>
        <div className="pp-family">
          <span className="pp-family-name">{copy.parent.rail.family}</span>
          <span className="pp-faces">
            {kids.map((kid) => (
              <span key={kid.id} className="pp-face" style={kidVars(kid.id, kid.color)}>
                <Avatar name={kid.name} avatar={kid.avatar} size={24} />
              </span>
            ))}
            {parents.map((one) => (
              <span key={one.id} className="pp-face pp-face-parent" title={one.name}>
                <Avatar
                  name={one.name}
                  avatar={null}
                  size={24}
                  initials={initialsFor(one.name, parents.map((other) => other.name))}
                />
              </span>
            ))}
          </span>
          {minutes !== null ? (
            <span className="pp-session">{copy.parent.rail.session(minutes)}</span>
          ) : null}
        </div>

        <ul className="pp-sections">
          {SECTIONS.map(({ id, glyph }) => (
            <li key={id}>
              <button
                type="button"
                className={id === section ? 'pp-section pp-section-on' : 'pp-section'}
                aria-current={id === section ? 'page' : undefined}
                aria-label={copy.parent.sections[id].title}
                data-section={id}
                onClick={() => open(id)}
              >
                <Icon name={glyph} size={22} className="pp-section-glyph" />
                <span className="pp-section-label">{copy.parent.sections[id].title}</span>
                {id === 'approvals' && waiting > 0 ? (
                  <span className="pp-badge" aria-label={copy.parent.rail.waiting(waiting)}>
                    {waiting}
                  </span>
                ) : null}
              </button>
            </li>
          ))}
        </ul>

        <button type="button" className="pp-section pp-done-row" onClick={close}>
          <Icon name="chevron-left" size={22} className="pp-section-glyph" />
          <span className="pp-section-label">{copy.parent.done}</span>
        </button>
      </nav>

      <main className="pp-pane" ref={paneRef}>
        {/* The phone's top bar: which section, and the way out. */}
        <div className="pp-phone-bar">
          <span className="pp-phone-title">
            {minutes !== null ? copy.parent.rail.session(minutes) : title}
          </span>
          <button type="button" className="pp-text-button" onClick={close}>
            {copy.parent.done}
          </button>
        </div>

        <Fallback what={title}>
          {section === 'approvals' ? (
            <ApprovalsSection
              kids={kids}
              onCount={setWaiting}
              onPointsChanged={onPointsChanged}
              onPlanOut={() => {
                setPlanOut((count) => count + 1)
                open('meals')
              }}
            />
          ) : section === 'meals' ? (
            <MealsSection
              kids={kids}
              onDecided={() => onPointsChanged?.()}
              planOut={planOut}
            />
          ) : section === 'events' ? (
            <EventsSection kids={kids} />
          ) : section === 'photos' ? (
            <PhotosSection />
          ) : section === 'points' ? (
            <PointsSection kids={kids} onPointsChanged={onPointsChanged} />
          ) : section === 'settings' ? (
            <SettingsSection />
          ) : (
            <AboutSection />
          )}
        </Fallback>

        {onDashboard ? (
          <button type="button" className="pp-text-button pp-escape" onClick={onDashboard}>
            {copy.parent.showDashboard}
          </button>
        ) : null}
      </main>
    </div>
  )
}
