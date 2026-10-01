import type { AgendaEntry, Day } from '../../api/types'

/**
 * The agenda flattened into rows, and the filter that hides them.
 *
 * Kept out of the component so the filtering can be read and tested without a
 * DOM — it is the only part of this screen with any thinking in it.
 */

/** A chip: one per child (their id), then the family's and the calendars'. */
export type Filter = string

/** The chips after the children's, which every house has. */
export const SHARED_FILTERS: Filter[] = ['family', 'school', 'festival', 'holiday']

/** Every chip, in order: each child by id, then the shared ones. */
export function filtersFor(kidIds: readonly string[]): Filter[] {
  return [...kidIds, ...SHARED_FILTERS]
}

export type Row = {
  key: string
  /** Which chip governs it. */
  filter: Filter
  /** The kid whose colour the dot takes, or null for school and family. */
  kid: string | null
  /** Whose face starts the row: the kid whose calendar it came from, or null
      for the family's — and for a school row both kids' feeds carried. */
  owner: string | null
  time: string | null
  title: string
  /** "Sam", from a "Dentist [Sam]" title: drawn as their initial. */
  tag: string | null
  where: string | null
  school: boolean
}

export type ListDay = {
  date: string
  weekday: string
  schoolNote: string | null
  isSchoolDay: boolean
  observances: { name: string; kind: string }[]
  rows: Row[]
}

/** Which chip an agenda entry belongs to. */
export function filterOf(entry: AgendaEntry, owner: string): Filter {
  if (entry.source_kind === 'school' || entry.source === 'school') {
    return 'school'
  }
  if (owner === 'family') {
    return 'family'
  }
  return owner
}

/** A trailing "[Name]", which the family's calendar uses to say whose it is. */
const OWNER_SUFFIX = /\s*\[([^\]]+)\]\s*$/

function rowFor(entry: AgendaEntry, owner: string, index: number): Row {
  const school = entry.source_kind === 'school' || entry.source === 'school'
  const suffix = OWNER_SUFFIX.exec(entry.title)
  return {
    key: `${owner}-${entry.title}-${entry.start ?? 'all'}-${index}`,
    filter: filterOf(entry, owner),
    kid: school ? null : owner === 'family' ? null : owner,
    owner: owner === 'family' ? null : owner,
    time: entry.all_day ? null : (entry.start ?? null),
    title: suffix ? entry.title.slice(0, suffix.index).trim() : entry.title,
    where: entry.where,
    school,
    tag: suffix ? suffix[1].trim() : null,
  }
}

/**
 * One day's rows in reading order, each thing once.
 *
 * All-day rows first, then by start time — the kids' rows were pushed before
 * the family's, so a family 9:10 came after a kid's 10:30. And a school's
 * all-day row arrives once per child's feed ("Minimum day", twice); it is
 * one day for the house, so it is one row, and the face on it is the
 * family's rather than either child's.
 */
export function ordered(rows: readonly Row[]): Row[] {
  const kept: Row[] = []
  const seen = new Map<string, Row>()
  for (const row of rows) {
    if (row.school && row.time === null) {
      const key = row.title.trim().toLowerCase().replace(/\s+/g, ' ')
      const first = seen.get(key)
      if (first) {
        if (first.owner !== row.owner) {
          first.owner = null
        }
        continue
      }
      const held = { ...row }
      seen.set(key, held)
      kept.push(held)
      continue
    }
    kept.push(row)
  }
  const rank = (row: Row) => (row.time === null ? '' : row.time)
  return kept
    .map((row, index) => ({ row, index }))
    .sort((a, b) => rank(a.row).localeCompare(rank(b.row)) || a.index - b.index)
    .map(({ row }) => row)
}

/** Every day in the window, with its rows, before filtering. */
export function daysFrom(agenda: readonly Day[]): ListDay[] {
  return agenda.map((day) => {
    const rows: Row[] = []
    day.kids.forEach((kid) => {
      kid.agenda.forEach((entry, index) => rows.push(rowFor(entry, kid.id, index)))
    })
    day.family_agenda.forEach((entry, index) => rows.push(rowFor(entry, 'family', index)))
    return {
      date: day.date,
      weekday: day.weekday,
      schoolNote: day.school_note,
      isSchoolDay: day.is_school_day,
      observances: day.observances.map((o) => ({ name: o.name, kind: o.kind })),
      rows: ordered(rows),
    }
  })
}

/**
 * The days worth drawing. A day with nothing left after filtering is skipped
 * entirely — sixty day headers with nothing under them is not a list.
 */
export function visible(days: readonly ListDay[], on: ReadonlySet<Filter>): ListDay[] {
  const all = on.size === 0
  return days
    .map((day) => {
      const rows = all ? day.rows : day.rows.filter((row) => on.has(row.filter))
      const observances = day.observances.filter(
        (o) => all || on.has(o.kind === 'festival' ? 'festival' : 'holiday'),
      )
      return { ...day, rows, observances }
    })
    .filter((day) => day.rows.length > 0 || day.observances.length > 0)
}
