import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import Illustration, { type Drawing } from './Illustration'

/** Every drawing the set offers. A new one added here fails until it draws. */
const ALL: Drawing[] = ['kite', 'cat', 'plate', 'sun', 'moon', 'party', 'backpack']

describe('the drawings', () => {
  it.each(ALL)('draws %s inline, with both tones', (name) => {
    const html = renderToStaticMarkup(<Illustration name={name} size={44} />)

    // Inline, not a file: the design doc asked for /illustrations/*.svg and
    // this set is deliberately not that, because an empty state is drawn in
    // the kid's colour and an <img> cannot inherit currentColor. So the
    // check that matters is that the shapes are in the document.
    expect(html).toContain('<svg')
    expect(html).not.toContain('<img')
    expect(html).toContain('currentColor')
    // The wash under the line work, at 14%.
    expect(html).toContain('opacity="0.14"')
  })

  it('asks for nothing over the network', () => {
    const every = ALL.map((name) => renderToStaticMarkup(<Illustration name={name} size={44} />))

    // The iPad may be offline for minutes at a time; a drawing that needs a
    // round trip is a drawing that is sometimes a gap.
    for (const html of every) {
      expect(html).not.toMatch(/src=|href=|url\(/)
    }
  })

  it('is drawn at the size it is asked for', () => {
    const html = renderToStaticMarkup(<Illustration name="kite" size={44} />)

    expect(html).toContain('width="44"')
    expect(html).toContain('height="44"')
  })
})
