import { describe, expect, it } from 'vitest'

import type { ApprovalItem, Kid } from '../../api/types'
import { groupApprovals, whenSaid } from './approvals'

const KIDS: Kid[] = [
  { id: 'mira', name: 'Mira', color: '#1F8A8A', avatar: 'fox' },
  { id: 'kabir', name: 'Kabir', color: '#D97706', avatar: 'panda' },
]

function item(kind: ApprovalItem['kind'], kid: string, when: string, title = 'x'): ApprovalItem {
  return { kind, id: 1, kid_id: kid, title, points: 10, when, note: null }
}

describe('the approvals list', () => {
  it('puts the meals first, then each child in the family order', () => {
    const groups = groupApprovals(
      [
        item('claim', 'kabir', '2026-09-23T15:00:00'),
        item('meal', 'kabir', '2026-09-24T00:00:00'),
        item('redemption', 'mira', '2026-09-23T09:00:00'),
      ],
      KIDS,
    )
    expect(groups.map((group) => group.key)).toEqual(['meals', 'mira', 'kabir'])
  })

  it('lists each child newest first', () => {
    const [group] = groupApprovals(
      [
        item('claim', 'mira', '2026-09-23T08:00:00', 'older'),
        item('claim', 'mira', '2026-09-23T16:00:00', 'newer'),
      ],
      KIDS,
    )
    expect(group.items.map((one) => one.title)).toEqual(['newer', 'older'])
  })

  it('says the time today and the weekday before that', () => {
    const now = new Date(2026, 8, 23, 18, 0)
    expect(whenSaid('2026-09-23T14:15:00', now)).toBe('2:15 pm')
    expect(whenSaid('2026-09-21T14:15:00', now)).toBe('Mon 2:15 pm')
  })
})
