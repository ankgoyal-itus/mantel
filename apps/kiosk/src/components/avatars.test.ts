import { readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { AVATARS } from './avatars'

const FOLDER = fileURLToPath(new URL('../avatars', import.meta.url))

describe('the animals', () => {
  it('are exactly the ones the picker offers, drawn in the repo', () => {
    const files = readdirSync(FOLDER)
      .filter((name) => name.endsWith('.svg'))
      .map((name) => name.replace(/\.svg$/, ''))
      .sort()
    expect([...AVATARS].sort()).toEqual(files)
  })

  it('are one line set: a circular crop and a 1.75px outline at any size', () => {
    for (const name of AVATARS) {
      const svg = readFileSync(`${FOLDER}/${name}.svg`, 'utf-8')
      expect(svg, name).toContain('<clipPath id="crop"><circle cx="24" cy="24" r="24"/>')
      const widths = new Set([...svg.matchAll(/stroke-width="([\d.]+)"/g)].map((m) => m[1]))
      expect([...widths], name).toEqual(['1.75'])
      expect(svg, name).toContain('vector-effect="non-scaling-stroke"')
    }
  })
})
