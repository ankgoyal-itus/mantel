import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Photo, Weather } from '../../api/types'
import FrameScreen from '../FrameScreen'
import { WEATHER } from '../day/fixtures'
import { BRIGHT_ABOVE, brightEnd } from './brightness'

/** The done-when's afternoon: 5:12 pm, 89° now, 92° / 58°. */
const HOT: Weather = {
  ...WEATHER,
  now: { temp: 89, label: 'Clear', icon: 'clear', is_day: true },
  today: { ...WEATHER.today!, high: 92, low: 58 },
  tomorrow: { ...WEATHER.tomorrow!, high: 77, low: 56 },
}

const PHOTO: Photo = {
  id: 'p1',
  url: '/photos/p1.jpg',
  taken_at: '2024-06-01T10:00:00',
  place: 'Lake Tahoe',
} as Photo

function render(props: Partial<Parameters<typeof FrameScreen>[0]> = {}): string {
  return renderToStaticMarkup(
    <FrameScreen photos={[PHOTO]} slideSeconds={20} night={false} weather={HOT} {...props} />,
  )
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date(2026, 8, 29, 17, 12))
})

afterEach(() => {
  vi.useRealTimers()
})

describe('the chip on the frame', () => {
  it('says the time, the temperature, and the high and low', () => {
    const html = render()
    const chip = html.slice(html.indexOf('frame-chip'))
    expect(chip).toContain('5:12<span class="frame-chip-meridiem">pm</span>')
    expect(chip).toContain('frame-chip-temp">89°<')
    expect(chip).toContain('frame-chip-range">92° / 58°<')
    // The month stays in its corner; the small clock there goes.
    expect(html).toContain('frame-when')
    expect(html).not.toContain('frame-clock')
  })

  it('at night steps back and reads tomorrow', () => {
    const html = render({ night: true })
    expect(html).toContain('frame-chip frame-chip-night')
    expect(html).toContain('Tomorrow 77° / 56°')
  })

  it('says since when when the weather is old', () => {
    const stale = { ...HOT, stale: true, fetched_at: '2026-09-29T06:08:00' }
    expect(render({ weather: stale })).toContain('since 6:08')
  })

  it('goes when the setting is off, and the corner clock comes back', () => {
    const html = render({ chip: false })
    expect(html).not.toContain('frame-chip')
    expect(html).toContain('frame-clock')
  })

  it('comes large for the far side of the room', () => {
    expect(render({ chipLarge: true })).toContain('frame-chip-large')
  })
})

describe('the corner under it', () => {
  const pixels = (value: number, count = 100) =>
    Array.from({ length: count * 4 }, (_, index) => (index % 4 === 3 ? 255 : value))

  it('measures the bright end, not the average', () => {
    // Ninety dark pixels and ten of white sky: bright, because of the sky.
    const mixed = [...pixels(20, 89), ...pixels(255, 11)]
    expect(brightEnd(mixed)).toBeGreaterThan(BRIGHT_ABOVE)
    expect(brightEnd(pixels(20))).toBeLessThan(BRIGHT_ABOVE)
  })

  it('switches where the frosted pill stops carrying the numbers', () => {
    // Grey 116 is the brightest corner the 0.34 pill still reads on.
    expect(brightEnd(pixels(116))).toBeLessThanOrEqual(BRIGHT_ABOVE)
    expect(brightEnd(pixels(130))).toBeGreaterThan(BRIGHT_ABOVE)
  })
})
