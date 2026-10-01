import { useEffect, useState } from 'react'

import { getJson } from './client'
import type { Day } from './types'

/**
 * Sixty days of agenda, fetched once when the list is first opened and kept
 * for the session. Paging back and forth between the month and the list
 * should not ask the API the same question twice.
 */
export function useAgenda(enabled: boolean, days = 60): Day[] {
  const [agenda, setAgenda] = useState<Day[]>([])

  useEffect(() => {
    if (!enabled || agenda.length > 0) {
      return
    }
    let cancelled = false
    getJson<Day[]>(`/api/agenda?days=${days}`)
      .then((found) => {
        if (!cancelled) {
          setAgenda(found)
        }
      })
      .catch(() => {
        // The list stays empty and says so; the screens behind it are fine.
      })
    return () => {
      cancelled = true
    }
  }, [enabled, days, agenda.length])

  return agenda
}
