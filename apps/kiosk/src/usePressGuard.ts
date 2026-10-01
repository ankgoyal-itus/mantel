import { useCallback, useEffect, useRef, useState } from 'react'

/** A second press of a deciding button inside this is the same press. */
export const PRESS_GUARD_MS = 400

/**
 * One press per decision.
 *
 * Approve, Decline, Award and Paid each do something that cannot be done
 * twice — a second approval of the same claim, a second award — and a tap on
 * an old iPad is sometimes two. The first press acts and shows pressed; any
 * press in the next 400ms in the same group (a claim's Approve and Decline
 * are one group) is dropped. Another item's buttons are not held up.
 */
export function usePressGuard(ms: number = PRESS_GUARD_MS): {
  /** Which button is showing pressed, if any. */
  pressed: string | null
  press: (key: string, action: () => void, group?: string) => void
} {
  const last = useRef(new Map<string, number>())
  const timer = useRef<number | null>(null)
  const [pressed, setPressed] = useState<string | null>(null)

  useEffect(
    () => () => {
      if (timer.current !== null) {
        window.clearTimeout(timer.current)
      }
    },
    [],
  )

  const press = useCallback(
    (key: string, action: () => void, group: string = key) => {
      const now = Date.now()
      if (now - (last.current.get(group) ?? Number.NEGATIVE_INFINITY) < ms) {
        return
      }
      last.current.set(group, now)
      setPressed(key)
      if (timer.current !== null) {
        window.clearTimeout(timer.current)
      }
      timer.current = window.setTimeout(() => {
        timer.current = null
        setPressed(null)
      }, ms)
      action()
    },
    [ms],
  )

  return { pressed, press }
}
