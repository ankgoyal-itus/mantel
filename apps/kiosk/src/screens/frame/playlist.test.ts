import { describe, expect, it } from 'vitest'

import type { Photo } from '../../api/types'
import { at, caption, ordered, playable, rank, shown } from './playlist'

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

describe('a new shuffle every pass (2026-10-18)', () => {
  const pass = (n: number) => LIBRARY.map((_, i) => shown(LIBRARY, SEED, n * LIBRARY.length + i)?.id)

  it('plays every photo once per pass, and no two passes alike', () => {
    const passes = [0, 1, 2, 3].map(pass)
    for (const p of passes) {
      expect(p.slice().sort()).toEqual(LIBRARY.map((one) => one.id).sort())
    }
    expect(new Set(passes.map((p) => p.join())).size).toBe(4)
  })

  it('never shows the same photo twice in a row at the turn', () => {
    const passes = [0, 1, 2, 3, 4, 5].map(pass)
    for (let n = 1; n < passes.length; n++) {
      expect(passes[n][0]).not.toBe(passes[n - 1][LIBRARY.length - 1])
    }
  })

  it('opens on no photo by rule, and survives an empty or single list', () => {
    const firsts = new Set(Array.from({ length: 40 }, (_, s) => shown(LIBRARY, s, 0)?.id))
    expect(firsts.size).toBeGreaterThan(2)
    expect(shown([], SEED, 0)).toBe(null)
    expect(shown([photo('only')], SEED, 9)?.id).toBe('only')
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
