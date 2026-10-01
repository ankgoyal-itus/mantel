import type { PickOption, Protein } from '../../api/types'

/**
 * The two tiles above the list: the common case in one tap.
 *
 * Both of them choose from the options the API sent and nothing else, which
 * is the whole safety argument. That list has already been through the diet
 * rules for the day, the two-treats-a-week cap and the four-day repeat rule,
 * and a dish that failed any of them arrives with pickable false. So neither
 * of these can offer a meal the house has said no to — not because they
 * re-check anything, but because they have nothing else to draw from.
 */

/** Only what a child may actually have. */
export function pickable(options: readonly PickOption[]): PickOption[] {
  return options.filter((option) => option.pickable)
}

/**
 * What the house ate in this slot yesterday, when that is still allowed.
 *
 * For dinner it never is — the four-day repeat rule ruled yesterday's dinner
 * out before the list was built — so the tile simply does not appear there.
 * That is the rule working, not a hole in this: the point of the repeat rule
 * is that nobody eats the same dinner two nights running, including by
 * pressing the fast button.
 */
export function sameAsYesterday(options: readonly PickOption[]): PickOption | null {
  return pickable(options).find((option) => option.yesterday) ?? null
}

/**
 * One of the allowed dishes, at random.
 *
 * `roll` is a number in [0, 1) — Math.random in the app, a fixed value in the
 * tests, so "never violates the diet guard" is a thing that can be asserted
 * rather than hoped for.
 */
export function surpriseMe(options: readonly PickOption[], roll: number): PickOption | null {
  const allowed = pickable(options)
  if (allowed.length === 0) {
    return null
  }
  const at = Math.min(allowed.length - 1, Math.max(0, Math.floor(roll * allowed.length)))
  return allowed[at]
}

/**
 * How to cook it, when the child has not said.
 *
 * Veg where veg is on the table, which it always is on a day the dish is
 * offered at all; otherwise the first way the day's rules left standing.
 */
export function defaultProtein(option: PickOption): Protein | null {
  if (option.proteins.includes('veg')) {
    return 'veg'
  }
  return option.proteins[0] ?? null
}
