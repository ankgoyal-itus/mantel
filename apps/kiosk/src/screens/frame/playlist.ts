import type { Photo } from '../../api/types'

/**
 * The slideshow's order, kept out of the component so it can be reasoned about
 * without a DOM or a timer.
 *
 * The order is a pure function of the photos and one seed drawn per session,
 * rather than a shuffled list held in state. That is what lets the list be
 * re-fetched every refresh_minutes without the slideshow restarting: a photo's
 * place depends only on its id, so photos already playing keep their relative
 * order and new ones simply appear in it.
 */

/** FNV-1a over the id, seeded. Cheap, and well spread for short ids. */
export function rank(id: string, seed: number): number {
  let hash = (2166136261 ^ seed) >>> 0
  for (let i = 0; i < id.length; i += 1) {
    hash = (hash ^ id.charCodeAt(i)) >>> 0
    hash = Math.imul(hash, 16777619) >>> 0
  }
  return hash
}

/** The playing order: stable for a seed, and a permutation of what came in. */
export function ordered(photos: readonly Photo[], seed: number): Photo[] {
  return [...photos].sort((a, b) => {
    const difference = rank(a.id, seed) - rank(b.id, seed)
    // Ids break a tie, so two photos never swap places between renders.
    return difference !== 0 ? difference : a.id.localeCompare(b.id)
  })
}

/** The list without the ones that would not load. */
export function playable(photos: readonly Photo[], broken: ReadonlySet<string>): Photo[] {
  return photos.filter((photo) => !broken.has(photo.id))
}

/** Pass n's seed, from the session's: well spread, so neighbouring passes share no order. */
export function passSeed(seed: number, pass: number): number {
  return (Math.imul((seed ^ pass) >>> 0, 2654435761) ^ Math.imul(pass + 1, 40503)) >>> 0
}

/**
 * The photo at `cursor` (it only goes up). Each pass through the photos plays every photo
 * once in its own shuffle (a seed per pass from the session's), so no two passes repeat; when
 * a pass would open on the photo the last one closed with, it opens on its second instead.
 * No photo opens the show by rule (2026-10-18: the newest-first opener is gone).
 */
export function shown(photos: readonly Photo[], seed: number, cursor: number): Photo | null {
  const count = photos.length
  if (count === 0) {
    return null
  }
  const pass = Math.floor(Math.max(0, cursor) / count)
  const order = (n: number): Photo[] => {
    const list = ordered(photos, passSeed(seed, n))
    if (n === 0 || count < 2) {
      return list
    }
    const before = ordered(photos, passSeed(seed, n - 1))
    if (list[0].id !== before[count - 1].id) {
      return list
    }
    return [list[1], list[0], ...list.slice(2)]
  }
  return order(pass)[at(cursor, count)]
}

/**
 * The caption: where, and when. Either may be missing, and when both are the
 * photo carries no caption at all rather than an empty separator.
 */
export function caption(place: string | null, when: string): string {
  return [place, when].filter((part) => part && part.length > 0).join(' · ')
}

/** Where a cursor lands in a list of this length. Always valid, or 0. */
export function at(cursor: number, length: number): number {
  if (length <= 0) {
    return 0
  }
  return ((cursor % length) + length) % length
}
