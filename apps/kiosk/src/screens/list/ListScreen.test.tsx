import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { Day, Kid } from '../../api/types'
import ListScreen from '../ListScreen'
import { TODAY, TOMORROW } from '../day/fixtures'
import type { Filter } from './rows'

const KIDS: Kid[] = [
  { id: 'mira', name: 'Mira', color: '#1F8A8A', avatar: 'fox' },
  { id: 'kabir', name: 'Kabir', color: '#D97706', avatar: 'panda' },
]

/** The Tuesday fixture, plus a school event and the festival on tomorrow. */
const WITH_SCHOOL: Day = {
  ...TODAY,
  kids: TODAY.kids.map((kid) =>
    kid.id === 'mira'
      ? {
          ...kid,
          agenda: [
            ...kid.agenda,
            {
              start: '15:00',
              end: '17:00',
              title: 'Cross Country meet',
              where: 'Bayside Middle',
              note: null,
              source: 'school',
              source_kind: 'school',
              all_day: false,
              calendar_id: 'bayside',
            },
          ],
        }
      : kid,
  ),
}

function render(filters: Filter[] = []): string {
  return renderToStaticMarkup(
    <ListScreen
      agenda={[WITH_SCHOOL, TOMORROW]}
      kids={KIDS}
      today="2026-09-29"
      filters={filters}
      onDone={() => {}}
      onShowMonth={() => {}}
    />,
  )
}

describe('the list', () => {
  it('renders the next days', () => {
    expect(render()).toMatchSnapshot()
  })

  it('shows every calendar at once', () => {
    const html = render()
    expect(html).toContain('Piano')
    expect(html).toContain('Cross Country meet')
    expect(html).toContain('Swim')
    expect(html).toContain('Dinner with grandparents')
    expect(html).toContain('Diwali/Deepavali')
  })

  it('marks a school row with the glyph and its place', () => {
    const html = render()
    expect(html).toContain('li-glyph')
    expect(html).toContain('Bayside Middle')
  })

  it('filters down to one person', () => {
    const html = render(['mira'])
    expect(html).toContain('Piano')
    expect(html).not.toContain('Swim')
    expect(html).not.toContain('Dinner with grandparents')
  })

  it('offers a chip per calendar, and All', () => {
    const html = render()
    for (const label of ['All', 'Mira', 'Kabir', 'Family', 'School', 'Festivals', 'Holidays']) {
      expect(html).toContain(label)
    }
  })

  it('has a way back to the month and a way out', () => {
    const html = render()
    expect(html).toContain('Month')
    expect(html).toContain('Done')
  })

  it('says so when a filter leaves nothing', () => {
    const html = renderToStaticMarkup(
      <ListScreen
        agenda={[]}
        kids={KIDS}
        today="2026-09-29"
        onDone={() => {}}
        onShowMonth={() => {}}
      />,
    )
    expect(html).toContain('Nothing in the next 60 days')
  })
})

describe('the weekend', () => {
  it('does not say "No school" on a Saturday or a Sunday', () => {
    const sunday: Day = { ...TODAY, weekday: 'sun', is_school_day: false, school_note: null }
    const html = renderToStaticMarkup(
      <ListScreen
        agenda={[sunday]}
        kids={KIDS}
        today="2026-09-29"
        onDone={() => {}}
        onShowMonth={() => {}}
      />,
    )
    expect(html).not.toContain('No school')
    // Each row starts with a face or the family's glyph.
    expect(html).toContain('li-who')
  })
})
