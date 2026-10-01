import { useCallback, useEffect, useState } from 'react'

import { sessionOpen } from '../api/parent'

/** Often enough that the pill is not stale for long, rarely enough to ignore. */
const POLL_MS = 30000

export type ParentSession = {
  /** True while the API's ten-minute cookie is still good. */
  open: boolean
  /** Ask again now — after a PIN, after Done, after an approval. */
  refresh: () => void
}

/**
 * Whether a parent is signed in, as the API sees it.
 *
 * The cookie is HttpOnly, so the kiosk cannot read it and must not keep its
 * own ten-minute timer beside it: the two would drift, and the pill would
 * offer a parent screen the API then refuses. Asking costs one request every
 * half minute and survives a reload, which is what a wall display does at
 * four in the morning.
 */
export function useParentSession(): ParentSession {
  const [open, setOpen] = useState(false)
  const [nonce, setNonce] = useState(0)

  const refresh = useCallback(() => setNonce((count) => count + 1), [])

  useEffect(() => {
    let cancelled = false
    const ask = () => {
      void sessionOpen().then((live) => {
        if (!cancelled) {
          setOpen(live)
        }
      })
    }

    ask()
    const timer = window.setInterval(ask, POLL_MS)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [nonce])

  return { open, refresh }
}
