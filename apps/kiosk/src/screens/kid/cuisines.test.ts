import { describe, expect, it } from 'vitest'

import type { PickOption } from '../../api/types'
import { groupByCuisine } from './cuisines'

const dish = (id: string, cuisine: string, pickable = true): PickOption => ({
  id,
  name: id,
  treat: false,
  cost: 0,
  proteins: ['veg'],
  pickable,
  why: null,
  cuisine,
  yesterday: false,
})

/** The shape the bug had: the catalog interleaves, it does not block. */
const dinners: PickOption[] = [
  dish('dal_rice', 'indian'),
  dish('idli', 'south_indian'),
  dish('rajma', 'indian'),
  dish('dosa', 'south_indian'),
  dish('tacos', 'mexican'),
  dish('chole', 'indian'),
  dish('quesadilla', 'mexican'),
  dish('upma', 'south_indian', false),
  dish('pasta', 'italian'),
]

describe('grouping the picker by cuisine', () => {
  it('says each cuisine once', () => {
    const headers = groupByCuisine(dinners).map((group) => group.name)

    expect(headers).toEqual([...new Set(headers)])
    // The old rule emitted nine rows of header for these nine dishes.
    expect(headers).toEqual(['Indian', 'South Indian', 'Mexican', 'Italian'])
  })

  it('loses no dish on the way into the buckets', () => {
    const groups = groupByCuisine(dinners)
    const under = groups.reduce((count, group) => count + group.items.length, 0)

    expect(under).toBe(dinners.length)
    expect(groups.flatMap((group) => group.items.map((item) => item.id)).sort()).toEqual(
      dinners.map((item) => item.id).sort(),
    )
  })

  it('keeps a faded dish in its own group rather than at the end', () => {
    const southIndian = groupByCuisine(dinners).find((group) => group.key === 'south_indian')

    expect(southIndian?.items.map((item) => item.id)).toEqual(['idli', 'dosa', 'upma'])
  })

  it('keeps catalog order inside a group', () => {
    const indian = groupByCuisine(dinners).find((group) => group.key === 'indian')

    expect(indian?.items.map((item) => item.id)).toEqual(['dal_rice', 'rajma', 'chole'])
  })

  it('leads with Indian and South Indian whatever the week looks like', () => {
    // Four Mexican dishes and one Indian: the order still holds, because a
    // child looking for dal should not have to learn a new list on Tuesday.
    const heavy = [
      dish('tacos', 'mexican'),
      dish('burrito', 'mexican'),
      dish('quesadilla', 'mexican'),
      dish('enchilada', 'mexican'),
      dish('dal_rice', 'indian'),
      dish('idli', 'south_indian'),
    ]

    expect(groupByCuisine(heavy).map((group) => group.name)).toEqual([
      'Indian',
      'South Indian',
      'Mexican',
    ])
  })

  it('orders the rest by how much is on the shelf, ties alphabetical', () => {
    const rest = [
      dish('pasta', 'italian'),
      dish('tacos', 'mexican'),
      dish('burrito', 'mexican'),
      dish('sushi', 'japanese'),
    ]

    expect(groupByCuisine(rest).map((group) => group.name)).toEqual([
      'Mexican',
      'Italian',
      'Japanese',
    ])
  })

  it('never splits one cuisine over capitals or stray spaces', () => {
    const messy = [dish('tacos', 'Mexican'), dish('burrito', ' mexican '), dish('nachos', 'MEXICAN')]
    const groups = groupByCuisine(messy)

    expect(groups).toHaveLength(1)
    expect(groups[0].name).toBe('Mexican')
    expect(groups[0].items).toHaveLength(3)
  })

  it('puts the dishes that carry no cuisine last, under no header', () => {
    const older = [dish('mystery', ''), dish('dal_rice', 'indian')]
    const groups = groupByCuisine(older)

    expect(groups.map((group) => group.name)).toEqual(['Indian', ''])
    expect(groups[1].items.map((item) => item.id)).toEqual(['mystery'])
  })
})

describe('one header per shelf, whatever the slug', () => {
  it('puts every dish said "Mexican" under one header', () => {
    // The catalog has both slugs, and both are said "Mexican".
    const headers = groupByCuisine([
      dish('tacos', 'mexican'),
      dish('kathi_roll', 'mexican_indian'),
      dish('burrito', ' Mexican  '),
    ]).map((group) => group.name)
    expect(headers).toEqual(['Mexican'])
  })

  it("keeps another slot's dishes at the end, under one header", () => {
    const also = { ...dish('dal_rice', 'indian'), also: true }
    const groups = groupByCuisine([dish('rajma', 'indian'), also], 'Also good for dinner')
    expect(groups.map((group) => group.name)).toEqual(['Indian', 'Also good for dinner'])
    expect(groups[1].items.map((one) => one.id)).toEqual(['dal_rice'])
  })
})
