import { describe, expect, it } from 'vitest'

import { BURST_MS, PARTICLE_COUNT, advance, alphaAt, makeParticles, shouldFire } from './confetti'

describe('when it fires', () => {
  it('fires on a balance that went up', () => {
    expect(shouldFire(10, 20)).toBe(true)
  })

  it('fires once per approval, not once per poll', () => {
    // The dashboard polls every few minutes and the number does not move
    // between approvals; only the step up is a yes.
    const polls = [0, 0, 0, 10, 10, 10, 10, 20, 20]
    let fired = 0
    for (let at = 1; at < polls.length; at += 1) {
      if (shouldFire(polls[at - 1], polls[at])) {
        fired += 1
      }
    }
    expect(fired).toBe(2)
  })

  it('does not fire on the first sighting of a number', () => {
    // Otherwise every morning's first load would greet an empty kitchen.
    expect(shouldFire(null, 120)).toBe(false)
    expect(shouldFire(null, 0)).toBe(false)
  })

  it('does not fire when points are spent', () => {
    // Asking for a reward holds the points, which takes the balance down.
    // That is a thing a child did, not a thing they were told yes about.
    expect(shouldFire(30, 0)).toBe(false)
    expect(shouldFire(30, 30)).toBe(false)
  })
})

describe('the burst', () => {
  const roll = (() => {
    // A deterministic stand-in for Math.random, so the shape is assertable.
    let n = 0
    return () => ((n = (n * 9301 + 49297) % 233280) / 233280)
  })()

  it('is eighty pieces in the colours it was given', () => {
    const pieces = makeParticles(400, 300, ['#1f8a8a', '#20844d'], roll)
    expect(pieces).toHaveLength(PARTICLE_COUNT)
    expect(new Set(pieces.map((one) => one.colour))).toEqual(
      new Set(['#1f8a8a', '#20844d']),
    )
  })

  it('starts inside the card it is drawn over', () => {
    for (const piece of makeParticles(400, 300, ['#000'], roll)) {
      expect(piece.x).toBeGreaterThanOrEqual(0)
      expect(piece.x).toBeLessThanOrEqual(400)
      expect(piece.y).toBeGreaterThanOrEqual(0)
      expect(piece.y).toBeLessThanOrEqual(300)
    }
  })

  it('throws upward first, so it reads as a burst and not a collapse', () => {
    const pieces = makeParticles(400, 300, ['#000'], roll)
    expect(pieces.every((piece) => piece.vy < 0)).toBe(true)
  })

  it('comes down again', () => {
    let piece = makeParticles(400, 300, ['#000'], roll)[0]
    const from = piece.y
    for (let n = 0; n < 60; n += 1) {
      piece = advance(piece, 1 / 60)
    }
    expect(piece.y).toBeGreaterThan(from)
  })

  it('is gone by the end of its 900ms', () => {
    expect(alphaAt(0)).toBe(1)
    expect(alphaAt(BURST_MS * 0.5)).toBe(1)
    expect(alphaAt(BURST_MS * 0.9)).toBeLessThan(1)
    expect(alphaAt(BURST_MS)).toBe(0)
    expect(alphaAt(BURST_MS * 2)).toBe(0)
  })
})
