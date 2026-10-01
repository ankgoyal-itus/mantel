import { useEffect, useId, useState } from 'react'

import { getJson } from '../../api/client'
import { awardPoints } from '../../api/parent'
import type { Config, Day, Kid } from '../../api/types'
import { copy } from '../../copy'
import { usePressGuard } from '../../usePressGuard'
import { kidVars } from '../../kidVars'
import { Sheet } from './ui'

/** The sizes a parent actually gives. Anything else is a conversation. */
const AMOUNTS = [5, 10, 15, 20]

/** And takes, where the house has said points can be taken at all. */
const DEDUCTIONS = [-5, -10]

/**
 * Points for something no task file lists: being kind to a brother, owning
 * up to something, getting through a hard afternoon. Or, only where
 * settings.points.deductions is on, points taken away — the chips for that
 * are not drawn at all otherwise, rather than drawn and refused.
 *
 * The note is required, because "15 points" six weeks later means nothing
 * without it. Today's tasks are offered as a starting point; the field is
 * free text, since the whole reason this exists is the things that are not.
 */
export default function AwardSheet({
  kids,
  onClose,
  onAwarded,
  title = copy.parent.award.title,
}: {
  kids: Kid[]
  onClose: () => void
  onAwarded: (said: string) => void
  title?: string
}) {
  const [kidId, setKidId] = useState(kids.length > 0 ? kids[0].id : '')
  const [points, setPoints] = useState(10)
  // One award per press: a bounced tap would give the points twice.
  const guard = usePressGuard()
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [titles, setTitles] = useState<Record<string, string[]>>({})
  const [deductions, setDeductions] = useState(false)
  const noteId = useId()

  useEffect(() => {
    let cancelled = false
    getJson<Day>('/api/today')
      .then((day) => {
        if (!cancelled) {
          setTitles(Object.fromEntries(day.kids.map((kid) => [kid.id, kid.tasks.map((t) => t.title)])))
        }
      })
      .catch(() => undefined)
    getJson<Config>('/api/config')
      .then((config) => {
        if (!cancelled) {
          setDeductions(config.settings.points?.deductions === true)
        }
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [])

  const give = () => {
    if (!kidId || !note.trim()) {
      return
    }
    setBusy(true)
    setError('')
    awardPoints(kidId, points, note.trim())
      .then((summary) => {
        const who = kids.find((kid) => kid.id === kidId)?.name ?? kidId
        onAwarded(copy.parent.award.said(points, who, summary.balance))
        onClose()
      })
      .catch((failure: Error) => setError(failure.message || copy.parent.approvals.failed))
      .finally(() => setBusy(false))
  }

  const amounts = deductions ? [...DEDUCTIONS, ...AMOUNTS] : AMOUNTS

  return (
    <Sheet title={title} onClose={onClose}>
      <div className="pp-chips" role="radiogroup" aria-label={copy.parent.award.who}>
        {kids.map((kid) => (
          <button
            key={kid.id}
            type="button"
            role="radio"
            aria-checked={kid.id === kidId}
            className={kid.id === kidId ? 'pp-chip pp-chip-on' : 'pp-chip'}
            style={kidVars(kid.id, kid.color)}
            onClick={() => setKidId(kid.id)}
          >
            {kid.name}
          </button>
        ))}
      </div>

      {(titles[kidId] ?? []).length > 0 ? (
        <div className="pp-chips">
          {(titles[kidId] ?? []).map((task) => (
            <button key={task} type="button" className="pp-chip" onClick={() => setNote(task)}>
              {task}
            </button>
          ))}
        </div>
      ) : null}

      <label className="pp-field" htmlFor={noteId}>
        <span className="pp-row-label">{copy.parent.award.forWhat}</span>
        <input
          id={noteId}
          className="pp-input"
          type="text"
          value={note}
          placeholder={copy.parent.award.placeholder}
          onChange={(event) => setNote(event.target.value)}
        />
      </label>

      <div className="pp-chips" role="radiogroup" aria-label={copy.parent.award.howMany}>
        {amounts.map((value) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={value === points}
            className={value === points ? 'pp-chip pp-chip-on' : 'pp-chip'}
            onClick={() => setPoints(value)}
          >
            {value > 0 ? `+${value}` : `−${Math.abs(value)}`}
          </button>
        ))}
      </div>

      {error ? <p className="pp-bad">{error}</p> : null}

      <div className="pp-sheet-actions">
        <button
          type="button"
          className="pp-button pp-button-accent"
          disabled={busy || !note.trim()}
          data-pressed={guard.pressed === 'give' ? 'yes' : undefined}
          onClick={() => guard.press('give', give)}
        >
          {points > 0 ? copy.parent.award.give : copy.parent.award.take}
        </button>
      </div>
    </Sheet>
  )
}
