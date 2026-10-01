import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import Illustration, { ILLUSTRATIONS } from '../illustrations/Illustration'
import Icon, { ICONS } from './Icon'

describe('the one line set', () => {
  it('draws every icon at 1.75px, whatever size it is shown at', () => {
    for (const name of ICONS) {
      const svg = renderToStaticMarkup(<Icon name={name} size={20} />)
      expect(svg, name).toContain('stroke-width="1.75"')
      expect(svg, name).toContain('vector-effect="non-scaling-stroke"')
    }
  })

  it('draws every illustration in the same line', () => {
    for (const name of ILLUSTRATIONS) {
      const svg = renderToStaticMarkup(<Illustration name={name} size={32} />)
      expect(svg, name).toContain('stroke-width="1.75"')
      expect(svg, name).toContain('vector-effect="non-scaling-stroke"')
    }
  })
})
