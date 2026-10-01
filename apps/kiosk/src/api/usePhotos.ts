import { useEffect, useState } from 'react'

import { getJson } from './client'
import type { Photo } from './types'

/**
 * The photo list, re-fetched on the same cadence as everything else. A failed
 * fetch keeps the list that is already playing: the frame must not go blank
 * because the Mac was asleep for a minute.
 */
export function usePhotos(refreshMinutes: number): Photo[] {
  const [photos, setPhotos] = useState<Photo[]>([])

  useEffect(() => {
    let cancelled = false
    let timer: number | null = null
    const every = Math.max(1, refreshMinutes) * 60000

    const load = () => {
      getJson<Photo[]>('/api/photos')
        .then((fetched) => {
          if (!cancelled) {
            setPhotos(fetched)
          }
        })
        .catch(() => {
          // Keep what we have; the next poll will try again.
        })
        .finally(() => {
          if (!cancelled) {
            timer = window.setTimeout(load, every)
          }
        })
    }

    load()
    return () => {
      cancelled = true
      if (timer !== null) {
        window.clearTimeout(timer)
      }
    }
  }, [refreshMinutes])

  return photos
}
