import type { TaskEntry } from '../../api/types'

/** What the day of to-dos is worth, for the foot of a child's card. */

/** What a parent has said yes to: points on the ledger today. */
export function earnedBy(tasks: readonly TaskEntry[]): number {
  return tasks
    .filter((task) => task.status === 'approved')
    .reduce((sum, task) => sum + task.points, 0)
}

/** What is still on the table: open and waiting to-dos. Not today's no. */
export function stillToEarn(tasks: readonly TaskEntry[]): number {
  return tasks
    .filter((task) => task.status === 'none' || task.status === 'claimed')
    .reduce((sum, task) => sum + task.points, 0)
}
