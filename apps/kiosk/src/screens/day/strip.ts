/**
 * How many family pills fit the strip, and what stands in for the rest.
 *
 * A pill never shrinks: "Pickup K…" is a pill that has stopped saying who.
 * So when they do not all fit, the last one that would have been drawn is
 * replaced by "+N", and the count covers it too.
 */

/** The "+N" pill, which is a fixed width so the answer cannot oscillate. */
export const MORE_PILL = 56

/**
 * The number of real pills to draw.
 *
 * `widths` are the pills as laid out, `room` the strip's own width. When the
 * answer is less than widths.length, a "+N" pill follows with N the rest.
 */
export function pillsThatFit(widths: number[], room: number, gap: number): number {
  const all = widths.reduce((sum, width) => sum + width, 0) + gap * Math.max(0, widths.length - 1)
  if (all <= room) {
    return widths.length
  }
  let used = MORE_PILL
  let count = 0
  for (const width of widths) {
    if (used + gap + width > room) {
      break
    }
    used += gap + width
    count += 1
  }
  return count
}
