import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import WeatherIcon from './WeatherIcon'

const ICONS = ['clear', 'partly', 'cloudy', 'fog', 'drizzle', 'rain', 'snow', 'storm']

function render(icon: string, night = false): string {
  return renderToStaticMarkup(<WeatherIcon icon={icon} night={night} />)
}

describe('weather icons', () => {
  it('draws all eight keys, and each one differently', () => {
    const drawn = ICONS.map((icon) => render(icon))
    expect(new Set(drawn).size).toBe(ICONS.length)
    for (const markup of drawn) {
      expect(markup).toContain('<svg')
    }
  })

  it('has a night face for clear and partly', () => {
    expect(render('clear', true)).not.toBe(render('clear'))
    expect(render('partly', true)).not.toBe(render('partly'))
  })

  it('leaves the rest alone after dark, because rain looks the same at midnight', () => {
    for (const icon of ['cloudy', 'fog', 'drizzle', 'rain', 'snow', 'storm']) {
      expect(render(icon, true)).toBe(render(icon))
    }
  })

  it('falls back rather than drawing nothing', () => {
    expect(render('sandstorm')).toBe(render('cloudy'))
  })
})
