import { type ReactNode, createContext, useContext, useEffect, useState } from 'react'

import { getJson } from './client'
import type { VersionInfo } from './types'

/** How often the fallback asks, when there is no stream. */
const POLL_MS = 5000
/** Reconnecting the stream: 2, 4, 8 … seconds, never more than 30. */
const BACKOFF_FIRST_MS = 2000
const BACKOFF_MAX_MS = 30000

export type Live = {
  /** The API's state version; null until the first answer. */
  version: number | null
  /** Set when a parent asks both iPads to reload. */
  reloadAt: string | null
}

const EMPTY: Live = { version: null, reloadAt: null }

/**
 * What the API says has changed, as it changes.
 *
 * The /api/events stream sends the state version whenever a write moves it —
 * a parent's approval on a phone, a pick, a meal set — so every screen can
 * refetch within a second instead of at the next five-minute poll. Where
 * there is no EventSource, or the stream drops, it asks /api/version every
 * five seconds and tries the stream again after 2, 4, 8 … 30 seconds.
 */
export function useLiveSource(): Live {
  const [live, setLive] = useState<Live>(EMPTY)

  useEffect(() => {
    let stopped = false
    let source: EventSource | null = null
    let poll: number | null = null
    let retry: number | null = null
    let backoff = BACKOFF_FIRST_MS

    const seen = (version: number) =>
      setLive((previous) => (previous.version === version ? previous : { ...previous, version }))

    const stopPolling = () => {
      if (poll !== null) {
        window.clearInterval(poll)
        poll = null
      }
    }

    const startPolling = () => {
      if (poll !== null) {
        return
      }
      const ask = () => {
        void getJson<VersionInfo>('/api/version').then(
          (info) => !stopped && seen(info.version),
          () => undefined,
        )
      }
      ask()
      poll = window.setInterval(ask, POLL_MS)
    }

    const connect = () => {
      if (stopped) {
        return
      }
      if (typeof window.EventSource !== 'function') {
        startPolling()
        return
      }
      source = new EventSource('/api/events')
      source.addEventListener('open', () => {
        backoff = BACKOFF_FIRST_MS
        stopPolling()
      })
      source.addEventListener('version', (event) => {
        try {
          seen((JSON.parse((event as MessageEvent<string>).data) as VersionInfo).version)
        } catch {
          // A garbled line is not a change; the next one will be.
        }
      })
      source.addEventListener('reload', (event) => {
        const at = (event as MessageEvent<string>).data
        setLive((previous) => ({ ...previous, reloadAt: at }))
      })
      source.addEventListener('error', () => {
        // The browser would retry on its own, but on its own schedule and
        // silently; take it over: poll meanwhile, and reconnect with backoff.
        source?.close()
        source = null
        startPolling()
        if (retry === null && !stopped) {
          retry = window.setTimeout(() => {
            retry = null
            connect()
          }, backoff)
          backoff = Math.min(backoff * 2, BACKOFF_MAX_MS)
        }
      })
    }

    connect()
    return () => {
      stopped = true
      source?.close()
      stopPolling()
      if (retry !== null) {
        window.clearTimeout(retry)
      }
    }
  }, [])

  return live
}

const LiveContext = createContext<Live>(EMPTY)

/** One stream for the whole app, whichever screen is up. */
export function LiveProvider({ children }: { children: ReactNode }) {
  const live = useLiveSource()
  return <LiveContext.Provider value={live}>{children}</LiveContext.Provider>
}

export function useLive(): Live {
  return useContext(LiveContext)
}

/**
 * A number that changes when something another screen did has changed what
 * this one shows. For a loader's dependency list: the first answer is the
 * baseline and does not count, so opening a screen does not load it twice.
 */
export function useLiveNonce(): number {
  const { version } = useLive()
  const [base, setBase] = useState(version)
  if (base === null && version !== null) {
    // Adjusting state while rendering: the first answer is the baseline.
    setBase(version)
  }
  return version === null || base === null ? 0 : version - base
}
