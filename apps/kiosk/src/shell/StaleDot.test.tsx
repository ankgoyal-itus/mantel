import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import StaleDot from './StaleDot'

const NOW = new Date(2026, 8, 29, 9, 41)

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(NOW)
})

afterEach(() => {
  vi.useRealTimers()
})

function at(minutesAgo: number): string {
  return renderToStaticMarkup(<StaleDot lastUpdated={NOW.getTime() - minutesAgo * 60000} />)
}

describe('the stale dot', () => {
  it('says nothing while the answer on screen is current', () => {
    // The old chip said "updated 9:41" all day, and everyone stopped seeing it.
    expect(at(1)).toBe('')
    expect(at(14)).toBe('')
  })

  it('appears once the data is a quarter of an hour old', () => {
    const html = at(16)
    expect(html).toContain('stale-dot')
    expect(html).toContain('since 9:25')
  })

  it('says nothing before the first poll has ever landed', () => {
    expect(renderToStaticMarkup(<StaleDot lastUpdated={null} />)).toBe('')
  })
})
