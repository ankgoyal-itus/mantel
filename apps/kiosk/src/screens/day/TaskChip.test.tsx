import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { TaskEntry } from '../../api/types'
import { task } from './fixtures'
import TaskChip, { chipState } from './TaskChip'

function chip(entry: TaskEntry, claimable = false, long = false): string {
  return renderToStaticMarkup(<TaskChip task={entry} claimable={claimable} long={long} />)
}

describe('a to-do chip', () => {
  it('draws each of the five states with its own class', () => {
    const cases: [TaskEntry, string][] = [
      [task('a', 'Tidy room'), 'open'],
      [task('a', 'Tidy room', { status: 'claimed', claim_id: 1 }), 'claimed'],
      [task('a', 'Tidy room', { status: 'approved' }), 'approved'],
      [task('a', 'Tidy room', { status: 'declined' }), 'declined'],
      [task('a', 'Tidy room', { claim: 'parent' }), 'parent'],
    ]
    for (const [entry, state] of cases) {
      expect(chipState(entry)).toBe(state)
      expect(chip(entry)).toContain(`<li class="chip-task chip-task-${state}"`)
    }
  })

  it('rings an open chip, and says what it is worth', () => {
    const html = chip(task('a', 'Tidy room', { points: 5 }))
    expect(html).toContain('chip-task-ring')
    expect(html).toContain('chip-task-title">Tidy room<')
    expect(html).toContain('chip-task-worth">+5<')
  })

  it('says a claimed chip is waiting', () => {
    const html = chip(task('a', '30 min outside', { status: 'claimed', points: 2 }))
    expect(html).toContain('chip-task-worth">Waiting · +2<')
  })

  it('fills the ring of an approved chip with a tick', () => {
    const html = chip(task('a', 'Tidy room', { status: 'approved' }))
    expect(html).toContain('chip-task-ring chip-task-tick')
    expect(html).toContain('<svg')
  })

  it('puts the lock where the ring would be on a parent-only chip', () => {
    const html = chip(task('a', 'Trash', { claim: 'parent' }))
    expect(html).toContain('chip-task-lock')
    expect(html).not.toContain('chip-task-ring')
  })

  it('is a button in kid mode, and only where a tap does something', () => {
    expect(chip(task('a', 'Tidy room'), true)).toContain('<button type="button" class="chip-task-tap"')
    expect(chip(task('a', 'Tidy room'), false)).not.toContain('<button')
    expect(chip(task('a', 'Trash', { claim: 'parent' }), true)).not.toContain('<button')
    expect(chip(task('a', 'Done', { status: 'approved' }), true)).not.toContain('<button')
  })

  it('marks a chip too long for one line', () => {
    expect(chip(task('a', 'Tidy room'), false, true)).toContain('chip-task chip-task-open chip-task-long')
  })
})
