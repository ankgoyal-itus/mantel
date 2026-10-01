/**
 * School titles, as they should be read rather than as the school writes them.
 *
 * "6th Grade Girls Volleyball @ NMS" carries three things in one string: who it
 * is for, what it is, and where. The grade is already implied by whose column
 * the row is in, and the place belongs in its own column — leaving them in the
 * title is what pushes the actual name out of the row.
 */

/** " @ Bayside Middle" at the end of a title. */
const AT_PLACE = /\s+@\s*(.+)$/

/** A leading "6th Grade ", "7th/8th Grade ", "Grade 5 ". */
const LEADING_GRADE = /^\s*(?:\d+(?:st|nd|rd|th)?(?:\s*\/\s*\d+(?:st|nd|rd|th)?)*\s*grade|grade\s*\d+)\s*/i

export type CleanTitle = { title: string; where: string | null }

/** A trailing "[Dad]", which is how a family calendar says whose event it is. */
const OWNER = /\s*\[([^\]]{1,24})\]\s*$/

export type Owned = { title: string; owner: string | null }

/**
 * Split "Haircut [Dad]" into the thing and the person.
 *
 * The brackets are a convention of the shared calendar, and reading them back
 * out on the wall makes the line look like a debug print. The name is worth
 * keeping — it answers "whose is this?" before anyone asks — but as a chip
 * beside the row rather than as punctuation inside it.
 */
export function splitOwner(title: string): Owned {
  const match = OWNER.exec(title)
  if (!match) {
    return { title: title.trim(), owner: null }
  }
  const owner = match[1].trim()
  const rest = title.slice(0, match.index).trim()
  // A title that is nothing but a name stays a title: better a row that reads
  // "Dad" than an empty row with a chip on it.
  return rest ? { title: rest, owner } : { title: owner, owner: null }
}

/**
 * Split a feed title into what it is and where it is.
 *
 * The place found in the title only wins when the row has none of its own: a
 * calendar that bothered to fill in a location knows better than a suffix.
 */
export function cleanTitle(title: string, where: string | null = null): CleanTitle {
  const match = AT_PLACE.exec(title)
  const stripped = match ? title.slice(0, match.index) : title
  const found = match ? match[1].trim() : null
  return {
    title: stripped.replace(LEADING_GRADE, '').trim() || title.trim(),
    where: where ?? found,
  }
}
