import { describe, expect, it } from 'vitest'

import { greetingAt } from './greeting'

const at = (hours: number, minutes = 0) => new Date(2026, 8, 29, hours, minutes)

describe('greetingAt', () => {
  it('says good morning from six until nine', () => {
    expect(greetingAt(at(5, 59), '22:00')).toBeNull()
    expect(greetingAt(at(6), '22:00')).toBe('morning')
    expect(greetingAt(at(8, 59), '22:00')).toBe('morning')
    expect(greetingAt(at(9), '22:00')).toBeNull()
  })

  it('says nothing through the middle of the day', () => {
    expect(greetingAt(at(12), '22:00')).toBeNull()
    expect(greetingAt(at(15, 30), '22:00')).toBeNull()
    expect(greetingAt(at(19, 59), '22:00')).toBeNull()
  })

  it('says good night from eight until the night screen takes over', () => {
    expect(greetingAt(at(20), '22:00')).toBe('night')
    expect(greetingAt(at(21, 59), '22:00')).toBe('night')
    expect(greetingAt(at(22), '22:00')).toBeNull()
  })

  it('follows the night start rather than a fixed hour', () => {
    expect(greetingAt(at(21), '20:30')).toBeNull()
    expect(greetingAt(at(22, 30), '23:00')).toBe('night')
  })

  it('falls back to 22:00 when the setting is missing or unreadable', () => {
    expect(greetingAt(at(21), undefined)).toBe('night')
    expect(greetingAt(at(21), 'later')).toBe('night')
    expect(greetingAt(at(22, 1), null)).toBeNull()
  })
})
