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

/**
 * The one to open on, after the frame takes over.
 *
 * The most recent photo by the date it was taken, not the date it arrived:
 * somebody who has just sent five pictures from a Saturday wants to see the
 * Saturday, and a scan of an old print is not new because it was scanned
 * today. Everything after it plays in the session's own shuffled order, so
 * the frame does not become a reverse-chronological feed.
 *
 * Nothing dated at all leaves the order alone, which is what a library with
 * no EXIF gets — the frame worked that way before this existed.
 */
export function newestFirst(photos: readonly Photo[]): Photo[] {
  let newest: Photo | null = null
  for (const photo of photos) {
    if (!photo.taken_at) {
      continue
    }
    if (!newest || !newest.taken_at || photo.taken_at > newest.taken_at) {
      newest = photo
    }
  }
  if (!newest) {
    return [...photos]
  }
  const rest = photos.filter((photo) => photo.id !== newest.id)
  return [newest, ...rest]
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
