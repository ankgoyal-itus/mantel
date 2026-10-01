import type { TaskEntry } from '../../api/types'
import { copy } from '../../copy'
import { ROUTINES } from '../../routines'

/**
 * The day's to-dos as chips: one wrapping row, routine order then task order,
 * no headers, nothing hidden and nothing scrolling. The card grows to hold
 * them, so what a card will need is worked out here, before it is drawn, from
 * the same measurements the stylesheet uses.
 */

/** A chip, in pixels. Mirrors .chip-task in day.css. */
export const CHIP = {
  height: 44,
  gap: 10,
  padLeft: 12,
  padRight: 14,
  ring: 12,
  ringGap: 8,
  worthGap: 10,
  border: 4,
} as const

/** The two faces a chip's words are set in: the system sans, never Nunito. */
const BODY = '-apple-system, BlinkMacSystemFont, "Helvetica Neue", Helvetica, Arial, sans-serif'
const TITLE_FONT = `400 18px ${BODY}`
const WORTH_FONT = `600 14px ${BODY}`
/** A card whose chips will not fit its band at body size sets them at
    caption size instead: still 44px tall, so still as easy to tap. */
const DENSE_TITLE_FONT = `400 14px ${BODY}`

let canvas: CanvasRenderingContext2D | null | undefined

/** Text width in a font, measured the way the browser will draw it. Outside
    a browser (the tests), an estimate from the font's average glyph. */
export function textWidth(text: string, font: string): number {
  if (canvas === undefined) {
    const real =
      typeof document !== 'undefined' &&
      typeof navigator !== 'undefined' &&
      !/jsdom/i.test(navigator.userAgent)
    canvas = real ? document.createElement('canvas').getContext('2d') : null
  }
  if (canvas) {
    canvas.font = font
    return canvas.measureText(text).width
  }
  const size = font.includes('18px') ? 18 : 14
  return text.length * size * (font.startsWith('600') ? 0.56 : 0.52)
}

/** The day's to-dos in the order the chips run: routine, then task. */
export function inChipOrder(tasks: readonly TaskEntry[]): TaskEntry[] {
  const known = new Set<string>(ROUTINES)
  const rank = (task: TaskEntry) =>
    ROUTINES.indexOf(known.has(task.routine) ? (task.routine as (typeof ROUTINES)[number]) : 'afternoon')
  return tasks
    .map((task, index) => ({ task, index }))
    .sort((a, b) => rank(a.task) - rank(b.task) || a.index - b.index)
    .map(({ task }) => task)
}

/** What the chip says at its right: the worth, and where it stands. For
    the five seconds after a claim, how to take it back. */
export function worthLabel(task: TaskEntry, undoing = false): string {
  if (undoing) {
    return copy.day.tapToUndo
  }
  if (task.status === 'claimed') {
    return copy.day.waitingFor(task.points)
  }
  // Once a week, and still to do: it says so, or a child reads it as today's.
  return task.every === 'week' && task.status === 'none'
    ? copy.day.worthWeek(task.points)
    : copy.day.worth(task.points)
}

/** One chip's width on a single line. */
export function chipWidth(task: TaskEntry, dense = false, undoing = false): number {
  return (
    CHIP.padLeft +
    CHIP.ring +
    CHIP.ringGap +
    textWidth(task.title, dense ? DENSE_TITLE_FONT : TITLE_FONT) +
    CHIP.worthGap +
    textWidth(worthLabel(task, undoing), WORTH_FONT) +
    CHIP.padRight +
    CHIP.border
  )
}

export type ChipLayout = {
  /** Rows the chips wrap to in the card's width. */
  rows: number
  /** Chips too wide for the card on one line: they wrap to two lines of
      caption inside the chip, and take a row to themselves. */
  long: Set<string>
  /** Set at caption size, to fit the band (see chipsFor). */
  dense: boolean
}

/** How the chips wrap in a width: greedy, as flex-wrap lays them out. */
export function chipLayout(
  tasks: readonly TaskEntry[],
  width: number,
  dense = false,
  /** The chip just claimed, whose worth reads "Tap again to undo". */
  undoing: string | null = null,
): ChipLayout {
  const long = new Set<string>()
  let rows = 0
  let used = 0
  for (const task of inChipOrder(tasks)) {
    let wide = chipWidth(task, dense, task.id === undoing)
    if (wide > width) {
      long.add(task.id)
      wide = width
    }
    if (rows === 0 || used + CHIP.gap + wide > width) {
      rows += 1
      used = wide
    } else {
      used += CHIP.gap + wide
    }
  }
  return { rows, long, dense }
}

/**
 * The chips as a card in `room` pixels of chip space draws them: at body
 * size when they fit there, at caption size when only that fits. Never
 * fewer of them — past caption size, the card grows instead.
 */
export function chipsFor(tasks: readonly TaskEntry[], width: number, room: number): ChipLayout {
  const body = chipLayout(tasks, width)
  if (chipsHeight(body.rows) <= room) {
    return body
  }
  const dense = chipLayout(tasks, width, true)
  return dense.rows < body.rows ? dense : body
}

/** The height the chips take: rows of 44 with 10 between, or the one row
    "Nothing to do" takes. */
export function chipsHeight(rows: number): number {
  return rows === 0 ? CHIP.height : rows * CHIP.height + (rows - 1) * CHIP.gap
}
