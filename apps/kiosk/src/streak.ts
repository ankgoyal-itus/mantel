/**
 * How big the flame is.
 *
 * A run of days is the one number on this screen that is worth being proud
 * of, and a flame that is the same size at three days and at thirty says the
 * thirty did not matter. Three sizes and no more: a child should be able to
 * tell theirs apart across a room without counting anything.
 *
 * The thresholds are days, not points. Nothing here can be bought.
 */

export type Flame = 'none' | 'small' | 'medium' | 'large'

/** Three days is a habit forming, seven is a week, fourteen is a fortnight. */
export const SMALL_FROM = 3
export const MEDIUM_FROM = 7
export const LARGE_FROM = 14

export function flameFor(days: number): Flame {
  if (days >= LARGE_FROM) {
    return 'large'
  }
  if (days >= MEDIUM_FROM) {
    return 'medium'
  }
  return days >= SMALL_FROM ? 'small' : 'none'
}

/** Pixels, at the two places a balance is drawn. */
const SIZES: Record<Exclude<Flame, 'none'>, { small: number; large: number }> = {
  small: { small: 18, large: 22 },
  medium: { small: 22, large: 28 },
  large: { small: 26, large: 34 },
}

export function flameSize(flame: Flame, big: boolean): number {
  if (flame === 'none') {
    return 0
  }
  return big ? SIZES[flame].large : SIZES[flame].small
}
