import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Day } from '../../api/types'
import NightScreen from '../NightScreen'
import { TODAY, TOMORROW, WEATHER } from '../day/fixtures'

/** Local wall-clock on Tuesday 29 September 2026, inside the night window. */
function renderAt(hour: number, minute = 0, day: Day = TOMORROW): string {
  vi.setSystemTime(new Date(2026, 8, 29, hour, minute, 0, 0))
  return renderToStaticMarkup(
    <NightScreen today={TODAY} tomorrow={day} weather={WEATHER} nightEnd="06:30" />,
  )
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('the night screen', () => {
  it('renders the night', () => {
    expect(renderAt(22, 0)).toMatchSnapshot()
  })

  it('shows the clock with am/pm and the date under it', () => {
    const html = renderAt(22, 0)
    expect(html).toContain('10:00')
    expect(html).toContain('night-ampm">pm')
    expect(html).toContain('29 September')
  })

  it('reads the weather in two lines', () => {
    const html = renderAt(22, 0)
    expect(html).toContain('Partly cloudy · 68° now')
    // Rain is stated whatever the odds here; the day screen hides the small ones.
    expect(html).toContain('Tomorrow 74° / 52° · rain 10% · sunrise 7:00')
  })

  it('lists tomorrow per kid, with the family last', () => {
    const html = renderAt(22, 0)
    expect(html).toContain('No school')
    expect(html.indexOf('Mira')).toBeLessThan(html.indexOf('Kabir'))
    expect(html.indexOf('Kabir')).toBeLessThan(html.indexOf('Family'))
    expect(html).toContain('10:30 am Dentist')
    expect(html).toContain('5:00 pm Swim')
  })

  it('says so when a kid has nothing on', () => {
    const quiet: Day = { ...TOMORROW, kids: TOMORROW.kids.map((kid) => ({ ...kid, agenda: [] })) }
    expect(renderAt(22, 0, quiet)).toContain('Nothing scheduled')
  })

  it('packs tomorrow’s breakfast and lunch, with their notes', () => {
    const html = renderAt(22, 0)
    expect(html).toContain('Pack')
    expect(html).toContain('Pancakes')
    expect(html).toContain('Dal and rice')
    expect(html).toContain('lunchbox')
    // Dinner is nobody's problem at bedtime.
    expect(html).not.toContain('Dinner')
  })

  it('says nothing is packed yet when both slots are empty', () => {
    const unplanned: Day = {
      ...TOMORROW,
      meals: { breakfast: null, lunch: null, dinner: null, snack: null },
    }
    const html = renderAt(22, 0, unplanned)
    expect(html).toContain('>Pack<')
    expect(html).toContain('Nothing packed yet')
  })

  it('shows the coming morning, not the day after it, in the small hours', () => {
    // 05:00 is still the night window, but "tomorrow" by then is a day too far:
    // what matters is the breakfast a few hours away, which is TODAY's payload.
    const html = renderAt(5, 0)
    expect(html).toContain('Today')
    expect(html).toContain('Oatmeal') // TODAY's breakfast
    expect(html).not.toContain('Pancakes') // TOMORROW's
  })
})

describe('dinner out', () => {
  it('puts it on the pack list with the place', () => {
    const out: Day = {
      ...TOMORROW,
      meals: {
        ...TOMORROW.meals,
        dinner: {
          name: 'Dinner out',
          id: 'dinner_out',
          note: 'Taqueria Luna',
          kids_protein: 'veg',
          picked_by: [],
          confirmed: true,
        },
      },
    }
    expect(renderAt(22, 0, out)).toContain('Dinner out · Taqueria Luna')
  })
})

describe('a Saturday tomorrow', () => {
  it('does not say "No school"', () => {
    const saturday: Day = { ...TOMORROW, weekday: 'sat', is_school_day: false, school_note: null }
    expect(renderAt(22, 0, saturday)).not.toContain('No school')
  })
})
