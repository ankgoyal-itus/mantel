import { useEffect, useState } from 'react'
import { copy } from '../copy'

import UpdatedChip from '../shell/UpdatedChip'

type HealthState = { text: string; ok: boolean }

/** iPadOS 13+ reports a desktop Safari UA by default, so this is best effort. */
function iosVersion(userAgent: string): string {
  const match = /(?:iPhone )?OS (\d+)[._](\d+)(?:[._](\d+))?/.exec(userAgent)
  if (match) {
    const parts = [match[1], match[2], match[3]].filter(Boolean)
    return parts.join('.')
  }
  const version = /Version\/(\d+(?:\.\d+)*)/.exec(userAgent)
  if (version && /Macintosh/.test(userAgent)) {
    return `unknown (desktop-class UA, Safari ${version[1]})`
  }
  return 'unknown'
}

function isDesktopClass(userAgent: string): boolean {
  return /Macintosh/.test(userAgent) && !/OS \d+[._]\d+/.test(userAgent)
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="diag-row">
      <span className="diag-key">{label}</span>
      <span className="diag-value">{value}</span>
    </div>
  )
}

export default function Diag() {
  const [loadedAt] = useState(() => Date.now())
  const [health, setHealth] = useState<HealthState>({ text: 'loading…', ok: false })
  const [viewport, setViewport] = useState({ width: 0, height: 0 })

  // Safari reports 0 during the first render, and again on every rotation.
  useEffect(() => {
    const read = () => setViewport({ width: window.innerWidth, height: window.innerHeight })
    read()
    window.addEventListener('resize', read)
    window.addEventListener('orientationchange', read)
    return () => {
      window.removeEventListener('resize', read)
      window.removeEventListener('orientationchange', read)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    fetch('/api/health')
      .then((response) => response.json())
      .then((data: unknown) => {
        if (!cancelled) {
          setHealth({ text: JSON.stringify(data, null, 2), ok: true })
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setHealth({ text: `unreachable: ${String(error)}`, ok: false })
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  const standalone = (navigator as Navigator & { standalone?: boolean }).standalone

  return (
    <div className="diag">
      <h1>{copy.diag.title}</h1>
      <UpdatedChip lastUpdated={loadedAt} stale={!health.ok} />
      <Row label="userAgent" value={navigator.userAgent} />
      <Row label="iOS" value={iosVersion(navigator.userAgent)} />
      {isDesktopClass(navigator.userAgent) ? (
        <div className="diag-row diag-hint">
          {copy.diag.desktopClass}
        </div>
      ) : null}
      <Row label="viewport" value={`${viewport.width} x ${viewport.height}`} />
      <Row label="devicePixelRatio" value={String(window.devicePixelRatio)} />
      <Row label="standalone" value={String(standalone)} />
      <Row label="onLine" value={String(navigator.onLine)} />
      <div className="diag-row">
        <span className="diag-key">{copy.diag.health}</span>
        <pre className={health.ok ? 'diag-json' : 'diag-json diag-json-bad'}>{health.text}</pre>
      </div>
    </div>
  )
}
