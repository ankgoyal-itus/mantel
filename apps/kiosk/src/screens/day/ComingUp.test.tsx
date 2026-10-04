import { describe, expect, it } from 'vitest'

import { shared } from './ComingUp'
import { TODAY } from './fixtures'

const [mira, kabir] = TODAY.kids

describe('Coming up', () => {
  it('draws an event both children have once, without a face', () => {
    const items = shared([
      { key: 'a', kid: mira, title: 'Conference Week - Early Release', start: null },
      { key: 'b', kid: kabir, title: 'Conference week -  early release', start: null },
      { key: 'c', kid: mira, title: 'Piano', start: '16:00' },
    ])
    expect(items.map((item) => [item.title, item.kid?.id ?? null])).toEqual([
      ['Conference Week - Early Release', null],
      ['Piano', 'mira'],
    ])
  })

  it('keeps a child on an event only they have, even twice over', () => {
    const items = shared([
      { key: 'a', kid: kabir, title: 'Picture day', start: null },
      { key: 'b', kid: kabir, title: 'Picture day', start: null },
    ])
    expect(items.map((item) => item.kid?.id)).toEqual(['kabir'])
  })

  it('keeps the same title at another time as its own event', () => {
    const items = shared([
      { key: 'a', kid: mira, title: 'Swim', start: '09:00' },
      { key: 'b', kid: kabir, title: 'Swim', start: '17:00' },
    ])
    expect(items).toHaveLength(2)
  })
})
