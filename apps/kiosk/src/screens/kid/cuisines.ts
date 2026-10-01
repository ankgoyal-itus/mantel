import type { PickOption } from '../../api/types'
import { copy } from '../../copy'

/**
 * The picker's list, bucketed by kind of food.
 *
 * The headers used to be emitted wherever the cuisine differed from the row
 * above, on the theory that the catalog already runs in cuisine blocks. It
 * does not — it runs in the order the dishes were written down — so dinner
 * read Indian, South Indian, Indian, South Indian, … Mexican, Mexican: not
 * landmarks but a stutter, and a list with fourteen headers in it has none.
 *
 * Grouping is done here rather than in the component because the thing worth
 * asserting — every cuisine once, and every dish still in the list — is a
 * fact about the buckets, not about the markup.
 */

export type Group = {
  /** The normalised slug, and the key React lists by. */
  key: string
  /** What to print, or '' for the dishes that carry no cuisine at all. */
  name: string
  items: PickOption[]
}

/**
 * "  South_Indian " and "south_indian" are the same shelf.
 *
 * Without this a feed that shifts its capitalisation splits one cuisine into
 * two headers, which is the bug this module exists to stop, arriving by a
 * different door.
 */
function normalise(cuisine: string | undefined): string {
  return (cuisine ?? '').trim().toLowerCase().replace(/\s+/g, ' ')
}

/**
 * What a shelf is keyed by: the name it prints, normalised — not the slug.
 * "mexican" and "mexican_indian" are both said "Mexican", and two headers
 * reading "Mexican" in one list is the bug this module exists to stop.
 */
function shelfOf(slug: string): string {
  return normalise(cuisineName(slug)).replace(/ /g, '_')
}

/**
 * "south_indian" -> "South Indian", for a slug the copy map has not named.
 *
 * Empty for a response that carries no cuisine at all: an older API, or a
 * cached body from before the field existed. A missing header is a list
 * without landmarks; a thrown error is a list without dinners.
 */
export function cuisineName(slug: string): string {
  if (!slug) {
    return ''
  }
  const known = copy.picker.cuisines[slug]
  if (known) {
    return known
  }
  return slug
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

/**
 * The two this house eats most, at the top, in this order.
 *
 * Not by count: on a week heavy with something else they would sink down the
 * list, and a child scrolling for dal should not have to learn a new order
 * every Tuesday.
 */
const FIRST = ['indian', 'south_indian']

/** The key of the trailing shelf: another slot's dishes, offered here too. */
export const ALSO = '__also'

export function groupByCuisine(options: readonly PickOption[], alsoName = ''): Group[] {
  const buckets = new Map<string, Group>()
  const also: PickOption[] = []

  for (const option of options) {
    if (option.also) {
      also.push(option)
      continue
    }
    const slug = normalise(option.cuisine).replace(/ /g, '_')
    const key = slug ? shelfOf(slug) : ''
    const found = buckets.get(key)
    if (found) {
      // Catalog order, inside the bucket: the API decided which dish leads.
      found.items.push(option)
    } else {
      buckets.set(key, { key, name: cuisineName(slug), items: [option] })
    }
  }

  const groups = sortShelves([...buckets.values()])
  // The other slot's dishes last, under one header, never mixed in.
  return also.length > 0 ? [...groups, { key: ALSO, name: alsoName, items: also }] : groups
}

function sortShelves(groups: Group[]): Group[] {
  return groups.sort((a, b) => {
    // The unnamed bucket has no header, so it goes to the bottom rather than
    // sitting in the middle of the list looking like part of what is above it.
    if (!a.key || !b.key) {
      return a.key ? -1 : b.key ? 1 : 0
    }
    const first = FIRST.indexOf(a.key)
    const second = FIRST.indexOf(b.key)
    if (first !== -1 || second !== -1) {
      return (first === -1 ? FIRST.length : first) - (second === -1 ? FIRST.length : second)
    }
    // Then the biggest shelves, because a header with one dish under it costs
    // a row to say less than the dish does.
    if (a.items.length !== b.items.length) {
      return b.items.length - a.items.length
    }
    return a.name.localeCompare(b.name)
  })
}
