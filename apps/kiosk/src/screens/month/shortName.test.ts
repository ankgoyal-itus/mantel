import { describe, expect, it } from 'vitest'

import { shortName } from '../MonthScreen'

describe('what a cell calls an observance', () => {
  it('names the ones this family keeps, from the map', () => {
    // October used to read "Jayanti", "Festivities", "Saptami", "Columbus":
    // four cells, none of them a festival anybody here would recognise.
    expect(shortName('First Day of Sharad Navratri')).toBe('Navratri')
    expect(shortName('Mahatma Gandhi Jayanti')).toBe('Gandhi Jayanti')
    expect(shortName('First Day of Durga Puja Festivities')).toBe('Durga Puja')
    expect(shortName('Columbus Day')).toBe('Columbus Day')
    expect(shortName('Karaka Chaturthi')).toBe('Karwa Chauth')
    expect(shortName('Maharishi Valmiki Jayanti')).toBe('Valmiki Jayanti')
    expect(shortName('Maha Saptami')).toBe('Saptami')
    expect(shortName('Maha Ashtami')).toBe('Ashtami')
  })

  it('leaves a name that is already short alone', () => {
    expect(shortName('Dussehra')).toBe('Dussehra')
    expect(shortName('Diwali')).toBe('Diwali')
    expect(shortName('Holi')).toBe('Holi')
    expect(shortName('Halloween')).toBe('Halloween')
    expect(shortName('Thanksgiving')).toBe('Thanksgiving')
    expect(shortName('Christmas')).toBe('Christmas')
  })

  it('matches the map however the feed capitalises it', () => {
    expect(shortName('COLUMBUS DAY')).toBe('Columbus Day')
    expect(shortName('  maha saptami  ')).toBe('Saptami')
  })

  it('takes the first two words of anything it does not know', () => {
    // The first two, never the last one alone: the name is at the front of
    // these, and the tail is what the feed added.
    expect(shortName('Ganesh Chaturthi')).toBe('Ganesh Chaturthi')
    expect(shortName('Raksha Bandhan')).toBe('Raksha Bandhan')
    expect(shortName('Guru Nanak Jayanti Gurpurab')).toBe('Guru Nanak')
  })

  it('takes the feeds scaffolding off the front and the back', () => {
    expect(shortName('First Day of Chhath Puja')).toBe('Chhath Puja')
    expect(shortName('Last Day of School')).toBe('School')
    expect(shortName('Onam Festivities')).toBe('Onam')
    expect(shortName('The Feast of Stephen')).toBe('Feast of')
  })

  it('cuts at a slash or a comma rather than showing both halves', () => {
    expect(shortName('Diwali/Deepavali')).toBe('Diwali')
    expect(shortName('Holi, the festival of colours')).toBe('Holi')
  })

  it('never comes back empty while there was something to say', () => {
    expect(shortName('Day')).toBe('Day')
    expect(shortName('')).toBe('')
  })
})
