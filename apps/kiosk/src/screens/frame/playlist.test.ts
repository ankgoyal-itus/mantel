import { describe, expect, it } from 'vitest'

import type { Photo } from '../../api/types'
import { at, caption, newestFirst, ordered, playable, rank } from './playlist'

function photo(id: string): Photo {
  return { id, url: `/api/photos/${id}.jpg`, w: 2048, h: 1536, taken_at: null }
}

const LIBRARY = ['a1', 'b2', 'c3', 'd4', 'e5', 'f6', 'g7', 'h8'].map(photo)
const SEED = 12345

describe('the playing order', () => {
  it('is a permutation of what came in', () => {
    const ids = ordered(LIBRARY, SEED).map((p) => p.id)
    expect(ids.slice().sort()).toEqual(LIBRARY.map((p) => p.id).sort())
  })

  it('is the same order every time for one session', () => {
    expect(ordered(LIBRARY, SEED)).toEqual(ordered(LIBRARY, SEED))
    // ...including when the API hands the list back in a different order.
    expect(ordered([...LIBRARY].reverse(), SEED)).toEqual(ordered(LIBRARY, SEED))
  })

  it('is not simply the order the API sent', () => {
    const shuffledByUs = ordered(LIBRARY, SEED).map((p) => p.id)
    expect(shuffledByUs).not.toEqual(LIBRARY.map((p) => p.id))
  })

  it('differs between sessions', () => {
    const orders = [1, 2, 3, 4, 5].map((seed) =>
      ordered(LIBRARY, seed)
        .map((p) => p.id)
        .join(),
    )
    expect(new Set(orders).size).toBe(orders.length)
  })

  it('folds new photos in without reshuffling what is playing', () => {
    const before = ordered(LIBRARY, SEED).map((p) => p.id)
    const after = ordered([...LIBRARY, photo('new1'), photo('new2')], SEED).map((p) => p.id)

    expect(after).toHaveLength(before.length + 2)
    // Everything already on the playlist holds its relative order, which is
    // what keeps a refresh from restarting the slideshow.
    expect(after.filter((id) => before.includes(id))).toEqual(before)
  })

  it('spreads ids that differ by one character', () => {
    const ranks = new Set(['a1', 'a2', 'a3', 'b1'].map((id) => rank(id, SEED)))
    expect(ranks.size).toBe(4)
  })
})

describe('skipping and wrapping', () => {
  it('drops photos that would not load', () => {
    const list = playable(LIBRARY, new Set(['c3', 'f6']))
    expect(list.map((p) => p.id)).toEqual(['a1', 'b2', 'd4', 'e5', 'g7', 'h8'])
  })

  it('wraps the cursor, in both directions', () => {
    expect(at(0, 3)).toBe(0)
    expect(at(3, 3)).toBe(0)
    expect(at(4, 3)).toBe(1)
    expect(at(-1, 3)).toBe(2)
  })

  it('survives an empty playlist', () => {
    expect(at(7, 0)).toBe(0)
    expect(playable([], new Set())).toEqual([])
  })
})

describe('what plays first after a wake', () => {
  const photo = (id: string, taken: string | null): Photo => ({
    id,
    url: `/p/${id}.jpg`,
    w: 2048,
    h: 1536,
    taken_at: taken,
  })

  it('opens on the most recent thing the house did', () => {
    const list = newestFirst([
      photo('a', '2024-01-02'),
      photo('c', '2026-08-30'),
      photo('b', '2025-06-14'),
    ])
    expect(list[0].id).toBe('c')
  })

  it('keeps everything else in the order it was given', () => {
    const list = newestFirst([
      photo('a', '2024-01-02'),
      photo('c', '2026-08-30'),
      photo('b', '2025-06-14'),
    ])
    expect(list.map((one) => one.id)).toEqual(['c', 'a', 'b'])
  })

  it('goes by when it was taken, not when it arrived', () => {
    // A scan of an old print is not new because it was scanned today.
    const list = newestFirst([photo('scan', '1994-07-01'), photo('sat', '2026-09-19')])
    expect(list[0].id).toBe('sat')
  })

  it('leaves an undated library exactly as it found it', () => {
    const list = newestFirst([photo('a', null), photo('b', null)])
    expect(list.map((one) => one.id)).toEqual(['a', 'b'])
  })

  it('ignores the undated ones rather than ranking them', () => {
    const list = newestFirst([photo('a', null), photo('b', '2020-01-01')])
    expect(list[0].id).toBe('b')
  })
})

describe('the caption', () => {
  it('says where and when', () => {
    expect(caption('Lake Tahoe', 'June 2024')).toBe('Lake Tahoe · June 2024')
  })

  it('says whichever it has', () => {
    expect(caption(null, 'June 2024')).toBe('June 2024')
    expect(caption('Lake Tahoe', '')).toBe('Lake Tahoe')
  })

  it('says nothing rather than a bare separator', () => {
    expect(caption(null, '')).toBe('')
  })
})
