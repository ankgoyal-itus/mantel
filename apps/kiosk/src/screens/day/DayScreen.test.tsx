import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Weekday } from '../../api/types'
import DayScreen from '../DayScreen'
import { LONG_DAY, TODAY, TOMORROW, WEATHER, meal, task } from './fixtures'

/** Tuesday 29 September 2026, local. */
function renderAt(hour: number, minute: number, height = 768): string {
  vi.setSystemTime(new Date(2026, 8, 29, hour, minute, 0, 0))
  return renderToStaticMarkup(
    <DayScreen today={TODAY} tomorrow={TOMORROW} weather={WEATHER} height={height} />,
  )
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('the day screen', () => {
  it('renders the morning', () => {
    expect(renderAt(7, 30)).toMatchSnapshot()
  })

  it('renders the afternoon', () => {
    expect(renderAt(15, 30)).toMatchSnapshot()
  })

  it('renders the evening', () => {
    expect(renderAt(20, 30)).toMatchSnapshot()
  })

  it('dims what is over and accents what is next', () => {
    // Half past seven, where Assembly is still ahead. Upright, where the
    // card has room for all three agenda rows over its to-dos.
    const html = renderAt(7, 30, 1024)

    // The row, not the headline: the next item is named up there too now.
    const assembly = html.indexOf('row-title clamp-1">Assembly')
    expect(assembly).toBeGreaterThan(-1)
    expect(html.slice(0, assembly)).toContain('row-dot-on')

    // One accent on the screen, not one per item.
    expect(html.match(/row-dot-on/g)).toHaveLength(1)

    // And what is over is demoted rather than accented.
    const afternoon = renderAt(15, 30, 1024)
    const done = afternoon.indexOf('row-title clamp-1">Assembly')
    expect(afternoon.slice(0, done)).toContain('row row-past')
  })

  it('turns the evening over to tomorrow', () => {
    const evening = renderAt(20, 30)
    expect(evening).toContain('Tonight')

    const afternoon = renderAt(15, 30)
    expect(afternoon).toContain('Tuesday')
  })

  it('stands today and tomorrow side by side under the children', () => {
    // Tomorrow used to be a column wedged in beside the kids that widened at
    // six. A family asks the wall two questions — what is on now and what is
    // on next — so both days are cards of the same size at the foot of it.
    const html = renderAt(15, 30)

    expect(html.indexOf('day-kids')).toBeLessThan(html.indexOf('day-bottom'))
    expect(html.match(/dp-card/g)).toHaveLength(2)
    expect(html).toContain('Tomorrow')

    // Tomorrow says which day it is; today does not need to.
    expect(html).toContain('Wed 30 Sep')
  })

  it('keeps the header to three sizes', () => {
    // The finding cut rain from the header: the glyph, the temperature and
    // the high/low are all it carries now.
    const html = renderAt(7, 30)
    expect(html).toContain('79° / 56°')
    expect(html).not.toContain('rain')
  })

  it('says how the kids eat a two-ways meal when there is no note instead', () => {
    // The note is what a parent wrote, so it wins the one place there is.
    expect(renderAt(15, 30)).toContain('chicken tikka for the kids')

    const plain = {
      ...TODAY,
      meals: { ...TODAY.meals, dinner: meal('Paneer tikka', { kids_protein: 'chicken' }) },
    }
    vi.setSystemTime(new Date(2026, 8, 29, 15, 30))
    const html = renderToStaticMarkup(<DayScreen today={plain} tomorrow={null} weather={WEATHER} />)
    expect(html).toContain('Kids eat chicken')
    // Veg slots say nothing about it.
    expect(html.match(/Kids eat/g)).toHaveLength(1)
  })

  it('draws the weather from the bundled icon set', () => {
    const html = renderAt(15, 30)
    expect(html).toContain('wx-icon')
    expect(html).toContain('stroke-width="1.75"')
  })

  it('tags a vegetarian day with the festival that made it one', () => {
    const festival = {
      ...TODAY,
      diet: { non_veg_ok: false, reasons: ['Dussehra'] },
    }
    vi.setSystemTime(new Date(2026, 8, 29, 7, 30))
    const html = renderToStaticMarkup(
      <DayScreen today={festival} tomorrow={TOMORROW} weather={WEATHER} />,
    )
    expect(html).toContain('Veg day')
    expect(html).toContain('Dussehra')

    // A plain Tuesday needs no tag: that rule is not news to anyone.
    expect(renderAt(7, 30)).not.toContain('veg day')
  })

  it('says tomorrow in one head line: the day, the weather and the chips', () => {
    const html = renderAt(15, 30)
    const head = html.slice(html.lastIndexOf('dp-head'))
    expect(head).toContain('>Tomorrow<')
    expect(head).toContain('· Wed 30 Sep')
    expect(head).toContain('74° / 52°')
    expect(head).toContain('dp-chip dp-chip-school clamp-1">No school<')
    // The family's library trip and one row for each child.
    expect(head).toContain('>3 events<')
    // No agenda list in either card any more.
    expect(html).not.toContain('dp-list')
  })

  it('says something specific where there is nothing', () => {
    const html = renderAt(7, 30)
    expect(html).toContain('Free afternoon') // Kabir has no agenda today
    expect(html).toContain('Mira: no tomato') // the lunch note
    expect(html).toContain('No school') // tomorrow is a day off
  })

  it('draws the free afternoon rather than only saying it', () => {
    const html = renderAt(7, 30)
    const empty = html.slice(html.indexOf('empty empty-drawn'))

    // The kite, above the words, in the kid's colour. It is inline SVG and
    // not /illustrations/kite.svg, because an <img> cannot inherit
    // currentColor — which docs/later.md records.
    expect(empty).toContain('M24 6 38 22 24 38 10 22Z')
    expect(empty.indexOf('<svg')).toBeLessThan(empty.indexOf('Free afternoon'))
    expect(html).not.toContain('/illustrations/')
  })

  it('greets the children in the morning and at bedtime, and not in between', () => {
    // The two windows a child is actually in front of this screen. Named,
    // and in the order family.yaml lists them.
    expect(renderAt(7, 30)).toContain('Good morning, Mira and Kabir')
    expect(renderAt(20, 30)).toContain('Good night')

    const afternoon = renderAt(15, 0)
    expect(afternoon).not.toContain('Good morning')
    expect(afternoon).not.toContain('Good night')
  })

  it('keeps an empty meal slot as a muted dash', () => {
    // Three rows every day, so an unplanned lunch reads as a gap to fill
    // rather than a card that forgot it.
    const noLunch = { ...TODAY, meals: { ...TODAY.meals, lunch: null } }
    vi.setSystemTime(new Date(2026, 8, 29, 7, 30))
    // Tomorrow off, so the only meals on screen are the ones being asserted.
    const html = renderToStaticMarkup(
      <DayScreen today={noLunch} tomorrow={null} weather={WEATHER} />,
    )
    expect(html.match(/class="dp-meal"/g)).toHaveLength(3)
    expect(html).toContain('Lunch</span><span class="meal-name dp-meal-empty">—')
  })

  it('draws three dashes when nothing is planned at all', () => {
    const nothing = {
      ...TODAY,
      meals: { breakfast: null, lunch: null, dinner: null, snack: null },
    }
    vi.setSystemTime(new Date(2026, 8, 29, 7, 30))
    const html = renderToStaticMarkup(
      <DayScreen today={nothing} tomorrow={null} weather={WEATHER} />,
    )
    expect(html.match(/dp-meal-empty/g)).toHaveLength(3)
    expect(html).not.toContain('No meals planned')
  })

  it('draws the meals as lines, in the order they are eaten', () => {
    const html = renderAt(15, 30)
    const today = html.slice(html.indexOf('dp-card'), html.lastIndexOf('dp-card'))
    expect(today.match(/class="dp-meal"/g)).toHaveLength(3)
    expect(today.indexOf('Breakfast')).toBeLessThan(today.indexOf('Lunch'))
    expect(today.indexOf('Lunch')).toBeLessThan(today.indexOf('Dinner'))
    // The note takes the room over, and is not drawn under 120px of it.
    expect(today).toContain('hide-under-120"><span class="dp-meal-note clamp-1">Mira: no tomato')
  })

  it('puts the face of whoever picked a meal on the end of its line', () => {
    const picked = {
      ...TODAY,
      meals: {
        ...TODAY.meals,
        dinner: meal('Pizza night', { picked_by: ['kabir'], id: 'pizza_night' }),
      },
    }
    vi.setSystemTime(new Date(2026, 8, 29, 15, 30))
    const html = renderToStaticMarkup(<DayScreen today={picked} tomorrow={null} weather={WEATHER} />)
    const dinner = html.slice(html.indexOf('Pizza night'))
    expect(dinner).toContain('dp-pick')
    expect(dinner).toContain('data-avatar="panda"')

    // Both, when both picked it.
    const both = { ...picked.meals.dinner!, picked_by: ['kabir', 'mira'] }
    const twice = renderToStaticMarkup(
      <DayScreen
        today={{ ...picked, meals: { ...picked.meals, dinner: both } }}
        tomorrow={null}
        weather={WEATHER}
      />,
    )
    expect(twice.match(/class="dp-pick"/g)).toHaveLength(2)

    // Two different dishes: both faces still, and who decides.
    const contested = {
      ...both,
      confirmed: false,
      picks: { kabir: { id: 'pizza_night' }, mira: { id: 'tacos' } },
    }
    const html2 = renderToStaticMarkup(
      <DayScreen
        today={{ ...picked, meals: { ...picked.meals, dinner: contested } }}
        tomorrow={null}
        weather={WEATHER}
      />,
    )
    expect(html2.match(/class="dp-pick"/g)).toHaveLength(2)
    expect(html2).toContain('dp-decide">Mom or Dad picks<')
  })

  it('draws the to-dos as chips, routine order then task order, with no headers', () => {
    const html = renderAt(7, 30)
    const mira = html.slice(html.indexOf('data-kid-card="mira"'), html.indexOf('data-kid-card="kabir"'))
    expect(mira).toContain('<ul class="chips')
    expect(mira.match(/<li class="chip-task /g)).toHaveLength(TODAY.kids[0].tasks.length)
    // No routine headers, and nothing folded away.
    expect(html).not.toContain('task-group')
    expect(html).not.toContain('routine-line')
    expect(html).not.toContain('task-more')
    // Each open to-do says what it is worth.
    expect(html).toMatch(/chip-task-worth">\+\d+</)
  })

  it('puts a chip in routine order, then task order', () => {
    const today = {
      ...TODAY,
      kids: [
        {
          ...TODAY.kids[0],
          tasks: [
            task('dishes', 'Dishes', { routine: 'evening' }),
            task('teeth', 'Teeth', { routine: 'morning' }),
            task('hw', 'Homework'),
          ],
        },
        TODAY.kids[1],
      ],
    }
    vi.setSystemTime(new Date(2026, 8, 29, 7, 30))
    const html = renderToStaticMarkup(<DayScreen today={today} tomorrow={TOMORROW} weather={WEATHER} />)
    const titles = [...html.matchAll(/chip-task-title">([^<]+)</g)].map((m) => m[1])
    expect(titles.slice(0, 3)).toEqual(['Teeth', 'Homework', 'Dishes'])
  })

  it('says what is next in one line above the rows', () => {
    // Everything on the card, agenda and chores both: the line sits over all
    // of them, and a count that covered only one read as wrong.
    // What is worth keeping first, whole; the count after it, which is the
    // half that ellipsises when the line is short.
    expect(renderAt(7, 30)).toMatch(
      /kid-headline-keep clamp-1">up to \+\d+ today<\/span><span class="kid-headline-rest clamp-1">\u00a0· 6 things today · Assembly at 9:00 am</,
    )
    // Inside the hour the card counts down instead of naming a time.
    expect(renderAt(15, 30)).toContain('Piano in 30 min')
  })

  it('does not say Today twice', () => {
    // The headline is the agenda's heading as well as its summary.
    const html = renderAt(7, 30)
    expect(html).toContain('kid-headline')
    expect(html).not.toContain('kid-section">Today')
  })

  it('counts agenda past three rows as a row of its own, and makes room for it', () => {
    const busy = {
      ...TODAY,
      kids: [
        {
          ...TODAY.kids[0],
          agenda: [
            ...TODAY.kids[0].agenda,
            { ...TODAY.kids[0].agenda[2], title: 'Soccer', start: '17:30', end: '18:30' },
          ],
        },
        TODAY.kids[1],
      ],
    }
    vi.setSystemTime(new Date(2026, 8, 29, 7, 30))
    const html = renderToStaticMarkup(
      <DayScreen today={busy} tomorrow={TOMORROW} weather={WEATHER} onOpenList={() => undefined} />,
    )
    const mira = html.slice(html.indexOf('data-kid-card="mira"'), html.indexOf('data-kid-card="kabir"'))
    // To-dos are never hidden, so the agenda gives way for them: two rows
    // and "+2 more", and every to-do drawn.
    expect(mira.match(/class="row row-/g)).toHaveLength(3)
    expect(mira).toContain('row-more-tap">+2 more<')
    expect(mira).not.toContain('task-more')
    expect(mira).toContain('>Homework<')
  })

  it('draws the chips read-only on the wall', () => {
    // A chip that looks tappable and is not is worse than one that plainly
    // is not: on DAY there is no button in a chip. Kid mode is where a tap
    // claims.
    const html = renderAt(7, 30)
    const chips = html.slice(html.indexOf('<ul class="chips'))
    expect(chips.slice(0, chips.indexOf('</ul>'))).not.toContain('<button')
    expect(html).not.toContain('chip-task-tap')
  })
})

describe('a claimed task', () => {
  it('shows filled on the dashboard, so a parent walking past sees it', () => {
    const claimed = {
      ...TODAY,
      kids: [
        { ...TODAY.kids[0], tasks: [task('hw', 'Homework', { status: 'claimed' as const })] },
        TODAY.kids[1],
      ],
    }
    vi.setSystemTime(new Date(2026, 8, 29, 15, 30))
    const html = renderToStaticMarkup(
      <DayScreen today={claimed} tomorrow={TOMORROW} weather={WEATHER} />,
    )
    expect(html).toContain('chip-task chip-task-claimed')
    expect(html).toContain('chip-task-worth">Waiting · +10<')
    // The sentence about waiting belongs in kid mode, where there is room for
    // it and where the person reading it is the one waiting.
    expect(html).not.toContain('Waiting for Mom or Dad')
  })

  it('locks a task only a parent may tick', () => {
    const locked = {
      ...TODAY,
      kids: [
        { ...TODAY.kids[0], tasks: [task('hw', 'Homework', { claim: 'parent' as const })] },
        TODAY.kids[1],
      ],
    }
    vi.setSystemTime(new Date(2026, 8, 29, 15, 30))
    const html = renderToStaticMarkup(
      <DayScreen today={locked} tomorrow={TOMORROW} weather={WEATHER} />,
    )
    // The lock where the ring would be, and no ring.
    const mira = html.slice(html.indexOf('Mira'), html.indexOf('Kabir'))
    expect(mira).toContain('chip-task chip-task-parent')
    expect(mira).toContain('chip-task-lock')
    expect(mira).not.toContain('chip-task-ring')
  })
})

describe("a district feed's long titles", () => {
  function renderLong(): string {
    vi.setSystemTime(new Date(2026, 8, 29, 15, 30))
    return renderToStaticMarkup(
      <DayScreen today={LONG_DAY} tomorrow={TOMORROW} weather={WEATHER} />,
    )
  }

  it('renders them', () => {
    expect(renderLong()).toMatchSnapshot()
  })

  it('shows the whole title, never a truncated one', () => {
    const html = renderLong()
    expect(html).toContain('>Cross Country meet<')
    // The grade is already said by whose column the row is in.
    expect(html).not.toContain('6th Grade Boys')
    expect(html).toContain('>Girls Volleyball<')
  })

  it('leaves the place to the room the title leaves', () => {
    // Parsed out of the title, and offered in what is left of the row: the
    // stylesheet does not draw it under 120px, which the design suite checks
    // at both sizes. Nothing here guesses at widths any more.
    const html = renderLong()
    expect(html).toContain('hide-under-120"><span class="row-where clamp-1">Bayside Middle<')
  })

  it('keeps a place beside a short title', () => {
    expect(renderLong()).toContain("Ms. Lee&#x27;s")
  })

  it('labels an all-day row rather than leaving the time blank', () => {
    expect(renderLong()).toContain('All day')
  })

  it('gives the long meal names room', () => {
    const html = renderLong()
    expect(html).toContain('Idli and sambar')
    expect(html).toContain('Pesto pasta')
  })
})

describe('the playful set', () => {
  function render(today: typeof TODAY, points = {}): string {
    vi.setSystemTime(new Date(2026, 8, 29, 15, 30))
    return renderToStaticMarkup(
      <DayScreen today={today} tomorrow={TOMORROW} weather={WEATHER} points={points} />,
    )
  }

  it('says happy birthday on the day, and nothing on any other', () => {
    const ordinary = render(TODAY)
    expect(ordinary).not.toContain('kid-bunting')

    const birthday = {
      ...TODAY,
      kids: TODAY.kids.map((kid, at) => (at === 0 ? { ...kid, birthday: true } : kid)),
    }
    const html = render(birthday)
    expect(html).toContain('Happy birthday, Mira')
    // One card, not both: it is one child's day.
    expect(html.match(/kid-bunting/g)).toHaveLength(1)
  })

  it('draws what a kid is saving for under their points, one bar and no more', () => {
    // A star that shows nothing where a child walks past does nothing. The
    // bar rides under the number in the header rather than taking a row: the
    // card is full at 434px and the header's height is the avatar's.
    const html = render(TODAY, {
      mira: {
        kid_id: 'mira',
        balance: 20,
        this_week: 20,
        streak_days: 0,
        saving_for: [
          { reward_id: 'hot_chocolate', name: 'Hot chocolate out', glyph: 'cup', cost: 40 },
          { reward_id: 'ice_cream', name: 'Ice cream', glyph: 'ice-cream', cost: 30 },
        ],
      },
    })

    expect(html.match(/save-mini/g)).toHaveLength(1)
    // The nearest, not the first: 10 to go rather than 60.
    expect(html).toContain('Ice cream')
    expect(html).not.toContain('Hot chocolate out')
    // Two thirds of the way there, and no row taken from today.
    expect(html).toContain('width:67%')
    expect(html).not.toContain('save-track')
  })

  it('draws no bar for a kid saving for nothing', () => {
    const html = render(TODAY, {
      mira: { kid_id: 'mira', balance: 20, this_week: 20, streak_days: 0, saving_for: [] },
    })

    expect(html).not.toContain('save-mini')
  })

  it('never asks how today was on the day screen', () => {
    // The bedtime check-in belongs to NIGHT and the weekly digest. It is off
    // by default, and it is not on this screen at all even when it is on.
    const html = render(TODAY)
    expect(html).not.toContain('feelings')
    expect(html).not.toContain('How was today')
  })
})

describe('the weekend', () => {
  function renderOn(date: string, weekday: Weekday): string {
    vi.setSystemTime(new Date(2026, 9, 3, 10, 0))
    return renderToStaticMarkup(
      <DayScreen
        today={{ ...TODAY, date, weekday }}
        tomorrow={TOMORROW}
        weather={WEATHER}
      />,
    )
  }

  it('says so under the date, in the festival colour', () => {
    // Saturday 3 October 2026.
    const saturday = renderOn('2026-10-03', 'sat')
    expect(saturday).toContain('day-date-weekend')
    expect(saturday).toContain('Weekend')
  })

  it('leaves the school feed out of it', () => {
    // A Saturday with "Girls Volleyball" on it reads as a school day.
    const saturday = renderToStaticMarkup(
      <DayScreen
        today={{ ...LONG_DAY, date: '2026-10-03', weekday: 'sat' }}
        tomorrow={TOMORROW}
        weather={WEATHER}
      />,
    )
    expect(saturday).not.toContain('row-glyph')
    expect(saturday).not.toContain('Cross Country meet')
  })

  it('is an ordinary day the rest of the week', () => {
    expect(renderOn('2026-09-29', 'tue')).not.toContain('day-date-weekend')
  })
})

describe('the family strip', () => {
  function renderWith(family: typeof TODAY.family_agenda, points = {}): string {
    vi.setSystemTime(new Date(2026, 8, 23, 9, 0))
    return renderToStaticMarkup(
      <DayScreen
        today={{ ...TODAY, family_agenda: family }}
        tomorrow={TOMORROW}
        weather={WEATHER}
        points={points}
      />,
    )
  }
  const at = (title: string, start: string) => ({
    ...TODAY.family_agenda[0],
    title,
    start,
    end: null,
  })

  it('draws each event as a pill, the owner out of the brackets and onto a chip', () => {
    const html = renderWith([at('Pickup Kevin', '13:30'), at('Hammer & Nails [Dad]', '10:30')])
    // In the order of the day.
    expect(html.indexOf('Hammer')).toBeLessThan(html.indexOf('Pickup'))
    expect(html).toContain('fam-when">10:30 am<')
    expect(html).toContain('fam-what">Hammer &amp; Nails<')
    expect(html).toContain('fam-who" title="Dad">D<')
    expect(html).not.toContain('[Dad]')
    // No owner, no chip.
    expect(html.match(/fam-who/g)).toHaveLength(1)
  })

  it('says so when the family has nothing on', () => {
    expect(renderWith([])).toContain('Nothing for the family today')
  })

  it('pins the jar at the end with its name on it, never a bare number', () => {
    const html = renderWith([], {
      family: { kid_id: 'family', balance: 5, this_week: 0, streak_days: 0, saving_for: [] },
    })
    // Something in it: the festival's tint.
    expect(html).toContain('fam-jar fam-jar-some">Family jar · 5<')
    // Empty: an outline in the muted ink, never the amber pill.
    const empty = renderWith([], {
      family: { kid_id: 'family', balance: 0, this_week: 0, streak_days: 0, saving_for: [] },
    })
    expect(empty).toContain('class="fam-jar">Family jar · 0<')
    expect(renderWith([])).not.toContain('fam-jar')
  })
})

describe('a decided task', () => {
  function renderTasks(tasks: ReturnType<typeof task>[]): string {
    vi.setSystemTime(new Date(2026, 8, 29, 15, 30))
    return renderToStaticMarkup(
      <DayScreen
        today={{ ...TODAY, kids: [TODAY.kids[0], { ...TODAY.kids[1], tasks }] }}
        tomorrow={TOMORROW}
        weather={WEATHER}
      />,
    )
  }

  it('says what it earned, or that it was not today', () => {
    const html = renderTasks([
      task('hw', 'Homework', { status: 'approved' }),
      task('outside', '30 min outside', { status: 'declined' }),
    ])
    // Approved: green, the ring a disc with a tick. Declined: dimmed, the
    // worth struck through (day.css) and still there to read.
    expect(html).toContain('chip-task chip-task-approved')
    expect(html).toContain('chip-task-ring chip-task-tick')
    expect(html).toContain('chip-task chip-task-declined')
    expect(html).toMatch(/chip-task-declined">.*?chip-task-worth">\+10</)
  })

  it('adds up what a parent said yes to today at the foot of the card', () => {
    const html = renderTasks([
      task('hw', 'Homework', { status: 'approved' }),
      task('outside', '30 min outside', { status: 'approved' }),
    ])
    expect(html).toContain('kid-foot-earned">+20 today<')
    expect(html).toContain('kid-foot-left">+0 still to earn<')
    // Still to earn, when nothing is approved yet.
    expect(renderTasks([task('hw', 'Homework')])).toContain('kid-foot-left">+10 still to earn<')
    // And nothing at all when both are zero.
    expect(renderTasks([])).not.toContain('kid-foot')
  })
})

describe('the Tuesday with 2, 5 and 7 to-dos', () => {
  const ALL = [
    task('hw', 'Homework', { status: 'claimed', points: 5 }),
    task('outside', '30 minutes outside', { points: 2 }),
    task('reading', 'Reading, 20 minutes', { points: 2 }),
    task('piano', 'Piano practice', { status: 'approved', points: 4 }),
    task('dishes', 'Load the dishwasher', { routine: 'evening', points: 5 }),
    task('bag', 'Pack the school bag', { routine: 'evening', points: 2 }),
    task('trash', 'Take out the trash', { routine: 'evening', claim: 'parent', points: 3 }),
  ]
  const ROUTINES_OF = (count: number) =>
    count === 2 ? [ALL[0], ALL[4]] : count === 5 ? ALL.slice(0, 5) : ALL

  for (const count of [2, 5, 7]) {
    for (const [orientation, height] of [
      ['landscape', 768],
      ['portrait', 1024],
    ] as const) {
      it(`draws ${count} to-dos at 5 pm, ${orientation}`, () => {
        vi.setSystemTime(new Date(2026, 8, 29, 17, 0))
        const html = renderToStaticMarkup(
          <DayScreen
            today={{ ...TODAY, kids: [{ ...TODAY.kids[0], tasks: ROUTINES_OF(count) }, TODAY.kids[1]] }}
            tomorrow={TOMORROW}
            weather={WEATHER}
            height={height}
          />,
        )
        const mira = html.slice(html.indexOf('data-kid-card="mira"'), html.indexOf('data-kid-card="kabir"'))
        // Every to-do drawn, none counted into "+N more", nothing scrolling.
        expect(mira.match(/<li class="chip-task /g)).toHaveLength(count)
        expect(mira).not.toContain('task-more')
        expect(mira).not.toContain('tasks-scroll')
        expect(mira).toMatchSnapshot()
      })
    }
  }
})

describe('dinner out', () => {
  it('reads Out and the place on Tomorrow, with the storefront and the veg leaf', () => {
    const tomorrow = {
      ...TOMORROW,
      diet: { non_veg_ok: false, reasons: ['Navratri'] },
      meals: {
        ...TOMORROW.meals,
        dinner: {
          name: 'Dinner out',
          id: 'dinner_out',
          note: 'Taqueria Luna',
          kids_protein: 'veg' as const,
          picked_by: [],
          confirmed: true,
        },
      },
    }
    vi.setSystemTime(new Date(2026, 8, 29, 15, 30))
    const html = renderToStaticMarkup(
      <DayScreen today={TODAY} tomorrow={tomorrow} weather={WEATHER} />,
    )
    const card = html.slice(html.lastIndexOf('dp-card'))
    expect(card).toContain('>Out · Taqueria Luna<')
    expect(card).toContain('meal-out-glyph')
    expect(card).toContain('meal-out-leaf')
  })
})

describe('the leftover height', () => {
  const SEVEN = [
    task('hw', 'Homework', { status: 'claimed', points: 5 }),
    task('outside', '30 minutes outside', { points: 2 }),
    task('reading', 'Reading, 20 minutes', { points: 2 }),
    task('piano', 'Piano practice', { status: 'approved', points: 4 }),
    task('dishes', 'Load the dishwasher', { routine: 'evening', points: 5 }),
    task('bag', 'Pack the school bag', { routine: 'evening', points: 2 }),
    task('trash', 'Take out the trash', { routine: 'evening', claim: 'parent', points: 3 }),
  ]

  /** Both cards alike: `agenda` rows of the calendar and these to-dos. */
  function at(height: number, agenda: number, tasks: ReturnType<typeof task>[]): string {
    vi.setSystemTime(new Date(2026, 8, 29, 17, 0))
    const kids = TODAY.kids.map((kid) => ({ ...kid, agenda: TODAY.kids[0].agenda.slice(0, agenda), tasks }))
    return renderToStaticMarkup(
      <DayScreen
        today={{ ...TODAY, kids }}
        tomorrow={TOMORROW}
        upcoming={[TOMORROW, TOMORROW, TOMORROW]}
        weather={WEATHER}
        height={height}
      />,
    )
  }

  it('gives more than 160px under the cards to a full Coming up', () => {
    // Upright, five to-dos under one agenda row: the bottom row keeps its
    // 168 and the next three days take the rest.
    const html = at(1024, 1, SEVEN.slice(0, 5))
    expect(html).toContain('day-coming-up')
    expect(html).not.toContain('day-compact-meals')
    expect(html.match(/class="cu-row"/g)).toHaveLength(3)
  })

  it('gives 60 to 160px to a two-day Coming up, over shorter meal rows', () => {
    // Landscape, one short to-do and nothing on the calendar.
    const html = at(768, 0, [task('hw', 'Homework')])
    expect(html).toContain('day-coming-up day-compact-meals')
    expect(html).toContain('cu-card-compact')
    expect(html.match(/class="cu-row"/g)).toHaveLength(2)
  })

  it('adds nothing under 60px', () => {
    // Landscape, seven to-dos and three agenda rows: the cards take it all.
    const html = at(768, 3, SEVEN)
    expect(html).not.toContain('day-coming-up')
    expect(html).not.toContain('cu-card')
    // And still every to-do.
    expect(html.match(/<li class="chip-task /g)).toHaveLength(14)
  })
})
