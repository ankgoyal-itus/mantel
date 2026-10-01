import { useEffect, useRef } from 'react'

import type { ModeState } from '../mode/machine'

const CHECK_MS = 30000
const FRAME_SETTLE_MS = 60000

function nextReloadAt(now: number, clock: string): number {
  const [hours, minutes] = clock.split(':').map(Number)
  const target = new Date(now)
  if (Number.isFinite(hours) && Number.isFinite(minutes)) {
    target.setHours(hours, minutes, 0, 0)
  } else {
    target.setHours(4, 0, 0, 0)
  }
  if (target.getTime() <= now) {
    target.setDate(target.getDate() + 1)
  }
  return target.getTime()
}

/** Reloads once a day so a new build is picked up overnight. */
export function useDailyReload(dailyReload: string): void {
  useEffect(() => {
    let due = nextReloadAt(Date.now(), dailyReload)
    const timer = window.setInterval(() => {
      if (Date.now() >= due) {
        due = nextReloadAt(Date.now(), dailyReload)
        window.location.reload()
      }
    }, CHECK_MS)
    return () => window.clearInterval(timer)
  }, [dailyReload])
}

/**
 * Reloads when the API reports a version we did not load with — but only from
 * the photo frame, and only after a minute there, so nobody watches the screen
 * blink mid-sentence.
 */
export function useVersionReload(version: string | null, state: ModeState): void {
  const loadedRef = useRef<string | null>(null)

  useEffect(() => {
    if (version && loadedRef.current === null) {
      loadedRef.current = version
    }
  }, [version])

  const frameSince = state.frameSince
  const mode = state.mode

  useEffect(() => {
    const loaded = loadedRef.current
    if (!version || loaded === null || version === loaded) {
      return
    }
    if (mode !== 'FRAME' || frameSince === null) {
      return
    }

    const check = () => {
      if (Date.now() - frameSince >= FRAME_SETTLE_MS) {
        window.location.reload()
      }
    }
    check()
    const timer = window.setInterval(check, 10000)
    return () => window.clearInterval(timer)
  }, [version, mode, frameSince])
}

/**
 * "Reload both iPads", from the parent screen's About section.
 *
 * The API holds a stamp; each iPad remembers the one it started with and
 * reloads when it sees a different one. Not while a parent is in parent mode
 * on this iPad — that is usually the parent who pressed it, mid-sentence —
 * but the moment they close it.
 */
export function useReloadFlag(reloadAt: string | null | undefined, mode: string): void {
  const firstRef = useRef<string | null | undefined>(undefined)

  useEffect(() => {
    // The first answer from the API is the baseline, whatever it is,
    // including none. Undefined is "not asked yet", which is not an answer:
    // taking it as one would reload on every boot after any reload request.
    if (firstRef.current === undefined && reloadAt !== undefined) {
      firstRef.current = reloadAt
      return
    }
    if (reloadAt && reloadAt !== firstRef.current && mode !== 'PARENT') {
      window.location.reload()
    }
  }, [reloadAt, mode])
}
