import { useEffect, useState } from 'react'

import { staleLevel, updatedLabel } from '../api/stale'

const TICK_MS = 30000

export default function UpdatedChip({
  lastUpdated,
  stale,
}: {
  lastUpdated: number | null
  stale: boolean
}) {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), TICK_MS)
    return () => window.clearInterval(timer)
  }, [])

  // Before the first poll there is no age to judge, only whether it failed.
  const level =
    lastUpdated === null ? (stale ? 'amber' : 'fresh') : staleLevel(now - lastUpdated, stale)

  return <div className={`chip chip-${level}`}>{updatedLabel(lastUpdated)}</div>
}
