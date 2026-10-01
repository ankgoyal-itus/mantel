import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import PinPad from '../screens/parent/PinPad'
import Keypad from './Keypad'

const never = () => new Promise<never>(() => undefined)

describe('the keypad', () => {
  it('is one component for a parent and a kid, with four dots and twelve places', () => {
    const parent = renderToStaticMarkup(<PinPad onOpen={() => undefined} onCancel={() => undefined} />)
    const kid = renderToStaticMarkup(
      <Keypad
        variant="kid"
        title={<span className="keypad-name">Mira</span>}
        caption="Your code"
        submit={never}
        onOpen={() => undefined}
        onCancel={() => undefined}
      />,
    )
    for (const [html, variant] of [
      [parent, 'parent'],
      [kid, 'kid'],
    ] as const) {
      expect(html).toContain(`class="pin keypad keypad-${variant}"`)
      expect(html.match(/class="pin-dot"/g)).toHaveLength(4)
      expect(html.match(/class="pin-key[ "]/g)).toHaveLength(11)
      expect(html).toContain('class="pin-go" disabled="">Open<')
      expect(html).toContain('class="pin-text">Cancel<')
    }
    expect(parent).toContain('pin-lock')
    expect(parent).toContain('Parents only')
    expect(parent).toContain('class="pin-prompt">Enter the PIN<')
    expect(kid).toContain('class="pin-prompt">Your code<')
    expect(kid).toContain('keypad-name">Mira<')
  })
})
