/**
 * The kiosk's mode machine.
 *
 * A pure reducer: clocks, touches and visibility changes all arrive as events,
 * so every transition can be tested without timers or a DOM.
 */

export type Mode = 'DAY' | 'NIGHT' | 'FRAME' | 'PARENT' | 'MONTH' | 'LIST' | 'KID'

/** What FRAME and PARENT sit on top of, and what a tap returns to. */
export type Underlying = 'DAY' | 'NIGHT'

export type ModeSettings = {
  idleMinutes: number
  night: {
    start: string
    end: string
    idleMinutes: number
    frame: boolean
  }
}

export type ModeState = {
  mode: Mode
  underlying: Underlying
  lastTouch: number
  /** When FRAME started, used to gate the version reload. */
  frameSince: number | null
  /**
   * When someone tapped the night screen to look at the day. DAY over a NIGHT
   * underlying is exactly that peek, but the mode alone cannot tell it from
   * the 21:00 crossing, which must drop straight to NIGHT.
   */
  peekSince: number | null
  /**
   * True only on the state that replaces the photo frame. The frame giving
   * way to a dense dashboard in a single frame reads as a fault, so that one
   * transition is crossfaded; this is what tells the shell to play it.
   */
  waking: boolean
  /**
   * Whose card is open in KID mode, and nothing else's business. It is
   * cleared on every way out, so a stale name can never greet the next child
   * who walks up to the screen.
   */
  kid: string | null
  /**
   * Until when the screen that just woke ignores every touch. The tap that
   * woke it was aimed at the frame or the night screen, not at whatever DAY
   * happens to have under the same spot; the shell swallows it and anything
   * else that arrives before this.
   */
  justWokeUntil: number
  /**
   * When a peek at the day from the night screen ends, unless a tap moves it
   * on. Its own timer, much shorter than the night's idle minutes.
   */
  peekUntil: number | null
  /**
   * A correct kid code, and how long it lasts: two minutes from the latest
   * touch in that kid's screen. Done, the idle exit and the other kid's
   * screen all end it.
   */
  kidGrace: { kid: string; until: number } | null
}

export type ModeEvent =
  | { type: 'tick'; now: number }
  | { type: 'month-open'; now: number }
  | { type: 'month-close'; now: number }
  | { type: 'list-open'; now: number }
  | { type: 'list-close'; now: number }
  | { type: 'kid-open'; kid: string; now: number }
  | { type: 'kid-close'; now: number }
  | { type: 'kid-unlock'; kid: string; now: number }
  | { type: 'peek-end'; now: number }
  | { type: 'visible'; now: number }
  | { type: 'touch'; now: number }
  | { type: 'parent-open'; now: number }
  | { type: 'parent-close'; now: number }

const MINUTE = 60000

/** How long a woken screen ignores touches after the tap that woke it. */
export const WAKE_GUARD_MS = 600
/** How long a peek at the day from the night screen lasts without a tap. */
export const PEEK_MS = 60000
/** How long a kid's code holds, from their latest touch. */
export const KID_GRACE_MS = 2 * MINUTE

/** Whether this kid's code still holds at `now`. */
export function graceFor(state: ModeState, kid: string, now: number): boolean {
  return state.kidGrace !== null && state.kidGrace.kid === kid && state.kidGrace.until > now
}

/** The next moment the state changes on its own, for a timer finer than
    the 30s tick: a peek running out, or a kid's code. */
export function nextDeadline(state: ModeState): number | null {
  const times = [state.peekUntil, state.kidGrace?.until ?? null].filter(
    (time): time is number => time !== null,
  )
  return times.length > 0 ? Math.min(...times) : null
}

/** "21:00" as minutes past midnight; NaN for anything unparseable. */
export function toMinutes(clock: string): number {
  const [hours, minutes] = clock.split(':')
  const h = Number(hours)
  const m = Number(minutes)
  if (!Number.isFinite(h) || !Number.isFinite(m)) {
    return Number.NaN
  }
  return h * 60 + m
}

export function minutesOfDay(now: number): number {
  const when = new Date(now)
  return when.getHours() * 60 + when.getMinutes()
}

/** Night windows usually cross midnight, so the ends may be out of order. */
export function isNightAt(minutes: number, start: string, end: string): boolean {
  const from = toMinutes(start)
  const to = toMinutes(end)
  if (!Number.isFinite(from) || !Number.isFinite(to) || from === to) {
    return false
  }
  if (from < to) {
    return minutes >= from && minutes < to
  }
  return minutes >= from || minutes < to
}

export function underlyingAt(now: number, settings: ModeSettings): Underlying {
  return isNightAt(minutesOfDay(now), settings.night.start, settings.night.end) ? 'NIGHT' : 'DAY'
}

function frameAllowed(underlying: Underlying, settings: ModeSettings): boolean {
  return underlying === 'DAY' ? true : settings.night.frame
}

function idleMinutes(underlying: Underlying, settings: ModeSettings): number {
  return underlying === 'DAY' ? settings.idleMinutes : settings.night.idleMinutes
}

export function initialState(now: number, settings: ModeSettings): ModeState {
  const underlying = underlyingAt(now, settings)
  return {
    mode: underlying,
    underlying,
    lastTouch: now,
    frameSince: null,
    peekSince: null,
    waking: false,
    kid: null,
    justWokeUntil: 0,
    peekUntil: null,
    kidGrace: null,
  }
}

export function reduce(before: ModeState, event: ModeEvent, settings: ModeSettings): ModeState {
  let state = before
  switch (event.type) {
    case 'touch': {
      // A tap in FRAME only wakes the screen; elsewhere it just restarts idle.
      if (state.mode === 'FRAME') {
        // Waking from the frame onto the night screen is still the night:
        // only a wake onto the day starts a peek.
        const peek = state.underlying === 'NIGHT' ? null : state.peekUntil
        return {
          ...state,
          mode: state.underlying,
          lastTouch: event.now,
          frameSince: null,
          waking: true,
          justWokeUntil: event.now + WAKE_GUARD_MS,
          peekUntil: peek,
        }
      }
      // Reading the calendar is touching it: a tap restarts the idle timer
      // rather than closing, which Done and the timer do. In a kid's screen
      // it also keeps their code good for another two minutes.
      if (state.mode === 'MONTH' || state.mode === 'LIST' || state.mode === 'KID') {
        const kidGrace =
          state.mode === 'KID' && state.kid !== null && graceFor(state, state.kid, event.now)
            ? { kid: state.kid, until: event.now + KID_GRACE_MS }
            : state.kidGrace
        return { ...state, lastTouch: event.now, waking: false, kidGrace }
      }
      // A tap on the night screen opens the day, still in the night palette,
      // for a minute; see the tick below.
      if (state.mode === 'NIGHT') {
        return {
          ...state,
          mode: 'DAY',
          lastTouch: event.now,
          peekSince: event.now,
          peekUntil: event.now + PEEK_MS,
          waking: false,
          justWokeUntil: event.now + WAKE_GUARD_MS,
        }
      }
      // A tap during a peek keeps the day up for another minute.
      const peekUntil = state.peekUntil === null ? null : event.now + PEEK_MS
      return { ...state, lastTouch: event.now, waking: false, peekUntil }
    }

    case 'peek-end':
      // The clock, tapped during a peek: straight back to the night.
      if (state.mode !== 'DAY' || state.peekUntil === null) {
        return state
      }
      return { ...state, mode: 'NIGHT', lastTouch: event.now, peekSince: null, peekUntil: null }

    case 'kid-unlock':
      return { ...state, lastTouch: event.now, kidGrace: { kid: event.kid, until: event.now + KID_GRACE_MS } }

    case 'month-open':
      // An overlay on whatever is underneath: the calendar is read in the
      // day's light or the night's, and goes back to where it came from.
      return {
        ...state,
        mode: 'MONTH',
        lastTouch: event.now,
        frameSince: null,
        peekSince: null,
        peekUntil: null,
        waking: false,
        kid: null,
      }

    case 'kid-open':
      // The same overlay shape, opened on one child. Which child is carried
      // on the state rather than looked up, so the screen and the reducer can
      // never disagree about whose card is open.
      return {
        ...state,
        mode: 'KID',
        lastTouch: event.now,
        frameSince: null,
        peekSince: null,
        waking: false,
        kid: event.kid,
        peekUntil: null,
        // The other kid's screen ends this one's code.
        kidGrace: state.kidGrace?.kid === event.kid ? state.kidGrace : null,
      }

    case 'list-open':
      // The same overlay, a different shape of the same answer. Switching
      // between them is not going back to the day.
      return { ...state, mode: 'LIST', lastTouch: event.now, frameSince: null, peekSince: null,
        peekUntil: null, waking: false, kid: null }

    case 'list-close':
    case 'month-close':
    case 'kid-close':
      return {
        ...state,
        mode: state.underlying,
        lastTouch: event.now,
        frameSince: null,
        peekSince: null,
        peekUntil: null,
        kid: null,
        // Done in a kid's screen hands it back: the next child needs a code.
        kidGrace: event.type === 'kid-close' ? null : state.kidGrace,
      }

    case 'parent-open':
      return {
        ...state,
        mode: 'PARENT',
        lastTouch: event.now,
        frameSince: null,
        peekSince: null,
        peekUntil: null,
        waking: false,
        kid: null,
      }

    case 'parent-close':
      return {
        ...state,
        mode: state.underlying,
        lastTouch: event.now,
        frameSince: null,
        peekSince: null,
        peekUntil: null,
        kid: null,
      }

    case 'tick':
    case 'visible': {
      const underlying = underlyingAt(event.now, settings)
      // A kid's code runs out on its own; the screen asks for it again.
      if (state.kidGrace !== null && state.kidGrace.until <= event.now) {
        state = { ...state, kidGrace: null }
      }

      // Parent mode is only left deliberately, never on a timer.
      if (state.mode === 'PARENT') {
        return { ...state, underlying }
      }

      // The overlays close themselves after the idle period for wherever
      // they were opened from — the night's patience at night, the day's by
      // day.
      if (state.mode === 'MONTH' || state.mode === 'LIST' || state.mode === 'KID') {
        const idleFor = event.now - state.lastTouch
        if (idleFor >= idleMinutes(underlying, settings) * MINUTE) {
          return {
            ...state,
            mode: underlying,
            underlying,
            frameSince: null,
            peekSince: null,
            peekUntil: null,
            waking: false,
            kid: null,
            kidGrace: null,
          }
        }
        return { ...state, underlying }
      }

      if (state.mode === 'FRAME') {
        // Crossing into a night that forbids the frame drops straight to NIGHT.
        if (!frameAllowed(underlying, settings)) {
          return {
            ...state,
            mode: underlying,
            underlying,
            frameSince: null,
            peekSince: null,
            peekUntil: null,
            waking: true,
          }
        }
        return { ...state, underlying }
      }

      const idleFor = event.now - state.lastTouch
      const idle = idleFor >= idleMinutes(underlying, settings) * MINUTE

      if (frameAllowed(underlying, settings) && idle) {
        return {
          ...state,
          mode: 'FRAME',
          underlying,
          frameSince: event.now,
          peekSince: null,
          peekUntil: null,
          waking: false,
          kid: null,
        }
      }

      // A peek only survives while the night lasts and its minute has not
      // run out. Night ending, or night starting under it, both end it: the
      // screen that belongs to the hour wins.
      const peeking =
        state.peekUntil !== null &&
        event.now < state.peekUntil &&
        underlying === 'NIGHT' &&
        state.underlying === 'NIGHT'
      if (peeking) {
        return { ...state, mode: 'DAY', underlying, waking: false }
      }

      return {
        ...state,
        mode: underlying,
        underlying,
        frameSince: null,
        peekSince: null,
        peekUntil: null,
        waking: false,
        kid: null,
      }
    }
  }
}
