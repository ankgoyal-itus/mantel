import type { CSSProperties } from 'react'

/**
 * A kid's colour, in the three forms the stylesheets ask for, published on
 * whatever element carries that kid.
 *
 * --kid fills: the accent down a claimed row, the dot, the avatar's disc.
 * --kid-tint carries: a surface a word can sit on.
 * --kid-ink writes: the same colour darkened until it can be read on paper.
 * --kid-chip-ink writes on the tint: a waiting chip's words.
 *
 * All three are published by useTheme from family.yaml, so the fallbacks here
 * only cover the frame before the config lands — the tint falls back to
 * nothing rather than to the colour, because a saturated card for one frame
 * is more noticeable than a plain one.
 */
export function kidVars(id: string | null | undefined, colour: string): CSSProperties {
  if (!id) {
    return { ['--kid']: colour } as CSSProperties
  }
  return {
    // The drawn shade: the colour by day, lightened at night (theme.css).
    ['--kid']: `var(--shade-${id}, var(--kid-${id}, ${colour}))`,
    ['--kid-tint']: `var(--tint-${id}, transparent)`,
    ['--kid-ink']: `var(--ink-${id}, ${colour})`,
    ['--kid-chip-ink']: `var(--chip-ink-${id}, var(--ink-${id}, ${colour}))`,
  } as CSSProperties
}
