import { type ReactNode, useEffect, useId, useRef, useState } from 'react'

import Icon from '../../components/icons/Icon'
import { copy } from '../../copy'

/**
 * The parent screen's handful of parts.
 *
 * A settings app is rows: a label on the left, the control on the right, in
 * cards on the page. Every control here is a real one — a button, a switch,
 * an input — at least 44px, and labelled, because this is the screen a
 * parent uses with one hand while holding a child's plate in the other.
 */

/** A section: its title, one line saying what it is for, and its cards. */
export function Pane({
  title,
  description,
  action,
  children,
}: {
  title: string
  description?: string
  /** A button beside the title, such as Award. */
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="pp-pane-body" aria-label={title}>
      <header className="pp-pane-head">
        <div className="pp-pane-titles">
          <h1 className="pp-title">{title}</h1>
          {description ? <p className="pp-description">{description}</p> : null}
        </div>
        {action ? <div className="pp-pane-action">{action}</div> : null}
      </header>
      {children}
    </section>
  )
}

export function Card({
  title,
  children,
  className,
}: {
  title?: string
  children: ReactNode
  className?: string
}) {
  return (
    <section className={className ? `pp-card ${className}` : 'pp-card'}>
      {title ? <h2 className="pp-card-title">{title}</h2> : null}
      {children}
    </section>
  )
}

/** A label on the left, the control right-aligned. */
export function Row({
  label,
  note,
  children,
  htmlFor,
}: {
  label: ReactNode
  note?: ReactNode
  children?: ReactNode
  /** The input this row labels, when the control is one. */
  htmlFor?: string
}) {
  return (
    <div className="pp-row">
      <div className="pp-row-text">
        {htmlFor ? (
          <label className="pp-row-label" htmlFor={htmlFor}>
            {label}
          </label>
        ) : (
          <span className="pp-row-label">{label}</span>
        )}
        {note ? <span className="pp-row-note">{note}</span> : null}
      </div>
      {children ? <div className="pp-row-control">{children}</div> : null}
    </div>
  )
}

/** On or off, and says which. A switch, not a checkbox: it saves as it flips. */
export function Toggle({
  label,
  checked,
  onChange,
  disabled = false,
}: {
  label: string
  checked: boolean
  onChange: (next: boolean) => void
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      className={checked ? 'pp-switch pp-switch-on' : 'pp-switch'}
      disabled={disabled}
      onClick={() => onChange(!checked)}
    >
      <span className="pp-switch-knob" aria-hidden="true" />
    </button>
  )
}

/** How long a run of taps on a stepper waits before it saves. */
const STEPPER_SETTLE_MS = 700

/**
 * A number, one step at a time.
 *
 * Taps change the number at once and save once they stop, so five taps are
 * one write rather than five racing each other to the file.
 */
export function Stepper({
  label,
  value,
  min,
  max,
  step = 1,
  unit,
  format,
  settle = STEPPER_SETTLE_MS,
  onCommit,
}: {
  label: string
  value: number
  min: number
  max: number
  step?: number
  unit?: string
  /** How the number is said, when a trailing unit will not do ("$15"). */
  format?: (value: number) => string
  /** How long to wait for more taps before committing. Zero where the
      number feeds a button rather than a save, so the button never acts on
      the number before last. */
  settle?: number
  onCommit: (next: number) => void
}) {
  const [draft, setDraft] = useState(value)
  const [seen, setSeen] = useState(value)
  const timer = useRef<number | null>(null)

  // A saved value (or a refused one, rolled back) replaces the draft.
  if (seen !== value) {
    setSeen(value)
    setDraft(value)
  }

  useEffect(
    () => () => {
      if (timer.current !== null) {
        window.clearTimeout(timer.current)
      }
    },
    [],
  )

  const nudge = (by: number) => {
    const next = Math.min(max, Math.max(min, draft + by))
    setDraft(next)
    if (timer.current !== null) {
      window.clearTimeout(timer.current)
    }
    timer.current = window.setTimeout(() => {
      timer.current = null
      if (next !== value) {
        onCommit(next)
      }
    }, settle)
  }

  return (
    <div className="pp-stepper" role="group" aria-label={label}>
      <button
        type="button"
        className="pp-step"
        aria-label={copy.parent.ui.less(label)}
        disabled={draft <= min}
        onClick={() => nudge(-step)}
      >
        <Icon name="minus" size={20} />
      </button>
      <output className="pp-step-value" aria-live="polite">
        {format ? format(draft) : unit ? `${draft} ${unit}` : draft}
      </output>
      <button
        type="button"
        className="pp-step"
        aria-label={copy.parent.ui.more(label)}
        disabled={draft >= max}
        onClick={() => nudge(step)}
      >
        <Icon name="plus" size={20} />
      </button>
    </div>
  )
}

/** A clock time, saved when the picker closes. */
export function TimeField({
  label,
  value,
  onCommit,
}: {
  label: string
  value: string
  onCommit: (next: string) => void
}) {
  const id = useId()
  const [draft, setDraft] = useState(value)
  const [seen, setSeen] = useState(value)
  if (seen !== value) {
    setSeen(value)
    setDraft(value)
  }
  return (
    <Row label={label} htmlFor={id}>
      <input
        id={id}
        className="pp-input pp-input-time"
        type="time"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={() => {
          if (draft && draft !== value) {
            onCommit(draft)
          }
        }}
      />
    </Row>
  )
}

/**
 * A panel over the screen, for the one thing being done: a cell of the week,
 * a photo, an award. Closed by its own button or by tapping outside it.
 */
export function Sheet({
  title,
  onClose,
  children,
}: {
  title: string
  onClose: () => void
  children: ReactNode
}) {
  const id = useId()
  return (
    <div className="pp-scrim" onClick={onClose}>
      <div
        className="pp-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby={id}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="pp-sheet-head">
          <h2 className="pp-sheet-title" id={id}>
            {title}
          </h2>
          <button
            type="button"
            className="pp-icon-button"
            aria-label={copy.parent.ui.close}
            onClick={onClose}
          >
            <Icon name="close" size={22} />
          </button>
        </header>
        <div className="pp-sheet-body">{children}</div>
      </div>
    </div>
  )
}

/** How long "Saved" stays up. */
export const TOAST_MS = 1500

/** One line, bottom of the pane, gone after a moment. A failure stays until
    the next thing is said, because it has to be read. */
export function Toast({ text, bad = false }: { text: string; bad?: boolean }) {
  if (!text) {
    return null
  }
  return (
    <div className={bad ? 'pp-toast pp-toast-bad' : 'pp-toast'} role="status">
      {bad ? null : <Icon name="check" size={20} />}
      <span>{text}</span>
    </div>
  )
}
