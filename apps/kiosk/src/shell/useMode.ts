import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import type { Settings } from '../api/types'
import {
  type ModeEvent,
  type ModeSettings,
  type ModeState,
  initialState,
  nextDeadline,
  reduce,
} from '../mode/machine'

const TICK_MS = 30000

/** Used for the second or two before /api/config arrives. */
export const DEFAULT_MODE_SETTINGS: ModeSettings = {
  idleMinutes: 3,
  night: { start: '21:00', end: '06:30', idleMinutes: 10, frame: false },
}

export function toModeSettings(settings: Settings | null): ModeSettings {
  if (!settings) {
    return DEFAULT_MODE_SETTINGS
  }
  return {
    idleMinutes: settings.idle_minutes,
    night: {
      start: settings.night.start,
      end: settings.night.end,
      idleMinutes: settings.night.idle_minutes,
      frame: settings.night.frame,
    },
  }
}

export type ModeMachine = {
  state: ModeState
  dispatch: (event: ModeEvent) => void
}

/** Drives the pure reducer from the clock, visibility changes and taps. */
export function useMode(settings: Settings | null): ModeMachine {
  const modeSettings = useMemo(() => toModeSettings(settings), [settings])
  const settingsRef = useRef(modeSettings)
  useEffect(() => {
    settingsRef.current = modeSettings
  }, [modeSettings])

  const [state, setState] = useState<ModeState>(() => initialState(Date.now(), modeSettings))

  const dispatch = useCallback((event: ModeEvent) => {
    setState((previous) => reduce(previous, event, settingsRef.current))
  }, [])

  useEffect(() => {
    const tick = () => dispatch({ type: 'tick', now: Date.now() })
    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        dispatch({ type: 'visible', now: Date.now() })
      }
    }

    tick() // new settings may change the answer immediately
    const timer = window.setInterval(tick, TICK_MS)
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [dispatch, modeSettings])

  // A peek's minute and a kid's two minutes end between ticks: one timer,
  // set for whichever comes first.
  const deadline = nextDeadline(state)
  useEffect(() => {
    if (deadline === null) {
      return
    }
    const timer = window.setTimeout(
      () => dispatch({ type: 'tick', now: Date.now() }),
      Math.max(0, deadline - Date.now()) + 20,
    )
    return () => window.clearTimeout(timer)
  }, [deadline, dispatch])

  return { state, dispatch }
}
