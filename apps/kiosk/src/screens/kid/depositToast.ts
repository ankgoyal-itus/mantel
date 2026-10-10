import { useEffect, useState } from 'react'

import type { BankRow } from '../../api/types'
import { depositSaid } from './bank'

/** How long "+$5 in your piggy bank" stays on the card. */
export const TOAST_MS = 4000

/** The newest deposit each card has already seen, kept across the card
    unmounting — the wall card and the open card are the same child, and a
    yes they were told about once is not news the second time. */
const remembered = new Map<string, number>()

type Seen = { kidId: string; id: number; toast: { id: number; text: string } | null }

/**
 * One line on a child's card for four seconds after a parent approves a
 * cash or Roblox reward: "+$5 in your piggy bank".
 *
 * Only a deposit newer than one this screen has already seen says anything,
 * so the first paint of the day is quiet and a reload never repeats it.
 */
export function useDepositToast(kidId: string, deposit: BankRow | null | undefined): string | null {
  const id = deposit?.id ?? 0
  const [seen, setSeen] = useState<Seen>(() => ({
    kidId,
    id: remembered.get(kidId) ?? id,
    toast: null,
  }))

  // Adjusting state while rendering, which React re-runs straight away.
  if (seen.kidId !== kidId) {
    setSeen({ kidId, id: remembered.get(kidId) ?? id, toast: null })
  } else if (deposit && id > seen.id) {
    setSeen({ kidId, id, toast: { id, text: depositSaid(deposit) } })
  }

  useEffect(() => {
    remembered.set(kidId, Math.max(remembered.get(kidId) ?? 0, id))
  }, [kidId, id])

  const showing = seen.toast?.id
  useEffect(() => {
    if (showing === undefined) {
      return
    }
    const timer = window.setTimeout(
      () => setSeen((current) => (current.toast?.id === showing ? { ...current, toast: null } : current)),
      TOAST_MS,
    )
    return () => window.clearTimeout(timer)
  }, [showing])

  return seen.toast?.text ?? null
}

/** For tests: forget what every card has seen. */
export function forgetDeposits(): void {
  remembered.clear()
}
