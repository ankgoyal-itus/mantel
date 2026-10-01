import { useEffect, useState } from 'react'

import { getJson } from './client'
import type { PointsSummary } from './types'

export type Points = Record<string, PointsSummary>

/**
 * Every kid's balance, and the family jar's.
 *
 * Refetched whenever `nonce` changes, which is how a claim or an approval
 * gets the number on screen without waiting for the five minute poll. A
 * failed fetch keeps the last good number rather than blanking it: a balance
 * that flickers to nothing reads as points lost.
 */
export function usePoints(kidIds: string[], nonce: number): Points {
  const [points, setPoints] = useState<Points>({})
  const key = kidIds.join(',')

  useEffect(() => {
    if (!key) {
      return
    }
    let cancelled = false
    const ids = [...key.split(','), 'family']

    void Promise.all(
      ids.map((id) =>
        getJson<PointsSummary>(`/api/points/${id}`).then(
          (value) => value,
          () => null,
        ),
      ),
    ).then((results) => {
      if (cancelled) {
        return
      }
      setPoints((previous) => {
        const next = { ...previous }
        results.forEach((result) => {
          if (result) {
            next[result.kid_id] = result
          }
        })
        return next
      })
    })

    return () => {
      cancelled = true
    }
  }, [key, nonce])

  return points
}

/**
 * How many things wait on a parent.
 *
 * Deliberately just a number: the endpoint says how many and not whose or
 * what, because the badge it feeds is on a screen the kids are looking at.
 */
export function usePending(nonce: number): number {
  const [pending, setPending] = useState(0)

  useEffect(() => {
    let cancelled = false
    void getJson<{ pending: number }>('/api/approvals/count').then(
      (value) => {
        if (!cancelled) {
          setPending(value.pending)
        }
      },
      () => undefined,
    )
    return () => {
      cancelled = true
    }
  }, [nonce])

  return pending
}
