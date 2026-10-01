import { describe, expect, it } from 'vitest'

import type { TaskEntry } from '../../api/types'
import { earnedBy, stillToEarn } from './taskList'

function task(id: string, routine: string, status: TaskEntry['status'] = 'none', points = 5): TaskEntry {
  return { id, title: id, claim: 'kid', status, points, routine, claim_id: null } as TaskEntry
}

describe('the day of to-dos', () => {
  it('says what the day is worth: earned, and still to earn', () => {
    const tasks = [
      task('a', 'afternoon', 'approved', 4),
      task('b', 'afternoon', 'claimed', 5),
      task('c', 'evening', 'none', 6),
      task('d', 'evening', 'declined', 9),
    ]
    expect(earnedBy(tasks)).toBe(4)
    expect(stillToEarn(tasks)).toBe(11)
  })
})
