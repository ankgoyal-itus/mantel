import { readableInk, tintOverWhite } from './tint'

/** A child as the palette needs them: an id and the colour family.yaml gives. */
export type KidColour = { id: string; color: string }

/** An id that is safe to write into a custom property's name. */
const SAFE_ID = /^[a-z0-9_-]+$/

/**
 * Each child's colour in every form the stylesheets ask for, as CSS.
 *
 * The children are data (family.yaml, via /api/config), so their variables
 * cannot be written into theme.css; this writes the same rules at runtime
 * instead, for however many children there are:
 *
 *   --kid-<id>       the colour itself
 *   --shade-<id>     the colour as drawn: itself by day, mixed with white 45%
 *                    at night so a dark colour still reads on the black
 *   --tint-<id>      a surface a word can sit on
 *   --ink-<id>       the colour darkened until it reads on paper
 *   --chip-ink-<id>  darker again, for words on the tint (a waiting chip)
 *
 * The day forms come from the contrast search in tint.ts; the night forms are
 * plain CSS, keyed on the same `html[data-theme='night']` as theme.css, so the
 * palette is right the instant the attribute changes rather than whenever
 * React next renders. kidVars points --kid and friends at these.
 */
export function kidPaletteCss(kids: readonly KidColour[]): string {
  const day: string[] = []
  const night: string[] = []
  for (const kid of kids) {
    if (!SAFE_ID.test(kid.id)) {
      continue
    }
    const tint = tintOverWhite(kid.color)
    const ink = readableInk(kid.color)
    if (!tint || !ink) {
      continue
    }
    const chipInk = readableInk(kid.color, undefined, tint) ?? ink
    const id = kid.id
    day.push(
      `--kid-${id}: ${kid.color};`,
      `--shade-${id}: var(--kid-${id});`,
      `--tint-${id}: ${tint};`,
      `--ink-${id}: ${ink};`,
      `--chip-ink-${id}: ${chipInk};`,
    )
    night.push(
      `--shade-${id}: color-mix(in srgb, var(--kid-${id}), white 45%);`,
      `--tint-${id}: color-mix(in srgb, var(--shade-${id}) 22%, transparent);`,
      `--ink-${id}: var(--shade-${id});`,
      `--chip-ink-${id}: var(--shade-${id});`,
    )
  }
  if (day.length === 0) {
    return ''
  }
  return `:root { ${day.join(' ')} }\nhtml[data-theme='night'] { ${night.join(' ')} }\n`
}

/** The day forms as values, for the tests that hold them to the rules. */
export function kidPaper(color: string): { tint: string; ink: string; chipInk: string } | null {
  const tint = tintOverWhite(color)
  const ink = readableInk(color)
  if (!tint || !ink) {
    return null
  }
  return { tint, ink, chipInk: readableInk(color, undefined, tint) ?? ink }
}
