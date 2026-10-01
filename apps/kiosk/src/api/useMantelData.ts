import { useEffect, useRef, useState } from 'react'

import { getJson } from './client'
import type { Config, Day, DayPicks, Health, Weather } from './types'

const FALLBACK_REFRESH_MINUTES = 5

export type MantelData = {
  config: Config | null
  today: Day | null
  tomorrow: Day | null
  /** The next three days after today, for the Coming up card. */
  upcoming: Day[]
  /** Seven days of meal picks from today, for the "My week" dots. */
  week: DayPicks[]
  weather: Weather | null
  /** API version from /api/health, watched for new builds. */
  version: string | null
  /** Set when a parent asked both iPads to reload. */
  reloadAt: string | null
  /** When the last fully successful poll finished. */
  lastUpdated: number | null
  /** True when the most recent poll did not fully succeed. */
  stale: boolean
}

const EMPTY: MantelData = {
  config: null,
  today: null,
  tomorrow: null,
  upcoming: [],
  week: [],
  weather: null,
  version: null,
  reloadAt: null,
  lastUpdated: null,
  stale: false,
}

type Result<T> = { ok: true; value: T } | { ok: false }

function attempt<T>(path: string): Promise<Result<T>> {
  return getJson<T>(path).then(
    (value): Result<T> => ({ ok: true, value }),
    (): Result<T> => ({ ok: false }),
  )
}

/**
 * Polls the API and keeps the last good response per endpoint, so one failed
 * request never blanks the screen. Config is fetched once and then only
 * retried until it succeeds.
 */
export function useMantelData(live = 0): MantelData {
  const [data, setData] = useState<MantelData>(EMPTY)
  // The live refetch, set by the poll's effect so it shares its guards.
  const refetchRef = useRef<(() => Promise<void>) | null>(null)

  useEffect(() => {
    let cancelled = false
    let timer: number | null = null
    let refreshMinutes = FALLBACK_REFRESH_MINUTES
    let haveConfig = false

    async function loadConfig(): Promise<void> {
      const result = await attempt<Config>('/api/config')
      if (cancelled || !result.ok) {
        return
      }
      haveConfig = true
      refreshMinutes = result.value.settings.refresh_minutes || FALLBACK_REFRESH_MINUTES
      setData((previous) => ({ ...previous, config: result.value }))
    }

    async function poll(): Promise<void> {
      const [today, agenda, weather, health, picks] = await Promise.all([
        attempt<Day>('/api/today'),
        // Four days: today, tomorrow's card, and the two after it that the
        // Coming up card adds when the screen has the room.
        attempt<Day[]>('/api/agenda?days=4'),
        attempt<Weather>('/api/weather'),
        attempt<Health>('/api/health'),
        // A week of meal picks from today: the dots on each child's card.
        // Not counted as a failure: a card without its dots is still a card.
        attempt<DayPicks[]>('/api/picks?days=7'),
      ])
      if (cancelled) {
        return
      }
      const failed = !today.ok || !agenda.ok || !weather.ok || !health.ok
      const now = Date.now()
      setData((previous) => ({
        ...previous,
        today: today.ok ? today.value : previous.today,
        tomorrow: agenda.ok ? (agenda.value[1] ?? null) : previous.tomorrow,
        upcoming: agenda.ok ? agenda.value.slice(1, 4) : previous.upcoming,
        week: picks.ok ? picks.value : previous.week,
        weather: weather.ok ? weather.value : previous.weather,
        version: health.ok ? health.value.version : previous.version,
        reloadAt: health.ok ? (health.value.reload_at ?? null) : previous.reloadAt,
        lastUpdated: failed ? previous.lastUpdated : now,
        stale: failed,
      }))
    }

    // What another screen's write can change here: today, the next days and
    // the week of picks. Weather and health keep to the poll.
    async function refetch(): Promise<void> {
      const [today, agenda, picks] = await Promise.all([
        attempt<Day>('/api/today'),
        attempt<Day[]>('/api/agenda?days=4'),
        attempt<DayPicks[]>('/api/picks?days=7'),
      ])
      if (cancelled) {
        return
      }
      setData((previous) => ({
        ...previous,
        today: today.ok ? today.value : previous.today,
        tomorrow: agenda.ok ? (agenda.value[1] ?? null) : previous.tomorrow,
        upcoming: agenda.ok ? agenda.value.slice(1, 4) : previous.upcoming,
        week: picks.ok ? picks.value : previous.week,
      }))
    }
    refetchRef.current = refetch

    async function cycle(): Promise<void> {
      if (!haveConfig) {
        await loadConfig()
      }
      await poll()
      if (!cancelled) {
        timer = window.setTimeout(() => {
          void cycle()
        }, refreshMinutes * 60000)
      }
    }

    void cycle()

    return () => {
      cancelled = true
      if (timer !== null) {
        window.clearTimeout(timer)
      }
    }
  }, [])

  // The live version moved: something another screen did changed this one.
  // The five-minute poll stays as the safety net under it.
  useEffect(() => {
    if (live > 0) {
      void refetchRef.current?.()
    }
  }, [live])

  return data
}
