import { describe, expect, it } from 'vitest'

import { cleanPlace, isOut, mealName } from './out'

describe('a meal eaten out', () => {
  it('reads as Out and the place, wherever a meal shows', () => {
    expect(mealName({ id: 'dinner_out', name: 'Dinner out', note: 'Taqueria Luna' })).toBe(
      'Out · Taqueria Luna',
    )
    expect(mealName({ id: 'lunch_out', name: 'Lunch out', note: null })).toBe('Out')
    expect(mealName({ id: 'rajma', name: 'Rajma masala', note: 'Lunchbox' })).toBe('Rajma masala')
  })

  it('knows the two ids and nothing else', () => {
    expect(isOut('dinner_out')).toBe(true)
    expect(isOut('lunch_out')).toBe(true)
    expect(isOut('pizza')).toBe(false)
    expect(isOut(null)).toBe(false)
  })

  it('keeps a place tidy and short', () => {
    expect(cleanPlace('  Corner   Trattoria ')).toBe('Corner Trattoria')
    expect(cleanPlace('   ')).toBeNull()
    expect(cleanPlace('x'.repeat(50))).toHaveLength(40)
  })
})
