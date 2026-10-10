import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { PointsSummary } from '../../api/types'
import KidColumn from '../day/KidColumn'
import { TODAY } from '../day/fixtures'

function summary(over: Partial<PointsSummary>): PointsSummary {
  return {
    kid_id: TODAY.kids[0].id,
    balance: 40,
    this_week: 40,
    streak_days: 0,
    saving_for: [],
    ...over,
  }
}

function card(points: PointsSummary, claimable = false): string {
  return renderToStaticMarkup(
    <KidColumn kid={TODAY.kids[0]} now={Date.now()} points={points} claimable={claimable} />,
  )
}

describe('the banks on a card', () => {
  it('says both under the balance on the wall', () => {
    const html = card(summary({ cash_cents: 1500, roblox_minutes: 120 }))
    expect(html).toContain('bank-caption')
    expect(html).toContain('$15 saved · 2 h Roblox')
  })

  it('says only the one with something in it', () => {
    expect(card(summary({ cash_cents: 0, roblox_minutes: 150 }))).toContain('2 h 30 min Roblox')
  })

  it('says nothing at zero', () => {
    expect(card(summary({ cash_cents: 0, roblox_minutes: 0 }))).not.toContain('bank-caption')
  })

  it('leaves the caption to the chips on their own card', () => {
    expect(card(summary({ cash_cents: 1500 }), true)).not.toContain('bank-caption')
  })

  it('shows no toast for a deposit the screen has only just met', () => {
    const html = card(
      summary({
        cash_cents: 500,
        last_deposit: {
          id: 7,
          kid_id: TODAY.kids[0].id,
          account: 'cash',
          delta: 500,
          reason_kind: 'deposit',
          reason_ref: 'redemption:3',
          note: '$5 cash',
          actor: 'parent',
          created_at: '2026-10-06T12:00:00-07:00',
        },
      }),
    )
    expect(html).not.toContain('bank-toast')
  })
})
