import { useEffect, useState } from 'react'

import { copy } from '../copy'
import { clock12 } from '../format'

/**
 * Nothing at all while the data is fresh.
 *
 * The old chip said "updated 9:41" every minute of every day, which taught
 * everyone to stop seeing it. This appears only once the answer on screen is
 * old enough to be wrong — a quarter of an hour — and then says since when.
 */
const STALE_AFTER_MS = 15 * 60 * 1000
const TICK_MS = 30000

export default function StaleDot({ lastUpdated }: { lastUpdated: number | null }) {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), TICK_MS)
    return () => window.clearInterval(timer)
  }, [])

  if (lastUpdated === null || now - lastUpdated < STALE_AFTER_MS) {
    return null
  }
  return (
    <div className="stale">
      <span className="stale-dot" aria-hidden="true" />
      {copy.stale.since(clock12(new Date(lastUpdated)))}
    </div>
  )
}
