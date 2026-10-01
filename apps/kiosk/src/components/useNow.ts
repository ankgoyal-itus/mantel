import { useEffect, useState } from 'react'

const DEFAULT_INTERVAL_MS = 15000

/** The current time, re-read on an interval. No seconds are shown anywhere. */
export function useNow(intervalMs: number = DEFAULT_INTERVAL_MS): Date {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), intervalMs)
    return () => window.clearInterval(timer)
  }, [intervalMs])

  return now
}
