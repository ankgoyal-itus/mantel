import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { kidPaper } from '../shell/kidPalette'

/**
 * Reads the palette out of theme.css so the test fails if a colour changes.
 * The children's colours are not in it — they are data, and shell/kidPalette
 * derives their forms at runtime — so theirs are checked below, through the
 * same code, for the sample family's two.
 */
function palette(): Record<string, string> {
  const css = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', 'theme.css'), 'utf8')
  const root = css.slice(css.indexOf(':root'), css.indexOf('}', css.indexOf(':root')))
  const found: Record<string, string> = {}
  for (const match of root.matchAll(/--([\w-]+):\s*(?:var\([^,)]+,\s*)?(#[0-9a-fA-F]{6})/g)) {
    found[match[1]] = match[2]
  }
  return found
}

function channel(value: number): number {
  const c = value / 255
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
}

function luminance(hex: string): number {
  const v = hex.replace('#', '')
  const r = channel(parseInt(v.slice(0, 2), 16))
  const g = channel(parseInt(v.slice(2, 4), 16))
  const b = channel(parseInt(v.slice(4, 6), 16))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function ratio(a: string, b: string): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (light + 0.05) / (dark + 0.05)
}

const AA = 4.5
const AA_LARGE = 3

const MEANINGS = ['school', 'festival', 'holiday']

/** The sample family's colours: a teal and an amber. */
const KIDS = { mira: '#1F8A8A', kabir: '#D97706' }

/**
 * The day palette, checked here rather than only in the browser.
 *
 * The design suite measures what a screen actually rendered, which is the
 * real answer but only for the pairs that happened to be on screen. This
 * measures the palette itself: it is the file that says a colour may be used
 * for text, and it should be the file that fails when one cannot.
 */
describe('day palette contrast', () => {
  const colors = palette()

  it('reads the palette out of the stylesheet', () => {
    expect(Object.keys(colors)).toEqual(
      expect.arrayContaining([
        'bg',
        'card',
        'fg',
        'muted',
        'line',
        'school',
        'festival',
        'holiday',
        'good',
        ...MEANINGS.map((name) => `tint-${name}`),
        ...MEANINGS.map((name) => `ink-${name}`),
      ]),
    )
  })

  it('clears AA for the two inks that are not a meaning', () => {
    for (const name of ['fg', 'muted']) {
      expect(ratio(colors[name], colors.bg), `${name} on bg`).toBeGreaterThanOrEqual(AA)
      expect(ratio(colors[name], colors.card), `${name} on card`).toBeGreaterThanOrEqual(AA)
    }
  })

  it('clears AA for every meaning in its ink form', () => {
    // On the page and on a card both: --bg is a shade under --card, so a
    // colour can clear on a card and fail on the wall behind it.
    for (const name of [...MEANINGS, 'good', 'bad']) {
      const ink = colors[`ink-${name}`]
      expect(ratio(ink, colors.bg), `ink-${name} on bg`).toBeGreaterThanOrEqual(AA)
      expect(ratio(ink, colors.card), `ink-${name} on card`).toBeGreaterThanOrEqual(AA)
    }
  })

  it('refuses the raw colours as text, which is why the inks exist', () => {
    // Not a rule so much as the evidence for one. --festival is 2.3:1, and
    // both sample kid colours are under AA: if one ever clears it on its
    // own, the ink layer may not be needed for it any more.
    expect(ratio(colors.festival, colors.card)).toBeLessThan(AA)
    for (const colour of Object.values(KIDS)) {
      expect(ratio(colour, colors.card)).toBeLessThan(AA)
    }
  })

  it('carries the page ink on every tint', () => {
    for (const name of MEANINGS) {
      expect(ratio(colors.fg, colors[`tint-${name}`]), `fg on tint-${name}`).toBeGreaterThanOrEqual(
        AA,
      )
    }
  })

  it('leaves no tint that white could be written on', () => {
    // The rule is "never white on a tint", and this is why: every tint is
    // within a ratio of 1.2 of white, so white on one is not dim, it is gone.
    for (const name of MEANINGS) {
      expect(ratio('#ffffff', colors[`tint-${name}`]), `white on tint-${name}`).toBeLessThan(1.2)
    }
  })

})

/**
 * Each child's colour, through the same code the kiosk runs (kidPalette.ts):
 * the ink reads on the page and on a card, the page's ink reads on the tint,
 * white never does, and a waiting chip's words read on the tint.
 */
describe('a kid colour, as the kiosk derives it', () => {
  const colors = palette()

  for (const [id, colour] of Object.entries(KIDS)) {
    const paper = kidPaper(colour)

    it(`derives every form for ${id}`, () => {
      expect(paper).not.toBeNull()
    })

    it(`clears AA for ${id}'s ink on the page and on a card`, () => {
      expect(ratio(paper!.ink, colors.bg)).toBeGreaterThanOrEqual(AA)
      expect(ratio(paper!.ink, colors.card)).toBeGreaterThanOrEqual(AA)
    })

    it(`carries the page ink on ${id}'s tint, and never white`, () => {
      expect(ratio(colors.fg, paper!.tint)).toBeGreaterThanOrEqual(AA)
      expect(ratio('#ffffff', paper!.tint)).toBeLessThan(1.2)
    })

    it(`clears AA-large for ${id}'s ink on their own tint, and AA for a waiting chip`, () => {
      // The band across an open card and the initial on an avatar are
      // display sizes; a waiting chip's words are body text.
      expect(ratio(paper!.ink, paper!.tint)).toBeGreaterThanOrEqual(AA_LARGE)
      expect(ratio(paper!.chipInk, paper!.tint)).toBeGreaterThanOrEqual(AA)
    })
  }
})
