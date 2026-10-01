import { describe, expect, it } from 'vitest'

import { cleanTitle } from './titles'

describe('cleaning a school title', () => {
  it('takes the place out of the title', () => {
    expect(cleanTitle('Cross Country meet @ Bayside Middle')).toEqual({
      title: 'Cross Country meet',
      where: 'Bayside Middle',
    })
  })

  it('takes the grade off the front', () => {
    // Whose column the row is in already says which child it is for.
    expect(cleanTitle('6th Grade Girls Volleyball @ NMS')).toEqual({
      title: 'Girls Volleyball',
      where: 'NMS',
    })
    expect(cleanTitle('7th/8th Grade Girls Volleyball @ WMS').title).toBe('Girls Volleyball')
  })

  it('leaves a plain title alone', () => {
    expect(cleanTitle('Science Olympiad')).toEqual({ title: 'Science Olympiad', where: null })
  })

  it('keeps a place the calendar gave us over one from the title', () => {
    // A calendar that filled in a location knows better than a suffix.
    expect(cleanTitle('Piano', "Ms. Lee's")).toEqual({ title: 'Piano', where: "Ms. Lee's" })
    expect(cleanTitle('Swim @ Pool', 'Aquatic center').where).toBe('Aquatic center')
  })

  it('does not eat an email address or a title that is only a place', () => {
    expect(cleanTitle('@ Home').title).toBe('@ Home')
  })
})
