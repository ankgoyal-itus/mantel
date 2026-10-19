import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import type { Photo, Weather } from '../api/types'
import { useNow } from '../components/useNow'
import { clock12, monthYear } from '../format'
import '../styles/frame.css'
import FrameChip from './frame/FrameChip'
import { useBrightCorner } from './frame/brightness'
import { caption, playable, shown } from './frame/playlist'

/** One photo into the next: 800ms, and the caption with it. */
const FADE_MS = 800
const DEFAULT_SLIDE_SECONDS = 20

export type FrameScreenProps = {
  photos: Photo[]
  slideSeconds: number
  /** True inside the night window: the whole slide goes under a black sheet. */
  night: boolean
  /** For the chip: the current temperature and the day's high and low. */
  weather?: Weather | null
  /** Settings → Photos: the chip, and whether it is the large one. */
  chip?: boolean
  chipLarge?: boolean
}

/** The small clock in the caption's corner, when there is no chip to say it.
    Its own component, so the minute ticks here and not over the photo. */
function CornerClock() {
  const now = useNow()
  return <span className="frame-clock">{clock12(now)}</span>
}

function Slide({
  photo,
  entering,
  slideMs,
  onError,
}: {
  photo: Photo
  entering: boolean
  slideMs: number
  onError: (id: string) => void
}) {
  return (
    <div
      className={entering ? 'slide slide-entering' : 'slide'}
      style={{ ['--slide-ms']: `${slideMs}ms` } as React.CSSProperties}
    >
      {/* The same photo, blown up and blurred, so a portrait sits on itself
          rather than on two black bars. */}
      <div className="slide-wash" style={{ backgroundImage: `url("${photo.url}")` }} />
      <img
        className="slide-photo"
        src={photo.url}
        alt=""
        draggable={false}
        onError={() => onError(photo.id)}
      />
    </div>
  )
}

export default function FrameScreen({
  photos,
  slideSeconds,
  night,
  weather = null,
  chip = true,
  chipLarge = false,
}: FrameScreenProps) {
  const [broken, setBroken] = useState<ReadonlySet<string>>(() => new Set())
  const [cursor, setCursor] = useState(0)
  const [leaving, setLeaving] = useState<Photo | null>(null)

  const slideMs = Math.max(1, slideSeconds || DEFAULT_SLIDE_SECONDS) * 1000

  // A random seed per session; each pass through the photos reshuffles from it
  // (playlist.shown), so the frame never replays the same order.
  const [seed] = useState(() => Math.floor(Math.random() * 0x7fffffff))
  const list = useMemo(() => playable(photos, broken), [photos, broken])

  const current = shown(list, seed, cursor)
  const bright = useBrightCorner(current ? current.url : null, night)

  const currentRef = useRef<Photo | null>(current)
  useEffect(() => {
    currentRef.current = current
  }, [current])

  const advance = useCallback(() => {
    setLeaving(currentRef.current)
    setCursor((previous) => previous + 1)
  }, [])

  useEffect(() => {
    if (list.length < 2) {
      return
    }
    const timer = window.setInterval(advance, slideMs)
    return () => window.clearInterval(timer)
  }, [advance, slideMs, list.length])

  // The outgoing slide is only around for the crossfade.
  useEffect(() => {
    if (!leaving) {
      return
    }
    const timer = window.setTimeout(() => setLeaving(null), FADE_MS)
    return () => window.clearTimeout(timer)
  }, [leaving])

  // The next one is in the cache before it is asked for, so a slide never
  // arrives half-drawn over a slow minute of Wi-Fi.
  useEffect(() => {
    if (list.length < 2) {
      return
    }
    const next = shown(list, seed, cursor + 1)
    if (next) {
      const preload = new Image()
      preload.src = next.url
    }
  }, [cursor, list, seed])

  const onError = useCallback((id: string) => {
    // One that will not load is dropped for the session rather than retried
    // every time it comes round.
    setBroken((previous) => new Set(previous).add(id))
  }, [])

  // "Lake Tahoe · June 2024", or just the month, or nothing at all.
  const said = current ? caption(current.place ?? null, monthYear(current.taken_at)) : ''

  return (
    <div className="screen screen-frame frame">
      {leaving && leaving.id !== (current ? current.id : '') ? (
        <Slide
          key={`leaving-${leaving.id}`}
          photo={leaving}
          entering={false}
          slideMs={slideMs}
          onError={onError}
        />
      ) : null}

      {current ? (
        <Slide
          key={`current-${current.id}-${cursor}`}
          photo={current}
          entering
          slideMs={slideMs}
          onError={onError}
        />
      ) : null}

      {night ? <div className="frame-dim" /> : null}

      {/* Top-right, over everything and never moving with a slide: the
          time and the weather in one frosted pill. */}
      {chip ? <FrameChip weather={weather} night={night} large={chipLarge} bright={bright} /> : null}

      {/* The month, bottom-right; the small clock beside it only when the
          chip is off. At night they drop to a quarter. */}
      <div className={night ? 'frame-captions frame-captions-night' : 'frame-captions'}>
        {said ? (
          // Keyed on the photo, so the caption fades with it.
          <span key={current ? current.id : ''} className="frame-when frame-when-in">
            {said}
          </span>
        ) : null}
        {chip ? null : <CornerClock />}
      </div>
    </div>
  )
}
