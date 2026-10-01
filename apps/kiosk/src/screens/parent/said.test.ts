import { describe, expect, it } from 'vitest'

import { ageSaid, bytesSaid } from './said'

describe('what the parent screen says about time and size', () => {
  const now = new Date('2026-09-23T16:00:00-07:00')

  it('says how long ago a feed answered', () => {
    expect(ageSaid('2026-09-23T15:56:00-07:00', now)).toBe('4m ago')
    expect(ageSaid('2026-09-23T13:00:00-07:00', now)).toBe('3h ago')
    expect(ageSaid('2026-09-20T16:00:00-07:00', now)).toBe('3d ago')
    expect(ageSaid('2026-09-23T16:00:00-07:00', now)).toBe('just now')
  })

  it('says the size the way the Finder does', () => {
    expect(bytesSaid(840_000)).toBe('840 KB')
    expect(bytesSaid(12_400_000)).toBe('12.4 MB')
  })
})
