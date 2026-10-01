/**
 * The seven drawings, in one hand.
 *
 * Two-tone: a pale wash from the colour the caller is drawn in, and the line
 * work over it at 2px with round caps — the same weight as the icons, so a
 * kite and a school glyph look like they came from the same pen.
 *
 * Inline rather than files in public/. The design doc asked for a folder of
 * SVGs, and these would be exactly that except for one thing: an empty state
 * is drawn in the kid's colour, and an <img> cannot inherit currentColor. A
 * mask would flatten the two tones into one. Seven inline shapes cost about a
 * kilobyte, which is less than one of the avatars — and the avatars are files
 * for the opposite reason, that there are twenty-four of them and only two
 * are ever on screen.
 */

export type Drawing = 'kite' | 'cat' | 'plate' | 'sun' | 'moon' | 'party' | 'backpack'

type Shape = {
  /** Filled at 14% of the current colour: the body of the thing. */
  wash: string
  /** Stroked at 2px in the current colour: the drawing itself. */
  line: string
}

const SHAPES: Record<Drawing, Shape> = {
  // Nothing on this afternoon, so the sky is free.
  kite: {
    wash: 'M24 6 38 22 24 38 10 22Z',
    line: 'M24 6 38 22 24 38 10 22ZM24 6v32M10 22h28M24 38q-2 6 2 8t-1 4',
  },
  // Nothing to do, and somebody has the right idea about it.
  cat: {
    wash: 'M14 34a10 8 0 0 1 20 0Z',
    line: 'M14 34a10 8 0 0 1 20 0M14 34h20M16 27l-3-5 6 1M32 27l3-5-6 1M18 31h.01M22 31h.01'
      + 'M6 34h36',
  },
  // Nothing planned to eat.
  plate: {
    wash: 'M24 14a10 10 0 1 1 0 20 10 10 0 0 1 0-20Z',
    line: 'M24 10a14 14 0 1 0 0 28 14 14 0 0 0 0-28M24 14a10 10 0 1 1 0 20 10 10 0 0 1 0-20',
  },
  sun: {
    wash: 'M24 16a8 8 0 1 1 0 16 8 8 0 0 1 0-16Z',
    line: 'M24 16a8 8 0 1 0 0 16 8 8 0 0 0 0-16M24 6v4M24 38v4M6 24h4M38 24h4'
      + 'M11 11l3 3M34 34l3 3M11 37l3-3M34 14l3-3',
  },
  moon: {
    wash: 'M34 30A13 13 0 0 1 18 14a13 13 0 1 0 16 16Z',
    line: 'M34 30A13 13 0 0 1 18 14a13 13 0 1 0 16 16Z',
  },
  party: {
    wash: 'M12 38 22 18l8 8Z',
    line: 'M12 38 22 18l8 8ZM30 10v4M36 16h4M33 21l3 3M28 8l-2 3',
  },
  backpack: {
    wash: 'M14 18h20v20H14Z',
    line: 'M14 20a10 10 0 0 1 20 0v16a2 2 0 0 1-2 2H16a2 2 0 0 1-2-2ZM20 18v-4a4 4 0 0 1 8 0v4'
      + 'M14 28h20M22 28v4h4v-4',
  },
}

/** Every drawing there is, for the tests. */
export const ILLUSTRATIONS = Object.keys(SHAPES) as Drawing[]

export default function Illustration({
  name,
  size = 48,
  className,
}: {
  name: Drawing
  size?: number
  className?: string
}) {
  const shape = SHAPES[name]
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={shape.wash} fill="currentColor" opacity="0.14" stroke="none" />
      <path d={shape.line} vectorEffect="non-scaling-stroke" />
    </svg>
  )
}
