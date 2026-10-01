import { describe, expect, it } from 'vitest'

import {
  CARD,
  KID_CARD,
  cardHeight,
  chipRoom,
  dashboardChipWidth,
  kidCardHeight,
  kidChipWidth,
  kidsRowHeight,
  planCard,
  planKidCard,
} from './budget'
import { chipsHeight } from './chips'

describe('the day budget', () => {
  it('gives the kids what the other three bands leave', () => {
    // 768 less 48 of margin, 300 of fixed bands and three 16px gaps.
    expect(kidsRowHeight(768)).toBe(372)
    expect(kidsRowHeight(1024)).toBe(628)
    // And never less than the floor, however short the screen.
    expect(kidsRowHeight(600)).toBe(340)
  })

  it('fits three agenda rows over two rows of chips at 1024x768', () => {
    // 132 of card, 98 of chips, 132 of agenda: 362 of 372.
    const plan = planCard({ height: 372, agenda: 3, chips: chipsHeight(2) })
    expect(plan).toEqual({ agenda: 3, agendaMore: 0, foot: false })
  })

  it('drops the footer first, and keeps it with the room', () => {
    expect(planCard({ height: 372, agenda: 3, chips: chipsHeight(2), foot: true }).foot).toBe(false)
    expect(planCard({ height: 628, agenda: 3, chips: chipsHeight(2), foot: true }).foot).toBe(true)
  })

  it('folds agenda rows for the chips, never the chips for the agenda', () => {
    // Three rows of chips need 152: one agenda row and "+2 more" leave room.
    const plan = planCard({ height: 372, agenda: 3, chips: chipsHeight(3) })
    expect(plan).toEqual({ agenda: 1, agendaMore: 2, foot: false })
  })

  it('folds the agenda into the headline before a to-do gives way', () => {
    // Four rows of chips (206) leave 34 under 372: not one agenda row, so
    // none, and the headline says "+3 more".
    const plan = planCard({ height: 372, agenda: 3, chips: chipsHeight(4) })
    expect(plan).toEqual({ agenda: 0, agendaMore: 3, foot: false })
    expect(cardHeight(plan, { agenda: 3, chips: chipsHeight(4) })).toBe(338)
  })

  it('gives the chips what is left with the agenda at its least', () => {
    // 372 less 122 of card, 10 of gap, and one row and its "+N more".
    expect(chipRoom({ height: 372, agenda: 3 })).toBe(152)
    expect(chipRoom({ height: 372, agenda: 1 })).toBe(196)
    expect(chipRoom({ height: 372, agenda: 3, bunting: true })).toBe(120)
  })

  it('never plans a card taller than the band unless the chips alone are', () => {
    for (const band of [340, 372, 500, 628]) {
      for (let agenda = 0; agenda <= 6; agenda += 1) {
        for (let rows = 0; rows <= 5; rows += 1) {
          const chips = chipsHeight(rows)
          const plan = planCard({ height: band, agenda, chips, foot: true })
          const used = cardHeight(plan, { agenda, chips })
          const floor =
            CARD.chrome + CARD.head + CARD.headline + CARD.week + CARD.chipGap + chips +
            (agenda === 0 ? 1 : 0) * CARD.row
          expect(used, `${band}px, ${agenda} agenda, ${rows} rows`).toBeLessThanOrEqual(
            Math.max(band, floor),
          )
        }
      }
    }
  })

  it('wraps chips in the width of the card', () => {
    // Half of 1024 less the margins and gap, less the card's padding.
    expect(dashboardChipWidth(1024)).toBe(430)
    expect(dashboardChipWidth(768)).toBe(302)
    expect(Math.round(kidChipWidth(1024))).toBe(590)
  })
})

describe('the open card in kid mode', () => {
  it('keeps two agenda rows over two rows of chips on a 768px iPad', () => {
    const height = kidCardHeight(768)
    expect(planKidCard({ height, agenda: 3, chips: chipsHeight(2), saving: true })).toEqual({
      agenda: 2,
    })
  })

  it('gives up agenda for chips, down to one row', () => {
    const height = kidCardHeight(768)
    expect(planKidCard({ height, agenda: 3, chips: chipsHeight(4), saving: true })).toEqual({
      agenda: 1,
    })
    expect(KID_CARD.row).toBe(56)
  })
})
