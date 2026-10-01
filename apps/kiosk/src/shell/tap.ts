import type { Mode } from '../mode/machine'

/**
 * What a touch on the stage means. Pulled out of Shell so the rules can be
 * tested without a DOM: the corner counting, and which taps the shell keeps to
 * itself rather than letting through to the screen underneath.
 */

export const CORNER_PX = 80
export const TAP_WINDOW_MS = 1500
export const TAPS_TO_DIAG = 3

export type Point = { x: number; y: number }

export type TapPlan = {
  /** The corner taps still inside the window, for the next call. */
  taps: number[]
  /** Open diagnostics. */
  diag: boolean
  /** Swallow the event instead of passing it down. */
  consume: boolean
}

/** Where a kid's card was, the last time one was on screen. */
export type CardArea = { kid: string; left: number; top: number; right: number; bottom: number }

export type TapContext = {
  /** On NIGHT, a control that acts on the night screen itself (a feeling,
      the date): it gets the tap rather than waking the day. */
  live?: boolean
  /** Until when the screen that just woke hears nothing (the reducer's
      justWokeUntil). */
  deafUntil?: number
}

/**
 * Whether a tap wakes the screen: any tap on the frame, and any tap on the
 * night screen that is not on one of its own controls. The waking tap is
 * swallowed, whatever is under it on the screen it wakes.
 */
export function wakes(mode: Mode, live = false): boolean {
  return mode === 'FRAME' || (mode === 'NIGHT' && !live)
}

export function planTap(
  mode: Mode,
  point: Point | null,
  recent: readonly number[],
  now: number,
  { live = false, deafUntil = 0 }: TapContext = {},
): TapPlan {
  const inCorner = point !== null && point.x <= CORNER_PX && point.y <= CORNER_PX
  // The tap that wakes the frame or the night screen belongs to them, and so
  // does anything in the 600ms after: letting either through would land it
  // on whatever the day screen happens to have at that spot.
  const swallow = wakes(mode, live) || now < deafUntil
  if (inCorner) {
    const taps = recent.filter((tap) => now - tap < TAP_WINDOW_MS).concat(now)
    if (taps.length >= TAPS_TO_DIAG) {
      return { taps: [], diag: true, consume: true }
    }
    return { taps, diag: false, consume: swallow }
  }
  return { taps: [], diag: false, consume: swallow }
}
