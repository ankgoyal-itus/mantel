import type { CSSProperties } from 'react'

/** The animals, drawn in this repo (src/avatars/): one line set, 1.75px ink
    on two fills, cropped to a circle. Bundled, so nothing is fetched from
    anywhere the iPad might not reach. */
const DRAWINGS = import.meta.glob('../avatars/*.svg', {
  eager: true,
  // A URL to a bundled file, never inlined data: cached once, and named in
  // the markup so a test can say which animal is on a card.
  query: '?no-inline',
  import: 'default',
}) as Record<string, string>

function drawingOf(avatar: string): string | null {
  return DRAWINGS[`../avatars/${avatar}.svg`] ?? null
}

/**
 * A kid's animal on a disc of their colour, at one of three sizes: 56 on a
 * card's head, 24 in chips, rows and the parent rail, 16 in a meal row.
 *
 * Falls back to letters: a kid's initial in their colour, or — for the
 * parents, who have no animal — the two letters the caller chose to tell
 * them apart ("An", "Ak"), in the muted ink on a hairline disc.
 *
 * The disc is left to the theme unless a caller names one: by day it is a
 * wash of the kid's colour, at night the colour itself. Only the events
 * editor overrides it, where the disc is saying on or off rather than whose.
 */
export default function Avatar({
  name,
  avatar,
  colour,
  size,
  nodding = false,
  initials,
}: {
  name: string
  avatar: string | null
  colour?: string
  size: 56 | 24 | 16
  /** One 400ms nod as a card opens into kid mode. Never on a loop. */
  nodding?: boolean
  /** A grown-up's letters, instead of an animal. */
  initials?: string
}) {
  const style: CSSProperties = { width: size, height: size }
  if (colour) {
    style.background = colour
  }
  const drawing = avatar ? drawingOf(avatar) : null
  const letters = initials ?? name.slice(0, 1)
  return (
    <span
      className={initials ? 'avatar avatar-parent' : 'avatar'}
      style={style}
      data-avatar={drawing ? avatar : undefined}
    >
      {drawing ? (
        <img
          className={nodding ? 'avatar-animal avatar-nod' : 'avatar-animal'}
          src={drawing}
          alt=""
          draggable={false}
        />
      ) : (
        <span className={size >= 56 ? 'avatar-initial' : 'avatar-initial avatar-initial-small'}>
          {letters}
        </span>
      )}
    </span>
  )
}
