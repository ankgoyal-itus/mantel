import { type CSSProperties, type ReactNode, useCallback, useEffect, useRef, useState } from 'react'

import { copy } from '../copy'

const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9']

/** Codes are four digits: four dots to fill, and the fourth submits. */
export const CODE_LENGTH = 4

/** How long a pad takes to fade into the screen behind it once it opens. */
export const LEAVE_MS = 200

/** What a submitted code comes back as. */
export type KeypadResult =
  | { ok: true }
  | { ok: false; message: string; lockedFor?: number }

/**
 * The one keypad, for a parent's PIN and a kid's code alike.
 *
 * The parent pad's card over the screen that asked for it: a title line, a
 * caption, four dots, the digits in a 3×4 grid of 64px keys, Open across the
 * card and Cancel under it as a word. The fourth digit submits on its own —
 * nobody should have to find a second button — and Open stays for anyone
 * who looks for it. A wrong code shakes the dots once and says so; it never
 * turns red, because the kids get this wrong while playing. A right one
 * fades the pad into the screen behind it.
 *
 * The two variants differ only in whose they are: a parent's is the lock and
 * the accent, a kid's is their face and name and their colour.
 */
export default function Keypad({
  variant,
  title,
  caption,
  submit,
  onOpen,
  onCancel,
  note = null,
  style,
}: {
  variant: 'parent' | 'kid'
  /** The title line: the lock and "Parents only", or a kid's face and name. */
  title: ReactNode
  caption: string
  /** Checks a code. The pad clears, shakes and says why on a refusal. */
  submit: (code: string) => Promise<KeypadResult>
  onOpen: () => void
  onCancel: () => void
  /** A line under the dots: the parent pad's "3 waiting". */
  note?: ReactNode
  /** The kid's colour, published on the pad for its dots and button. */
  style?: CSSProperties
}) {
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [shake, setShake] = useState(0)
  const [waiting, setWaiting] = useState(false)
  const [lockedFor, setLockedFor] = useState(0)
  const [leaving, setLeaving] = useState(false)
  // A digit typed while the fourth is being checked is not the start of the
  // next code: it is the same impatient finger.
  const busy = useRef(false)
  // The code as typed so far, read by the handlers without waiting for a
  // render: two digits in one frame must both land.
  const typed = useRef('')
  const enter = useCallback((next: string) => {
    typed.current = next
    setCode(next)
  }, [])

  useEffect(() => {
    if (lockedFor <= 0) {
      return
    }
    const timer = window.setInterval(() => setLockedFor((left) => Math.max(0, left - 1)), 1000)
    return () => window.clearInterval(timer)
  }, [lockedFor])

  const check = useCallback(
    (entered: string) => {
      if (busy.current || lockedFor > 0 || entered.length === 0) {
        return
      }
      busy.current = true
      setWaiting(true)
      void submit(entered)
        .catch((): KeypadResult => ({ ok: false, message: copy.keypad.tryAgain }))
        .then((result) => {
          busy.current = false
          setWaiting(false)
          enter('')
          if (result.ok) {
            setLeaving(true)
            window.setTimeout(onOpen, LEAVE_MS)
            return
          }
          setError(result.message)
          setShake((count) => count + 1)
          if (result.lockedFor) {
            setLockedFor(result.lockedFor)
          }
        })
    },
    [enter, lockedFor, onOpen, submit],
  )

  const press = useCallback(
    (key: string) => {
      if (busy.current || leaving || lockedFor > 0) {
        return
      }
      if (typed.current.length >= CODE_LENGTH) {
        return
      }
      setError('')
      const next = typed.current + key
      enter(next)
      // The fourth digit is the submit.
      if (next.length === CODE_LENGTH) {
        check(next)
      }
    },
    [check, enter, leaving, lockedFor],
  )

  const back = useCallback(() => {
    setError('')
    enter(typed.current.slice(0, -1))
  }, [enter])

  // A laptop has a keyboard, and a parent sitting at one should not have to
  // aim a mouse at ten buttons. The pad is the only thing on screen, so
  // listening on the window costs nothing and steals nothing.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey) {
        return
      }
      if (/^[0-9]$/.test(event.key)) {
        event.preventDefault()
        press(event.key)
      } else if (event.key === 'Backspace') {
        event.preventDefault()
        back()
      } else if (event.key === 'Enter') {
        event.preventDefault()
        check(typed.current)
      } else if (event.key === 'Escape') {
        event.preventDefault()
        onCancel()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [back, check, onCancel, press])

  return (
    <div
      className={['pin', 'keypad', `keypad-${variant}`, leaving ? 'keypad-leaving' : '']
        .filter(Boolean)
        .join(' ')}
      style={style}
    >
      <div className="pin-card">
        <h1 className="pin-title">{title}</h1>
        <p className="pin-prompt">{caption}</p>
        <CodeDots entered={code.length} shake={shake} />
        {error ? <p className="pin-error">{error}</p> : null}
        {note}

        {/* Digits only in the grid. Cancel and Open are words, and a word in
            a 64px tile either spills out of it or gets cut to "Ca…". They get
            rows of their own. */}
        <div className="pin-keys">
          {KEYS.map((key) => (
            <button key={key} type="button" className="pin-key" onClick={() => press(key)}>
              {key}
            </button>
          ))}
          <span className="pin-blank" aria-hidden="true" />
          <button type="button" className="pin-key" onClick={() => press('0')}>
            0
          </button>
          <button
            type="button"
            className="pin-key pin-key-back"
            aria-label={copy.parent.backspace}
            onClick={back}
          >
            ←
          </button>
        </div>

        {/* Open across the card, in the accent or the kid's colour. The
            fourth digit has usually opened the pad before a finger gets here;
            it is live from the first digit for a shorter code. */}
        <button
          type="button"
          className="pin-go"
          onClick={() => check(code)}
          disabled={waiting || lockedFor > 0 || code.length === 0}
        >
          {lockedFor > 0 ? copy.parent.wait(lockedFor) : copy.keypad.open}
        </button>
        <button type="button" className="pin-text" onClick={onCancel}>
          {copy.parent.cancel}
        </button>
      </div>
    </div>
  )
}

/**
 * Four 12px dots that fill as digits land. A wrong code shakes them once —
 * the dots, not the card, since the dots are what was wrong.
 */
export function CodeDots({ entered, shake }: { entered: number; shake: number }) {
  return (
    <div
      key={shake}
      className="pin-dots"
      role="img"
      aria-label={copy.parent.digitsEntered(entered)}
      data-shake={shake > 0 ? 'yes' : undefined}
    >
      {Array.from({ length: CODE_LENGTH }, (_, index) => (
        <span key={index} className={index < entered ? 'pin-dot pin-dot-on' : 'pin-dot'} />
      ))}
    </div>
  )
}
