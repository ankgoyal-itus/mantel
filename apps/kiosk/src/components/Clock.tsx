import { useEffect, useState } from 'react'

function format(when: Date): string {
  return when.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

export default function Clock() {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  return <div className="clock">{format(now)}</div>
}
