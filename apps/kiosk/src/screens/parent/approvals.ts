import type { ApprovalItem, Kid } from '../../api/types'

export type ApprovalGroup = {
  key: string
  /** Whose group this is; null for the meals, which are the family's. */
  kidId: string | null
  items: ApprovalItem[]
}

/**
 * The queue as a parent reads it: the meals first, soonest first, then one
 * group per child in the family's order, newest first inside each.
 */
export function groupApprovals(items: ApprovalItem[], kids: Kid[]): ApprovalGroup[] {
  const groups: ApprovalGroup[] = []
  const meals = items
    .filter((item) => item.kind === 'meal')
    .sort((a, b) => a.when.localeCompare(b.when))
  if (meals.length > 0) {
    groups.push({ key: 'meals', kidId: null, items: meals })
  }

  const rest = items.filter((item) => item.kind !== 'meal')
  const order = [
    ...kids.map((kid) => kid.id),
    ...rest.map((item) => item.kid_id).filter((id) => !kids.some((kid) => kid.id === id)),
  ]
  for (const kidId of [...new Set(order)]) {
    const theirs = rest
      .filter((item) => item.kid_id === kidId)
      .sort((a, b) => b.when.localeCompare(a.when))
    if (theirs.length > 0) {
      groups.push({ key: kidId, kidId, items: theirs })
    }
  }
  return groups
}

/** "2:15 pm" today, "Mon 2:15 pm" before that. */
export function whenSaid(iso: string, now: Date = new Date()): string {
  const at = new Date(iso)
  if (Number.isNaN(at.getTime())) {
    return ''
  }
  const time = at.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }).toLowerCase()
  const sameDay =
    at.getFullYear() === now.getFullYear() &&
    at.getMonth() === now.getMonth() &&
    at.getDate() === now.getDate()
  return sameDay ? time : `${at.toLocaleDateString('en-US', { weekday: 'short' })} ${time}`
}
