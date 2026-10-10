/**
 * The day screen's vertical budget, counted in rows.
 *
 * The screen is one grid in both orientations — header, family strip, the
 * kids, the two day cards — and every row inside a kid card is a fixed
 * height. So what fits is arithmetic, done here on the same numbers the
 * tokens in theme.css set, rather than measured after the fact: a card that
 * measures itself has already drawn the row it then has to take away.
 *
 * What gives, when there is not room for everything, is decided in this
 * order: the footer, then agenda rows (into "+N more"). The to-dos are chips
 * and never give: the card grows to hold them.
 * The head and the headline never give.
 */

/** The four bands and the space round them. Mirrors --day-* in theme.css. */
export const SCREEN = {
  margin: 24,
  gap: 16,
  header: 88,
  strip: 44,
  kidsMin: 340,
  bottom: 168,
} as const

/** The rows of a kid card. Mirrors --card-* in theme.css. */
export const CARD = {
  /** 8px of padding top and bottom, and the hairline round the card. */
  chrome: 18,
  head: 64,
  headline: 24,
  /** "My week": seven dots on their own 16px line under the headline. */
  week: 16,
  row: 44,
  /** The space between the agenda and the chips. */
  chipGap: 10,
  foot: 32,
  /** The birthday line, on the one day it is drawn. */
  bunting: 32,
} as const

/** Agenda rows before the rest become "+N more". */
export const MAX_AGENDA_ROWS = 3

/** The kids' band, from the stage's height: whatever the other three leave. */
export function kidsRowHeight(stageHeight: number): number {
  const fixed = SCREEN.header + SCREEN.strip + SCREEN.bottom
  const space = stageHeight - 2 * SCREEN.margin - fixed - 3 * SCREEN.gap
  return Math.max(SCREEN.kidsMin, space)
}

export type CardPlan = {
  /** Agenda rows drawn. */
  agenda: number
  /** Agenda entries behind the "+N more" row; 0 when there is no such row. */
  agendaMore: number
  /** Whether the "+4 today · +7 still to earn" footer has room. */
  foot: boolean
}

/**
 * How much of one child's day fits a card of this height.
 *
 * The to-dos are chips, every one of them, at the height they wrap to
 * (`chips`, from chips.ts): they never give. What does, in order: the
 * footer, then agenda rows into "+N more" (down to one). An empty agenda
 * still takes a row, because it says so in words.
 */
export function planCard({
  height,
  agenda,
  chips,
  bunting = false,
  foot = false,
}: {
  /** The kids' band, which is the most a card may be. */
  height: number
  /** Agenda entries today. */
  agenda: number
  /** The chips' height, in pixels. */
  chips: number
  bunting?: boolean
  /** True when there is something for the footer to say. */
  foot?: boolean
}): CardPlan {
  const fixed =
    CARD.chrome + CARD.head + CARD.headline + CARD.week + CARD.chipGap + chips +
    (bunting ? CARD.bunting : 0)
  const most = Math.min(agenda, MAX_AGENDA_ROWS)
  // Down to no agenda rows at all: the headline already counts the day's
  // things, and its "+N more" says where they went. A to-do is never what
  // gives way.
  for (let shown = most; shown >= 0; shown -= 1) {
    const agendaMore = agenda - shown
    const left = height - fixed - agendaRowCount(agenda, shown, agendaMore) * CARD.row
    if (left >= 0) {
      return { agenda: shown, agendaMore, foot: foot && left >= CARD.foot }
    }
  }
  // Even with no agenda rows the chips need more: the card grows past the
  // band rather than hide one.
  return { agenda: 0, agendaMore: agenda, foot: false }
}

/** The agenda's rows on the card: the empty day's one, or those shown and
    their "+N more" — or none, when the agenda has folded into the headline. */
function agendaRowCount(agenda: number, shown: number, more: number): number {
  if (agenda === 0) {
    return 1
  }
  return shown === 0 ? 0 : shown + (more > 0 ? 1 : 0)
}

/**
 * The most room a card's chips can have in `height`: everything else at its
 * least — one agenda row and its "+N more", no footer.
 */
export function chipRoom({
  height,
  agenda,
  bunting = false,
}: {
  height: number
  agenda: number
  bunting?: boolean
}): number {
  const agendaRows = agenda <= 1 ? 1 : 2
  return (
    height -
    CARD.chrome -
    CARD.head -
    CARD.headline -
    CARD.week -
    (bunting ? CARD.bunting : 0) -
    agendaRows * CARD.row -
    CARD.chipGap
  )
}

/**
 * What a planned card measures, in pixels: the same rows KidColumn draws.
 */
export function cardHeight(
  plan: CardPlan,
  { agenda, chips, bunting = false }: { agenda: number; chips: number; bunting?: boolean },
): number {
  const agendaRows = agendaRowCount(agenda, plan.agenda, plan.agendaMore)
  return (
    CARD.chrome +
    CARD.head +
    CARD.headline +
    CARD.week +
    (bunting ? CARD.bunting : 0) +
    agendaRows * CARD.row +
    CARD.chipGap +
    chips +
    (plan.foot ? CARD.foot : 0)
  )
}

/**
 * Kid mode's open card: the stage less the band over it and the padding
 * round it. Mirrors .kid-mode and .kid-mode-band in kid.css.
 */
export const KID_SCREEN = {
  /** 16px above the band, the 44px band with 8px inside it top and bottom
      (60), 16px under it, and 8px under the card. */
  chrome: 100,
} as const

/** The rows of the open card, as kid.css draws them. */
export const KID_CARD = {
  chrome: 18,
  /** The 72px face and the balance beside it, and the 8px under them. */
  head: 80,
  /** The headline and its 8px. */
  headline: 31,
  /** An agenda row, 56px where a finger lands. */
  row: 56,
  /** The space above the chips. */
  chipGap: 10,
  /** This week: the title, the 60px bars and the day letters, and 8px. */
  week: 113,
  /** The starred reward: its name and its bar, and 8px. */
  save: 57,
  /** Rewards, Pick a meal and the jar. */
  actions: 60,
  /** The bank chips under the balance: 44px to tap beneath the 34px number,
      which is 78 of a head drawn at 72 — and 8 to spare. */
  bank: 8,
} as const

/** Agenda rows on the open card when there is room for them. */
export const KID_MAX_AGENDA = 2

export function kidCardHeight(stageHeight: number): number {
  return stageHeight - KID_SCREEN.chrome
}

/**
 * How many agenda rows and to-dos the open card draws in this height.
 *
 * The to-dos are what a child came to the card to do, so the agenda gives
 * way first — down to one row, the rest counted on the headline — and only
 * then do the to-dos, never below one. Everything else on the card is a
 * fixed row and never gives.
 */
export function planKidCard({
  height,
  agenda,
  chips,
  saving,
  bank = false,
}: {
  height: number
  agenda: number
  /** The chips' height, in pixels (chips.ts). */
  chips: number
  /** Whether a reward is starred. */
  saving: boolean
  /** Whether either bank has anything in it, so its chips are drawn. */
  bank?: boolean
}): { agenda: number } {
  const fixed =
    KID_CARD.chrome +
    KID_CARD.head +
    KID_CARD.headline +
    KID_CARD.chipGap +
    chips +
    KID_CARD.week +
    KID_CARD.actions +
    (saving ? KID_CARD.save : 0) +
    (bank ? KID_CARD.bank : 0)
  // The chips are what a child came to tap, so they never give; the agenda
  // does, down to one row, the rest counted on the headline.
  let shown = Math.min(agenda, KID_MAX_AGENDA)
  while (shown > 1 && fixed + shown * KID_CARD.row > height) {
    shown -= 1
  }
  return { agenda: shown }
}

/**
 * The width the chips have to wrap in, from the stage's width — the same
 * arithmetic the stylesheets lay the cards out with. On the dashboard: half
 * the stage less its margins and the gap, less the card's padding and
 * hairline. In kid mode: two thirds of the screen less the same.
 */
export function dashboardChipWidth(stageWidth: number): number {
  return (stageWidth - 2 * SCREEN.margin - SCREEN.gap) / 2 - 2 * CARD_PAD - 2
}

export function kidChipWidth(stageWidth: number): number {
  return ((stageWidth - 2 * CARD_PAD - SCREEN.gap) * 2) / 3 - 2 * CARD_PAD - 2
}

/** A card's padding either side (--pad). */
const CARD_PAD = 24
