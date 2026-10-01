import { describe, expect, it } from 'vitest'

import {
  KID_GRACE_MS,
  type ModeSettings,
  type ModeState,
  WAKE_GUARD_MS,
  graceFor,
  initialState,
  isNightAt,
  nextDeadline,
  reduce,
} from './machine'

const SETTINGS: ModeSettings = {
  idleMinutes: 3,
  night: { start: '21:00', end: '06:30', idleMinutes: 10, frame: false },
}

const nightFrame: ModeSettings = { ...SETTINGS, night: { ...SETTINGS.night, frame: true } }

/** Local wall-clock time on a Tuesday, which is what the machine reads. */
function at(hour: number, minute = 0, second = 0): number {
  return new Date(2026, 8, 29, hour, minute, second, 0).getTime()
}

function dayState(hour: number, minute = 0): ModeState {
  return initialState(at(hour, minute), SETTINGS)
}

describe('night window', () => {
  it('spans midnight', () => {
    const { start, end } = SETTINGS.night
    expect(isNightAt(22 * 60, start, end)).toBe(true)
    expect(isNightAt(3 * 60, start, end)).toBe(true)
    expect(isNightAt(6 * 60 + 29, start, end)).toBe(true)
    expect(isNightAt(6 * 60 + 30, start, end)).toBe(false) // end is exclusive
    expect(isNightAt(21 * 60, start, end)).toBe(true) // start is inclusive
    expect(isNightAt(20 * 60 + 59, start, end)).toBe(false)
  })

  it('treats an empty window as never night', () => {
    expect(isNightAt(12 * 60, '21:00', '21:00')).toBe(false)
    expect(isNightAt(12 * 60, 'nonsense', '06:30')).toBe(false)
  })
})

describe('day', () => {
  it('starts in DAY outside the night window', () => {
    expect(dayState(10).mode).toBe('DAY')
  })

  it('drops to FRAME after the idle minutes', () => {
    const state = dayState(10)
    expect(reduce(state, { type: 'tick', now: at(10, 2, 59) }, SETTINGS).mode).toBe('DAY')

    const framed = reduce(state, { type: 'tick', now: at(10, 3) }, SETTINGS)
    expect(framed.mode).toBe('FRAME')
    expect(framed.underlying).toBe('DAY')
    expect(framed.frameSince).toBe(at(10, 3))
  })

  it('returns from FRAME on a tap and restarts the idle timer', () => {
    const framed = reduce(dayState(10), { type: 'tick', now: at(10, 3) }, SETTINGS)

    const woken = reduce(framed, { type: 'touch', now: at(10, 4) }, SETTINGS)
    expect(woken.mode).toBe('DAY')
    expect(woken.lastTouch).toBe(at(10, 4))
    expect(woken.frameSince).toBeNull()

    // And the countdown starts again from that tap, not from before.
    expect(reduce(woken, { type: 'tick', now: at(10, 6, 59) }, SETTINGS).mode).toBe('DAY')
    expect(reduce(woken, { type: 'tick', now: at(10, 7) }, SETTINGS).mode).toBe('FRAME')
  })

  it('drops to NIGHT at night.start even with a hand on the screen', () => {
    // No reload, and no waiting out an idle timer: the hour owns the screen.
    const evening = reduce(dayState(20, 55), { type: 'touch', now: at(20, 59) }, SETTINGS)
    expect(evening.mode).toBe('DAY')

    const night = reduce(evening, { type: 'tick', now: at(21, 0) }, SETTINGS)
    expect(night.mode).toBe('NIGHT')
    expect(night.peekSince).toBeNull()
  })

  it('switches to NIGHT when the window opens', () => {
    const evening = reduce(dayState(20, 59), { type: 'tick', now: at(21, 0) }, SETTINGS)
    expect(evening.mode).toBe('NIGHT')
    expect(evening.underlying).toBe('NIGHT')
  })
})

describe('night', () => {
  const nightState = (settings: ModeSettings) => initialState(at(22), settings)

  it('stays on the night screen when frame is off, however long it idles', () => {
    const state = nightState(SETTINGS)
    expect(state.mode).toBe('NIGHT')
    expect(reduce(state, { type: 'tick', now: at(23, 30) }, SETTINGS).mode).toBe('NIGHT')
  })

  it('uses the night idle minutes when frame is on', () => {
    const state = nightState(nightFrame)
    expect(reduce(state, { type: 'tick', now: at(22, 3) }, nightFrame).mode).toBe('NIGHT')

    const framed = reduce(state, { type: 'tick', now: at(22, 10) }, nightFrame)
    expect(framed.mode).toBe('FRAME')
    expect(framed.underlying).toBe('NIGHT')
  })

  it('returns to NIGHT, not DAY, when tapped', () => {
    const framed = reduce(nightState(nightFrame), { type: 'tick', now: at(22, 10) }, nightFrame)
    expect(reduce(framed, { type: 'touch', now: at(22, 11) }, nightFrame).mode).toBe('NIGHT')
  })

  it('opens the day screen on a tap, still in the night theme', () => {
    const tapped = reduce(nightState(SETTINGS), { type: 'touch', now: at(22, 5) }, SETTINGS)
    expect(tapped.mode).toBe('DAY')
    // NIGHT underlying is what keeps the palette dim while the day is shown.
    expect(tapped.underlying).toBe('NIGHT')
    expect(tapped.peekSince).toBe(at(22, 5))
  })

  it('holds the day screen for a minute, on its own timer', () => {
    const tapped = reduce(nightState(SETTINGS), { type: 'touch', now: at(22, 5) }, SETTINGS)
    expect(tapped.peekUntil).toBe(at(22, 6))

    const soon = reduce(tapped, { type: 'tick', now: at(22, 5, 59) }, SETTINGS)
    expect(soon.mode).toBe('DAY')

    const later = reduce(soon, { type: 'tick', now: at(22, 6) }, SETTINGS)
    expect(later.mode).toBe('NIGHT')
    expect(later.peekUntil).toBeNull()
    expect(nextDeadline(tapped)).toBe(at(22, 6))
  })

  it('gives the peek another minute on a second tap', () => {
    const tapped = reduce(nightState(SETTINGS), { type: 'touch', now: at(22, 5) }, SETTINGS)
    const again = reduce(tapped, { type: 'touch', now: at(22, 5, 50) }, SETTINGS)
    expect(reduce(again, { type: 'tick', now: at(22, 6, 30) }, SETTINGS).mode).toBe('DAY')
    expect(reduce(again, { type: 'tick', now: at(22, 6, 50) }, SETTINGS).mode).toBe('NIGHT')
  })

  it('goes back to the night on a tap of the clock', () => {
    const tapped = reduce(nightState(SETTINGS), { type: 'touch', now: at(22, 5) }, SETTINGS)
    const back = reduce(tapped, { type: 'peek-end', now: at(22, 5, 10) }, SETTINGS)
    expect(back.mode).toBe('NIGHT')
    expect(back.peekUntil).toBeNull()
    // By day the clock is only a clock.
    const day = dayState(10)
    expect(reduce(day, { type: 'peek-end', now: at(10, 1) }, SETTINGS)).toBe(day)
  })

  it('goes to the frame instead, when the night allows one', () => {
    const tapped = reduce(nightState(nightFrame), { type: 'touch', now: at(22, 5) }, nightFrame)
    expect(tapped.mode).toBe('DAY')

    const framed = reduce(tapped, { type: 'tick', now: at(22, 16) }, nightFrame)
    expect(framed.mode).toBe('FRAME')
    expect(framed.peekSince).toBeNull()
  })

  it('ends the day screen when the night does', () => {
    const tapped = reduce(nightState(SETTINGS), { type: 'touch', now: at(23, 58) }, SETTINGS)
    const dawn = reduce(tapped, { type: 'tick', now: at(6, 31) }, SETTINGS)
    expect(dawn.mode).toBe('DAY')
    expect(dawn.underlying).toBe('DAY')
    expect(dawn.peekSince).toBeNull()
  })

  it('leaves a day frame when night forbids the frame', () => {
    const framed = reduce(dayState(20, 55), { type: 'tick', now: at(20, 58) }, SETTINGS)
    expect(framed.mode).toBe('FRAME')

    const night = reduce(framed, { type: 'tick', now: at(21, 0) }, SETTINGS)
    expect(night.mode).toBe('NIGHT')
    expect(night.frameSince).toBeNull()
  })
})

describe('waking from the frame', () => {
  it('is flagged once, on the state that replaces the frame', () => {
    const framed = reduce(dayState(10), { type: 'tick', now: at(10, 4) }, SETTINGS)
    expect(framed.mode).toBe('FRAME')
    expect(framed.waking).toBe(false)

    const woken = reduce(framed, { type: 'touch', now: at(10, 5) }, SETTINGS)
    expect(woken.mode).toBe('DAY')
    expect(woken.waking).toBe(true)

    // And not on the next thing that happens, so the fade plays once.
    expect(reduce(woken, { type: 'touch', now: at(10, 6) }, SETTINGS).waking).toBe(false)
    expect(reduce(woken, { type: 'tick', now: at(10, 6) }, SETTINGS).waking).toBe(false)
  })

  it('is flagged when the night closes the frame too', () => {
    const framed = reduce(dayState(20, 55), { type: 'tick', now: at(20, 58) }, SETTINGS)
    expect(framed.mode).toBe('FRAME')
    expect(reduce(framed, { type: 'tick', now: at(21, 0) }, SETTINGS).waking).toBe(true)
  })

  it('is not flagged by opening the month', () => {
    const open = reduce(dayState(10), { type: 'month-open', now: at(10, 1) }, SETTINGS)
    expect(open.waking).toBe(false)
  })
})

describe('the month overlay', () => {
  it('opens over the day and goes back to it', () => {
    const open = reduce(dayState(10), { type: 'month-open', now: at(10, 1) }, SETTINGS)
    expect(open.mode).toBe('MONTH')
    expect(open.underlying).toBe('DAY')

    const closed = reduce(open, { type: 'month-close', now: at(10, 5) }, SETTINGS)
    expect(closed.mode).toBe('DAY')
  })

  it('opens over the night and goes back to it', () => {
    const night = initialState(at(22), SETTINGS)
    const open = reduce(night, { type: 'month-open', now: at(22, 1) }, SETTINGS)
    expect(open.mode).toBe('MONTH')
    expect(open.underlying).toBe('NIGHT')

    const closed = reduce(open, { type: 'month-close', now: at(22, 5) }, SETTINGS)
    expect(closed.mode).toBe('NIGHT')
  })

  it('closes itself after the day idle period', () => {
    const open = reduce(dayState(10), { type: 'month-open', now: at(10, 1) }, SETTINGS)
    expect(reduce(open, { type: 'tick', now: at(10, 3) }, SETTINGS).mode).toBe('MONTH')
    expect(reduce(open, { type: 'tick', now: at(10, 5) }, SETTINGS).mode).toBe('DAY')
  })

  it('is given the night\u2019s patience at night', () => {
    const open = reduce(initialState(at(22), SETTINGS), { type: 'month-open', now: at(22, 1) }, SETTINGS)
    // Three minutes would have closed it by day; the night allows ten.
    expect(reduce(open, { type: 'tick', now: at(22, 5) }, SETTINGS).mode).toBe('MONTH')
    expect(reduce(open, { type: 'tick', now: at(22, 12) }, SETTINGS).mode).toBe('NIGHT')
  })

  it('stays open while it is being read', () => {
    const open = reduce(dayState(10), { type: 'month-open', now: at(10, 1) }, SETTINGS)
    const tapped = reduce(open, { type: 'touch', now: at(10, 4) }, SETTINGS)
    expect(tapped.mode).toBe('MONTH')
    expect(reduce(tapped, { type: 'tick', now: at(10, 6) }, SETTINGS).mode).toBe('MONTH')
  })

  it('never drops into the photo frame', () => {
    const open = reduce(dayState(10), { type: 'month-open', now: at(10, 1) }, nightFrame)
    expect(reduce(open, { type: 'tick', now: at(10, 30) }, nightFrame).mode).toBe('DAY')
  })
})

describe('the list overlay', () => {
  it('opens over the day and goes back to it', () => {
    const open = reduce(dayState(10), { type: 'list-open', now: at(10, 1) }, SETTINGS)
    expect(open.mode).toBe('LIST')
    expect(open.underlying).toBe('DAY')
    expect(reduce(open, { type: 'list-close', now: at(10, 2) }, SETTINGS).mode).toBe('DAY')
  })

  it('opens over the night and goes back to it', () => {
    const night = initialState(at(22), SETTINGS)
    const open = reduce(night, { type: 'list-open', now: at(22, 1) }, SETTINGS)
    expect(open.underlying).toBe('NIGHT')
    expect(reduce(open, { type: 'list-close', now: at(22, 2) }, SETTINGS).mode).toBe('NIGHT')
  })

  it('swaps with the month without going back to the day', () => {
    // They are two shapes of the same answer, not two trips out.
    const month = reduce(dayState(10), { type: 'month-open', now: at(10, 1) }, SETTINGS)
    const list = reduce(month, { type: 'list-open', now: at(10, 2) }, SETTINGS)
    expect(list.mode).toBe('LIST')

    const back = reduce(list, { type: 'month-open', now: at(10, 3) }, SETTINGS)
    expect(back.mode).toBe('MONTH')
    expect(back.underlying).toBe('DAY')
  })

  it('closes itself after the idle period', () => {
    const open = reduce(dayState(10), { type: 'list-open', now: at(10, 1) }, SETTINGS)
    expect(reduce(open, { type: 'tick', now: at(10, 3) }, SETTINGS).mode).toBe('LIST')
    expect(reduce(open, { type: 'tick', now: at(10, 5) }, SETTINGS).mode).toBe('DAY')
  })

  it('stays open while it is being read', () => {
    const open = reduce(dayState(10), { type: 'list-open', now: at(10, 1) }, SETTINGS)
    const scrolled = reduce(open, { type: 'touch', now: at(10, 4) }, SETTINGS)
    expect(reduce(scrolled, { type: 'tick', now: at(10, 6) }, SETTINGS).mode).toBe('LIST')
  })
})

describe('visibility and parent', () => {
  it('re-evaluates the window when the tab becomes visible', () => {
    const stale = dayState(20, 59)
    expect(reduce(stale, { type: 'visible', now: at(21, 30) }, SETTINGS).mode).toBe('NIGHT')
  })

  it('holds PARENT until it is closed', () => {
    const parent = reduce(dayState(10), { type: 'parent-open', now: at(10, 1) }, SETTINGS)
    expect(parent.mode).toBe('PARENT')

    // Idling in parent mode must not steal the screen away mid-edit.
    expect(reduce(parent, { type: 'tick', now: at(10, 30) }, SETTINGS).mode).toBe('PARENT')

    const closed = reduce(parent, { type: 'parent-close', now: at(10, 31) }, SETTINGS)
    expect(closed.mode).toBe('DAY')
  })
})

describe('a kid card', () => {
  it('opens on the kid it was asked for', () => {
    const open = reduce(dayState(15), { type: 'kid-open', kid: 'mira', now: at(15) }, SETTINGS)
    expect(open.mode).toBe('KID')
    expect(open.kid).toBe('mira')
  })

  it('goes back to the day when Done is tapped', () => {
    const open = reduce(dayState(15), { type: 'kid-open', kid: 'mira', now: at(15) }, SETTINGS)
    const done = reduce(open, { type: 'kid-close', now: at(15, 1) }, SETTINGS)
    expect(done.mode).toBe('DAY')
    expect(done.kid).toBeNull()
  })

  it('closes itself after the idle period', () => {
    const open = reduce(dayState(15), { type: 'kid-open', kid: 'kabir', now: at(15) }, SETTINGS)
    const waiting = reduce(open, { type: 'tick', now: at(15, 2) }, SETTINGS)
    expect(waiting.mode).toBe('KID')

    const gone = reduce(open, { type: 'tick', now: at(15, 3) }, SETTINGS)
    expect(gone.mode).toBe('DAY')
    expect(gone.kid).toBeNull()
  })

  it('is not dropped by the data that arrives under it', () => {
    // A kid card seemed to close itself once. It was a stray tap, and this
    // is the proof: /api/today lands every minute or so, and the mode has to
    // survive it — otherwise a child loses their card to the clock rather
    // than to anything they did.
    //
    // The reducer is the whole guarantee. Every event it takes is a clock, a
    // touch or a screen being asked for; a fetch landing is none of those, so
    // there is no event for it to send and no branch it can reach. This
    // fails the day one is added.
    const open = reduce(dayState(15), { type: 'kid-open', kid: 'mira', now: at(15) }, SETTINGS)

    // Two and a half minutes of polling, under the three-minute idle.
    let state = open
    for (const second of [15, 30, 45, 60, 90, 120, 150]) {
      state = reduce(state, { type: 'tick', now: at(15, 0, second) }, SETTINGS)
      expect(state.mode).toBe('KID')
      expect(state.kid).toBe('mira')
    }

    // And a refetch on the tab coming back does not take the card either.
    const back = reduce(state, { type: 'visible', now: at(15, 2, 50) }, SETTINGS)
    expect(back.mode).toBe('KID')
    expect(back.kid).toBe('mira')
  })

  it('treats reading it as touching it', () => {
    const open = reduce(dayState(15), { type: 'kid-open', kid: 'mira', now: at(15) }, SETTINGS)
    const tapped = reduce(open, { type: 'touch', now: at(15, 2) }, SETTINGS)
    expect(tapped.mode).toBe('KID')
    expect(tapped.kid).toBe('mira')

    // And the idle timer restarted, so it survives past the original three.
    expect(reduce(tapped, { type: 'tick', now: at(15, 4) }, SETTINGS).mode).toBe('KID')
  })

  it('never leaves a name behind on the way out', () => {
    const open = reduce(dayState(15), { type: 'kid-open', kid: 'mira', now: at(15) }, SETTINGS)
    for (const next of [
      reduce(open, { type: 'month-open', now: at(15, 1) }, SETTINGS),
      reduce(open, { type: 'list-open', now: at(15, 1) }, SETTINGS),
      reduce(open, { type: 'parent-open', now: at(15, 1) }, SETTINGS),
      reduce(open, { type: 'parent-close', now: at(15, 1) }, SETTINGS),
      reduce(open, { type: 'tick', now: at(22) }, SETTINGS),
    ]) {
      expect(next.kid).toBeNull()
    }
  })

  it('does not survive the night falling', () => {
    const open = reduce(dayState(20, 50), { type: 'kid-open', kid: 'mira', now: at(20, 50) }, SETTINGS)
    const night = reduce(open, { type: 'tick', now: at(21, 5) }, SETTINGS)
    expect(night.mode).toBe('NIGHT')
    expect(night.kid).toBeNull()
  })
})

describe('a data poll', () => {
  it('never changes the mode, whichever screen is up', () => {
    // A poll lands /api/config, /api/today and the rest. The only thing it
    // can send the machine is what useMode sends when settings arrive: a tick
    // at the same moment, with a settings object that is new but equal. From
    // every screen, that must leave the screen where it is.
    const now = at(15)
    const day = dayState(15)
    const frame = reduce(day, { type: 'tick', now: at(15, 3) }, SETTINGS)
    const states: ModeState[] = [
      day,
      reduce(day, { type: 'month-open', now }, SETTINGS),
      reduce(day, { type: 'list-open', now }, SETTINGS),
      reduce(day, { type: 'kid-open', kid: 'kabir', now }, SETTINGS),
      reduce(day, { type: 'parent-open', now }, SETTINGS),
      frame,
      initialState(at(22), SETTINGS),
    ]
    expect(states.map((state) => state.mode)).toEqual([
      'DAY',
      'MONTH',
      'LIST',
      'KID',
      'PARENT',
      'FRAME',
      'NIGHT',
    ])

    for (const state of states) {
      const polled = structuredClone(SETTINGS)
      const moment = state.mode === 'FRAME' ? at(15, 3) : state.mode === 'NIGHT' ? at(22) : now
      const after = reduce(state, { type: 'tick', now: moment }, polled)
      expect(after.mode, state.mode).toBe(state.mode)
      expect(after.kid, state.mode).toBe(state.kid)
    }
  })
})

describe('idle, with the live stream running', () => {
  // A version bump every ten seconds is a refetch every ten seconds, and a
  // refetch sends the machine nothing at all — only the tick useMode sends
  // when anything re-renders. So: a tick every ten seconds, and the frame
  // must still arrive at idle_minutes and not a second later.
  function run(state: ModeState, from: number, seconds: number, settings: ModeSettings) {
    let now = state
    for (let second = 10; second <= seconds; second += 10) {
      now = reduce(now, { type: 'tick', now: from + second * 1000 }, settings)
    }
    return now
  }

  it('reaches FRAME from DAY after idle_minutes exactly', () => {
    const start = dayState(15)
    expect(run(start, at(15), 170, SETTINGS).mode).toBe('DAY')
    expect(run(start, at(15), 180, SETTINGS).mode).toBe('FRAME')
  })

  it('reaches FRAME from NIGHT after night.idle_minutes when the frame is on', () => {
    const start = initialState(at(22), nightFrame)
    expect(start.mode).toBe('NIGHT')
    expect(run(start, at(22), 590, nightFrame).mode).toBe('NIGHT')
    expect(run(start, at(22), 600, nightFrame).mode).toBe('FRAME')
  })
})

describe('the tap that wakes the screen', () => {
  it('holds DAY deaf for 600ms after waking from the frame', () => {
    const framed = reduce(dayState(10), { type: 'tick', now: at(10, 3) }, SETTINGS)
    const woken = reduce(framed, { type: 'touch', now: at(10, 4) }, SETTINGS)
    expect(woken.mode).toBe('DAY')
    expect(woken.justWokeUntil).toBe(at(10, 4) + WAKE_GUARD_MS)
  })

  it('and after waking from the night screen', () => {
    const night = initialState(at(22), SETTINGS)
    const woken = reduce(night, { type: 'touch', now: at(22, 1) }, SETTINGS)
    expect(woken.mode).toBe('DAY')
    expect(woken.justWokeUntil).toBe(at(22, 1) + WAKE_GUARD_MS)
  })

  it('but not on an ordinary tap on the day', () => {
    const tapped = reduce(dayState(10), { type: 'touch', now: at(10, 1) }, SETTINGS)
    expect(tapped.justWokeUntil).toBe(0)
  })
})

describe("a kid's code", () => {
  const open = (now: number) => {
    const opened = reduce(dayState(10), { type: 'kid-open', kid: 'mira', now }, SETTINGS)
    return reduce(opened, { type: 'kid-unlock', kid: 'mira', now }, SETTINGS)
  }

  it('holds for two minutes', () => {
    const state = open(at(10, 0))
    expect(graceFor(state, 'mira', at(10, 1, 59))).toBe(true)
    expect(graceFor(state, 'mira', at(10, 0) + KID_GRACE_MS)).toBe(false)
    expect(graceFor(state, 'kabir', at(10, 1))).toBe(false)
    // And runs out on its own, between ticks.
    expect(nextDeadline(state)).toBe(at(10, 2))
    expect(reduce(state, { type: 'tick', now: at(10, 2) }, SETTINGS).kidGrace).toBeNull()
  })

  it('each tap in their screen extends it', () => {
    const tapped = reduce(open(at(10, 0)), { type: 'touch', now: at(10, 1, 30) }, SETTINGS)
    expect(graceFor(tapped, 'mira', at(10, 3, 20))).toBe(true)
  })

  it('ends on Done, on the idle exit, and on the other kid', () => {
    const state = open(at(10, 0))
    expect(reduce(state, { type: 'kid-close', now: at(10, 1) }, SETTINGS).kidGrace).toBeNull()
    expect(reduce(state, { type: 'tick', now: at(10, 3) }, SETTINGS).kidGrace).toBeNull()
    const other = reduce(state, { type: 'kid-open', kid: 'kabir', now: at(10, 1) }, SETTINGS)
    expect(other.kidGrace).toBeNull()
    // Opening the same kid again keeps it.
    const same = reduce(state, { type: 'kid-open', kid: 'mira', now: at(10, 1) }, SETTINGS)
    expect(graceFor(same, 'mira', at(10, 1))).toBe(true)
  })
})
