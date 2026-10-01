import { describe, expect, it } from 'vitest'

import { kidPaletteCss } from './kidPalette'

describe('the kid palette', () => {
  const css = kidPaletteCss([
    { id: 'mira', color: '#1F8A8A' },
    { id: 'kabir', color: '#D97706' },
  ])

  it('writes every form of every child by day', () => {
    const day = css.slice(0, css.indexOf('}'))
    for (const id of ['mira', 'kabir']) {
      for (const form of ['kid', 'shade', 'tint', 'ink', 'chip-ink']) {
        expect(day).toContain(`--${form}-${id}:`)
      }
    }
    expect(day).toContain('--kid-mira: #1F8A8A;')
  })

  it('keys the night forms on the same attribute as theme.css', () => {
    const night = css.slice(css.indexOf("html[data-theme='night']"))
    expect(night).toContain('--shade-kabir: color-mix(in srgb, var(--kid-kabir), white 45%);')
    expect(night).toContain('--ink-mira: var(--shade-mira);')
  })

  it('skips an id it cannot write into a property name, and a colour it cannot read', () => {
    expect(kidPaletteCss([{ id: 'a b;}', color: '#123456' }])).toBe('')
    expect(kidPaletteCss([{ id: 'ok', color: 'teal' }])).toBe('')
  })
})
