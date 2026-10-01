import { describe, expect, it } from 'vitest'

import { CHIP, chipLayout, chipsFor, chipsHeight, inChipOrder, worthLabel } from './chips'
import { task } from './fixtures'

const LONG_FIVE = [
  task('hw', 'Homework', { status: 'claimed' }),
  task('outside', '30 minutes outside'),
  task('reading', 'Reading, 20 minutes'),
  task('piano', 'Piano practice', { status: 'approved' }),
  task('dishes', 'Load the dishwasher', { routine: 'evening' }),
]

describe('the chips', () => {
  it('run in routine order, then task order', () => {
    const order = inChipOrder([
      task('a', 'A', { routine: 'evening' }),
      task('b', 'B'),
      task('c', 'C', { routine: 'morning' }),
      task('d', 'D', { routine: 'evening' }),
    ])
    expect(order.map((t) => t.id)).toEqual(['c', 'b', 'a', 'd'])
  })

  it('say what a to-do is worth, and that it is waiting once claimed', () => {
    expect(worthLabel(task('a', 'A', { points: 5 }))).toBe('+5')
    expect(worthLabel(task('a', 'A', { status: 'claimed', points: 2 }))).toBe('Waiting · +2')
  })

  it('say a once-a-week to-do is for the week, until it is done', () => {
    expect(worthLabel(task('math', 'Math homework', { every: 'week', points: 5 }))).toBe('+5 · week')
    const done = task('math', 'Math homework', { every: 'week', status: 'approved', points: 5 })
    expect(worthLabel(done)).toBe('+5')
    const waiting = task('math', 'Math homework', { every: 'week', status: 'claimed', points: 5 })
    expect(worthLabel(waiting)).toBe('Waiting · +5')
  })

  it('are 44px rows with 10px between', () => {
    expect(chipsHeight(0)).toBe(CHIP.height)
    expect(chipsHeight(1)).toBe(44)
    expect(chipsHeight(3)).toBe(152)
  })

  it('wrap short to-dos several to a row', () => {
    const short = [task('a', 'Tidy room'), task('b', 'Teeth'), task('c', 'Bed')]
    expect(chipLayout(short, 430).rows).toBe(1)
  })

  it('give a chip wider than the card two lines of caption and a row of its own', () => {
    const layout = chipLayout(
      [task('a', 'A very long thing the school asked for, with a form to sign and return')],
      302,
    )
    expect(layout.long.has('a')).toBe(true)
    expect(layout.rows).toBe(1)
  })

  it('go to caption size only when body size will not fit the room', () => {
    const body = chipLayout(LONG_FIVE, 430)
    expect(body.dense).toBe(false)
    // Room for all of them at body size: body size.
    expect(chipsFor(LONG_FIVE, 430, chipsHeight(body.rows))).toEqual(body)
    // Not: caption size, in fewer rows, every one still there.
    const dense = chipsFor(LONG_FIVE, 430, chipsHeight(3))
    expect(dense.dense).toBe(true)
    expect(dense.rows).toBeLessThan(body.rows)
  })
})
