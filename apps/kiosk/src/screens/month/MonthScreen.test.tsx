import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import MonthScreen, { barsFor, dotsFor, tithiLabel } from '../MonthScreen'
import { NAVRATRI_DAY, OCTOBER } from './fixtures'
import { cellsFor, isHatched, masaLine, monthName, shiftMonth, weeksIn } from './grid'

const KID_COLOURS = { mira: '#1F8A8A', kabir: '#D97706' }

/** Rendered with the month already in hand: effects do not run here. */
function render(day: typeof NAVRATRI_DAY | null = null, panchang = false): string {
  return renderToStaticMarkup(
    <MonthScreen
      initialYm="2026-10"
      today="2026-10-11"
      kidColours={KID_COLOURS}
      onDone={() => {}}
      months={{ '2026-10': OCTOBER }}
      day={day}
      panchang={panchang}
    />,
  )
}

describe('the month grid', () => {
  it('renders October 2026', () => {
    expect(render()).toMatchSnapshot()
  })

  it('lays out only the weeks the month needs', () => {
    // October 2026 opens on a Thursday and runs 31 days: five weeks.
    expect(weeksIn('2026-10')).toBe(5)
    expect(cellsFor('2026-10', []).length).toBe(35)
    // May 2027 opens on a Saturday: six.
    expect(weeksIn('2027-05')).toBe(6)
    // February 2026 opens on a Sunday and has 28 days: exactly four.
    expect(weeksIn('2026-02')).toBe(4)
  })

  it('draws October in five rows', () => {
    expect(render()).toContain('grid-template-rows:repeat(5, 1fr)')
  })

  it('has a legend under the grid', () => {
    const drawn = render()
    expect(drawn).toContain('mo-legend')
    for (const word of ['Family', 'No school', 'Festival', 'Holiday', 'Veg', 'New moon', 'Full moon']) {
      expect(drawn).toContain(`>${word}<`)
    }
  })

  it('starts each week on Sunday', () => {
    const cells = cellsFor('2026-10', [])
    // 1 October 2026 is a Thursday, so the grid opens on 27 September.
    expect(cells[0].date).toBe('2026-09-27')
    expect(cells[0].inMonth).toBe(false)
    expect(cells[4].date).toBe('2026-10-01')
    expect(cells[4].inMonth).toBe(true)
  })

  it('names the month and its masa', () => {
    expect(monthName('2026-10')).toBe('October 2026')
    expect(masaLine(OCTOBER.days, 2083)).toBe('Ashwin · Vikram Samvat 2083')
    expect(masaLine(OCTOBER.days, null)).toBe('Ashwin')
  })

  it('pages between months, across a year boundary', () => {
    expect(shiftMonth('2026-10', 1)).toBe('2026-11')
    expect(shiftMonth('2026-12', 1)).toBe('2027-01')
    expect(shiftMonth('2026-01', -1)).toBe('2025-12')
  })

  it('hatches a weekday with no school, and leaves the weekend alone', () => {
    const noSchool = { is_school_day: false, note: null }
    const weekday = { ...OCTOBER.days[0], weekday: 'wed' as const, school: noSchool }
    const weekend = { ...OCTOBER.days[0], weekday: 'sat' as const, school: noSchool }
    expect(isHatched(weekday)).toBe(true)
    expect(isHatched(weekend)).toBe(false)
    expect(isHatched({ ...weekday, school: { is_school_day: true, note: null } })).toBe(false)
    expect(isHatched(null)).toBe(false)
  })
})

describe('what a cell shows', () => {
  const html = render()

  it('names the day in family mode, rather than its almanac shorthand', () => {
    // The default is the calendar a family reads: what makes the day special.
    // One word of it, though — the full name is in the panel, and a cell is
    // 90px across.
    expect(html).toContain('>Navratri<')
    expect(html).toContain('>Dussehra<')
    expect(html).not.toContain('First Day of Sharad Navratri')
    expect(html).not.toContain('>S1<')
    expect(html).not.toContain('mo-moon')
  })

  it('keeps a cell to one word and one dot', () => {
    // Two observances on a day is still one word; the almanac's leaf and
    // tithi belong to panchang mode, and everything else to the panel.
    expect(html).not.toContain('mo-leaf')
    expect(html).not.toContain('mo-tithi')
    // The busiest cell in the fixture carries exactly one dot.
    const busiest = html.slice(html.indexOf('>20<'))
    const cell = busiest.slice(0, busiest.indexOf('</button>'))
    expect(cell.match(/mo-dot"/g) ?? []).toHaveLength(1)
  })

  it('shows the tithi and the moons once panchang is on', () => {
    const almanac = render(null, true)
    expect(almanac).toContain('>Pratipada ◑<')
    expect(almanac).toContain('>Dwadashi ◑<')
    expect(almanac).toContain('>Amavasya ◐<')
    expect(almanac).not.toContain('>S12')
    expect(almanac).toContain('mo-moon')
  })

  it('offers the toggle either way', () => {
    expect(html).toContain('Panchang')
    expect(render(null, true)).toContain('mo-toggle-on')
  })

  it('leafs a vegetarian day, in the mode that is about food rules', () => {
    // The leaf came off the family grid with the rest of the shorthand: a
    // veg day is in the panel, and in the almanac view where it belongs.
    expect(render(null, true)).toContain('mo-leaf')
  })

  it('outlines today', () => {
    expect(html).toContain('mo-today')
  })

  it('hatches the days school is out', () => {
    expect(html).toContain('mo-noschool')
  })

  it('dims the days either side of the month', () => {
    expect(html).toContain('mo-out')
  })

  it('offers a way out', () => {
    expect(html).toContain('Done')
  })
})

describe('the day panel', () => {
  const html = render(NAVRATRI_DAY)

  it('names the festival', () => {
    expect(html).toContain('First Day of Sharad Navratri')
  })

  it('gives the tithi with the time it ends', () => {
    expect(html).toContain('Pratipada')
    expect(html).toContain('shukla')
    expect(html).toContain('9:01 am')
  })

  it('gives the masa and the samvat', () => {
    expect(html).toContain('Ashwin')
    expect(html).toContain('Vikram Samvat 2083')
  })

  it('says why it is a vegetarian day', () => {
    expect(html).toContain('veg day')
    // The panel reads the same words the wall does.
    expect(html).toContain('Sharad Navratri · day 1 of 10')
  })

  it('shows the school status and the meals planned', () => {
    expect(html).toContain('No school')
    expect(html).toContain('Kanda poha')
    expect(html).toContain('Dal and jeera rice')
  })

  it('leaves yoga and karana out while the setting is off', () => {
    expect(html).not.toContain('Vishkambha')
  })

  it('makes room for itself', () => {
    expect(html).toContain('month-with-panel')
    expect(render()).not.toContain('mo-panel')
  })
})

describe('the marks', () => {
  const colours = { mira: '#1F8A8A', kabir: '#D97706' }
  const base = OCTOBER.days[0]

  it('dots a festival amber and a holiday purple', () => {
    expect(dotsFor({ ...base, observances: ['Dussehra'] })).toEqual(['var(--festival)'])
    expect(dotsFor({ ...base, observances: ['Columbus Day'], holiday: true })).toEqual([
      'var(--holiday)',
    ])
  })

  it('dots the family grey', () => {
    expect(dotsFor({ ...base, family: true })).toEqual(['var(--muted)'])
  })

  it('does not dot an ordinary school day', () => {
    // Four days in five are school days; dotting them all says nothing.
    expect(dotsFor({ ...base, school: { is_school_day: true, note: null } })).toEqual([])
  })

  it('gives each kid with something on a bar in their colour, in family order', () => {
    expect(barsFor({ ...base, kids: ['kabir'] }, colours)).toEqual(['#D97706'])
    expect(barsFor({ ...base, kids: ['kabir'], school_kids: ['mira'] }, colours)).toEqual([
      '#1F8A8A',
      '#D97706',
    ])
  })

  it('shortens the tithi, keeping the glyph, when the panel narrows the cell', () => {
    expect(tithiLabel({ ...base, tithi_name: 'Dwadashi', paksha: 'shukla' }, true)).toBe('Dwad ◑')
    expect(tithiLabel({ ...base, tithi_name: 'Chaturdashi', paksha: 'krishna' }, true)).toBe(
      'Chaturd ◐',
    )
    expect(tithiLabel({ ...base, tithi_name: 'Amavasya', paksha: 'krishna' }, true)).toBe('Amavas ◐')
  })

  it('names the tithi with the paksha glyph', () => {
    expect(tithiLabel({ ...base, tithi_name: 'Dwadashi', paksha: 'shukla' })).toBe('Dwadashi ◑')
    expect(tithiLabel({ ...base, tithi_name: 'Shashthi', paksha: 'krishna' })).toBe('Shashthi ◐')
  })
})
