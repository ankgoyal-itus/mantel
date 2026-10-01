import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import type { Kid } from '../../api/types'
import ParentScreen, { SECTIONS } from './ParentScreen'

// The sections fetch on mount; static rendering runs no effects, so this is
// about the frame: which section it opens on, and what the rail offers.
vi.mock('../../api/parent', () => ({
  getApprovals: () => Promise.resolve([]),
  getTodos: () => Promise.resolve([]),
  getMeals: () => Promise.resolve([]),
  getDiet: () => Promise.resolve([]),
  sessionLeft: () => Promise.resolve(600),
  signOut: () => Promise.resolve(),
}))

const KIDS: Kid[] = [
  { id: 'mira', name: 'Mira', color: '#1F8A8A', avatar: 'fox' },
  { id: 'kabir', name: 'Kabir', color: '#D97706', avatar: 'panda' },
]

function current(html: string): string {
  const at = html.indexOf('aria-current="page"')
  return html.slice(at, at + 200)
}

describe('the parent screen', () => {
  const waiting = renderToStaticMarkup(
    <ParentScreen onDone={() => {}} pending={2} kids={KIDS} />,
  )
  const quiet = renderToStaticMarkup(<ParentScreen onDone={() => {}} pending={0} kids={KIDS} />)

  it('opens on Approvals while something is waiting', () => {
    // The only thing on this screen somebody is waiting on, and the only
    // thing a parent alone can do.
    expect(current(waiting)).toContain('data-section="approvals"')
  })

  it('opens on Meals when nothing is', () => {
    expect(current(quiet)).toContain('data-section="meals"')
  })

  it('badges Approvals with the count, and only when there is one', () => {
    expect(waiting).toContain('class="pp-badge" aria-label="2 waiting">2<')
    expect(quiet).not.toContain('pp-badge')
  })

  it('offers every section from the rail, in one tap each', () => {
    const rows = SECTIONS.map(({ id }) => waiting.indexOf(`data-section="${id}"`))
    expect(rows.every((at) => at > -1)).toBe(true)
    expect(rows).toEqual([...rows].sort((a, b) => a - b))
    // Each is a real, labelled button.
    for (const { id } of SECTIONS) {
      const at = waiting.indexOf(`data-section="${id}"`)
      expect(waiting.lastIndexOf('<button', at)).toBeGreaterThan(waiting.lastIndexOf('</button>', at))
    }
  })

  it('shows the family at the top of the rail, and Done at the foot', () => {
    expect(waiting).toContain('data-avatar="fox"')
    expect(waiting).toContain('data-avatar="panda"')
    expect(waiting.indexOf('pp-done-row')).toBeGreaterThan(waiting.indexOf('data-section="about"'))
  })
})

describe('the grown-ups on the rail', () => {
  it('get two letters that tell them apart, never two identical discs', async () => {
    const { initialsFor } = await import('./ParentScreen')
    const both = ['Sam', 'Shreya']
    expect(initialsFor('Sam', both)).toBe('Sa')
    expect(initialsFor('Shreya', both)).toBe('Sh')
    // Letters that still collide take the next one.
    expect(initialsFor('Anne', ['Anne', 'Anna'])).toBe('Anne')
  })
})
