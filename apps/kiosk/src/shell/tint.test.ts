import { describe, expect, it } from 'vitest'

import { readableInk, tintOverWhite } from './tint'

/** The page the day theme is printed on, which is what --bg is. */
const PAPER = '#fbfaf7'

/** WCAG contrast of a hex against the page, for asserting the ink is enough. */
function onPaper(colour: string, ground: string = PAPER): number {
  const rgb = [1, 3, 5].map((at) => parseInt(colour.slice(at, at + 2), 16))
  const channel = (value: number) => {
    const scaled = value / 255
    return scaled <= 0.03928 ? scaled / 12.92 : ((scaled + 0.055) / 1.055) ** 2.4
  }
  const lum = (values: number[]) =>
    0.2126 * channel(values[0]) + 0.7152 * channel(values[1]) + 0.0722 * channel(values[2])
  const paper = [1, 3, 5].map((at) => parseInt(ground.slice(at, at + 2), 16))
  return (lum(paper) + 0.05) / (lum(rgb) + 0.05)
}

describe('tintOverWhite', () => {
  it('lays the colour over white at 8%', () => {
    expect(tintOverWhite('#1F8A8A')).toBe('#edf6f6')
    expect(tintOverWhite('#D97706')).toBe('#fcf4eb')
  })

  it('reads three-digit hex, and refuses what it cannot read', () => {
    expect(tintOverWhite('#fff')).toBe('#ffffff')
    expect(tintOverWhite('rebeccapurple')).toBeNull()
  })
})

describe('readableInk', () => {
  it('darkens a colour only as far as AA needs', () => {
    // An amber like Kabir's is about 3:1 on the page: his own name on his
    // own card would fail the design checks.
    expect(onPaper('#d97706')).toBeLessThan(4.5)
    const ink = readableInk('#D97706')
    expect(ink).not.toBeNull()
    // Measured as it ships, not as the search found it: rounding to a hex
    // channel can hand back the tenth of a point the search just won.
    expect(onPaper(ink as string)).toBeGreaterThanOrEqual(4.5)
    // And no darker than it has to be: within a tenth of the floor.
    expect(onPaper(ink as string)).toBeLessThan(4.6)
  })

  it('leaves a colour alone when it already clears AA', () => {
    expect(readableInk('#1D2433')).toBe('#1d2433')
  })

  it('handles both kids, and gives up on what it cannot parse', () => {
    for (const colour of ['#1F8A8A', '#D97706']) {
      expect(onPaper(readableInk(colour) as string)).toBeGreaterThanOrEqual(4.5)
    }
    expect(readableInk('not a colour')).toBeNull()
  })

  it('darkens further for a word on the kid tint, a waiting chip', () => {
    for (const colour of ['#1F8A8A', '#D97706']) {
      const tint = tintOverWhite(colour) as string
      const ink = readableInk(colour, undefined, tint) as string
      expect(onPaper(ink, tint)).toBeGreaterThanOrEqual(4.5)
      // The page's ink falls just short there, which is why this exists.
      expect(onPaper(readableInk(colour) as string, tint)).toBeLessThan(4.5)
    }
  })
})
