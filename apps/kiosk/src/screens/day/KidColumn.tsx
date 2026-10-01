import type { CSSProperties, ReactNode } from 'react'

import type { KidDay, PointsSummary, TaskEntry } from '../../api/types'
import Avatar from '../../components/Avatar'
import Balance from '../../components/Balance'
import Confetti from '../../components/Confetti'
import Icon, { ICONS, type IconName } from '../../components/icons/Icon'
import Illustration from '../../components/illustrations/Illustration'
import { copy } from '../../copy'
import { timeRange } from '../../format'
import { kidVars } from '../../kidVars'
import { relativeTime } from '../../routines'
import { classifyAgenda, isAccented } from './agenda'
import {
  KID_MAX_AGENDA,
  MAX_AGENDA_ROWS,
  dashboardChipWidth,
  cardHeight,
  chipRoom,
  planCard,
  planKidCard,
} from './budget'
import { type ChipLayout, chipLayout, chipsFor, chipsHeight, inChipOrder } from './chips'
import type { WeekMarks } from './myWeek'
import TaskChip from './TaskChip'
import { earnedBy, stillToEarn } from './taskList'
import { cleanTitle } from './titles'

/**
 * Where no budget is passed (the rail, and tests): two agenda rows. The
 * dashboard and the open card both count their rows against the height they
 * have (see budget.ts); every to-do is always drawn.
 */
const MAX_AGENDA = KID_MAX_AGENDA

/** The card's own tokens. Confetti resolves them against the card element,
    because a canvas cannot be given a CSS variable to paint with. */
const CHEER_TOKENS = ['--kid', '--ink-good']

/** A reward's glyph, or the star every reward falls back to. */
function glyphFor(name: string): IconName {
  return (ICONS as readonly string[]).includes(name) ? (name as IconName) : 'star'
}

function kidStyle(kid: { id: string; color: string }): CSSProperties {
  // Themed, so useTheme's night handling reaches it. See the theme hook.
  return kidVars(kid.id, kid.color)
}

/** A dashboard card's chips: at body size, or at caption size when only
    that fits the band with the agenda at its least. */
function dashboardChips(kid: KidDay, agenda: number, height: number, width: number): ChipLayout {
  return chipsFor(kid.tasks, width, chipRoom({ height, agenda, bunting: kid.birthday }))
}

/**
 * Whether this child's card fits whole in `height`: every agenda row it would
 * draw with room to spare, every to-do at 44px, nothing scrolling. The
 * footer does not count — it is the first thing on a card to give way — so
 * a card that fits without it still counts as fitting. The day screen asks
 * this of both cards to decide whether Coming up gets the leftover.
 */
export function cardFitsWhole(
  kid: KidDay,
  weekend: boolean,
  height: number,
  width: number,
): boolean {
  const agenda = (weekend ? kid.agenda.filter((entry) => entry.source !== 'school') : kid.agenda)
    .length
  const chips = chipsHeight(dashboardChips(kid, agenda, height, width).rows)
  const plan = planCard({ height, agenda, chips, bunting: kid.birthday })
  // Every row it wants, and all of them inside `height`: with nothing on the
  // calendar the plan's agenda is 0 whether or not the card fit.
  return (
    plan.agenda === Math.min(agenda, MAX_AGENDA_ROWS) &&
    cardHeight(plan, { agenda, chips, bunting: kid.birthday }) <= height
  )
}

/** The card's height as planned in `height`, for the day screen's leftover. */
export function plannedCardHeight(
  kid: KidDay,
  weekend: boolean,
  height: number,
  width: number,
): number {
  const agenda = (weekend ? kid.agenda.filter((entry) => entry.source !== 'school') : kid.agenda)
    .length
  const chips = chipsHeight(dashboardChips(kid, agenda, height, width).rows)
  const foot = earnedBy(kid.tasks) > 0 || stillToEarn(kid.tasks) > 0
  const plan = planCard({ height, agenda, chips, bunting: kid.birthday, foot })
  return cardHeight(plan, { agenda, chips, bunting: kid.birthday })
}

export default function KidColumn({
  kid,
  now,
  avatarSize = 56,
  showTasks = true,
  points = null,
  claimable = false,
  compact = false,
  weekend = false,
  onClaim,
  onHold,
  deciding = null,
  onApprove,
  onDecline,
  cheer = 0,
  nodding = false,
  onOpen,
  onMore,
  marks,
  pulse = null,
  undoing = null,
  onWeek,
  budget,
  chipWidth = dashboardChipWidth(1024),
  belowTasks,
  footer,
  underBalance,
}: {
  kid: KidDay
  now: number
  avatarSize?: 56 | 24
  showTasks?: boolean
  points?: PointsSummary | null
  /** True in kid mode, where the to-do rows become real. */
  claimable?: boolean
  /**
   * The narrow rail beside an open card. It shows when a thing starts and
   * not when it ends: the range costs 150px the title cannot spare here.
   */
  compact?: boolean
  /** Saturday and Sunday, when the school feed's rows are hidden. */
  weekend?: boolean
  onClaim?: (task: TaskEntry) => void
  /** A long press on a waiting row, on the dashboard only. */
  onHold?: (task: TaskEntry) => void
  /** The task id being decided in place, if any. */
  deciding?: string | null
  onApprove?: (task: TaskEntry) => void
  onDecline?: (task: TaskEntry) => void
  /** Bumped when a parent says yes: one burst of confetti on this card. */
  cheer?: number
  /** Whose card it is, so the nod plays when it opens into kid mode. */
  nodding?: boolean
  /** Tapping the card — its head, its body, or one of its chips — opens this
      kid's own card; a chip says which one it was. */
  onOpen?: (kidId: string, taskId?: string) => void
  /** Kid mode: the chip tapped on the wall, pulsing once as the card opens. */
  pulse?: string | null
  /** Kid mode: the chip just claimed, while it can still be taken back. */
  undoing?: string | null
  /** The "+N more" agenda row: the rest of this kid's days, in the list. */
  onMore?: (kidId: string) => void
  /** Their week of meal picks, as dots and any news (the dashboard only). */
  marks?: WeekMarks
  /** The dots: their own week strip, in kid mode. */
  onWeek?: (kidId: string) => void
  /**
   * The most the card may be, in pixels. Given on the dashboard, where the
   * card is planned row by row to fit it and ends where its content does.
   */
  budget?: number
  /** The width the chips wrap in: the card's, from the stage (budget.ts). */
  chipWidth?: number
  /** Under the chips, before the starred reward: the week. Kid mode only. */
  belowTasks?: ReactNode
  /** What the card can do, at the bottom of it. Kid mode only. */
  footer?: ReactNode
  /** A line under the balance, for what is about points rather than today. */
  underBalance?: ReactNode
}) {
  // At the weekend the school feed's rows are somebody else's business: a
  // Saturday with "Girls Volleyball practice" on it reads as a school day.
  const showing = weekend ? kid.agenda.filter((entry) => entry.source !== 'school') : kid.agenda
  const classified = classifyAgenda(showing, now)

  // What the day is worth: said yes to, and still on the table.
  const approved = earnedBy(kid.tasks)
  const toEarn = stillToEarn(kid.tasks)

  // Every to-do, as chips, in the card's width: how many rows they wrap to,
  // and which are too long for one line.
  const budgeted = budget !== undefined && !claimable && !compact
  const layout = budgeted
    ? dashboardChips(kid, classified.length, budget, chipWidth)
    : chipLayout(kid.tasks, chipWidth, false, undoing)
  const chips = chipsHeight(layout.rows)

  const plan = budgeted
    ? planCard({
        height: budget,
        agenda: classified.length,
        chips,
        bunting: kid.birthday,
        foot: approved > 0 || toEarn > 0,
      })
    : null
  // Kid mode's open card, planned the same way against the screen it has.
  const kidPlan =
    claimable && budget !== undefined
      ? planKidCard({
          height: budget,
          agenda: classified.length,
          chips,
          saving: (points?.saving_for.length ?? 0) > 0,
        })
      : null
  const agenda = classified.slice(0, plan ? plan.agenda : kidPlan ? kidPlan.agenda : MAX_AGENDA)
  const hiddenAgenda = classified.length - agenda.length

  // "3 things today · Piano at 4", the line a child reads before the rows.
  // Everything on the card, not just the chores: it sits above three agenda
  // rows and two to-dos, and a count that only covered one of those read as
  // wrong — "2 things today" over three visible rows.
  const next = classified.find(({ status }) => status === 'now' || status === 'next')
  //
  // Two halves. What is kept whole — news from their week of meal picks,
  // and what today could still be worth — goes first; the count ("6 things
  // today", and the next thing when there is no news) comes after it and is
  // the half that ellipsises. A line too short for both loses the count,
  // never "Yours is Saturday" or "up to +5 today".
  const notice = marks?.notice ?? null
  const kept: string[] = []
  if (notice) {
    kept.push(
      notice.kind === 'contested' ? copy.day.parentsDecide : copy.day.yoursIs(notice.weekday),
    )
  }
  if (!claimable && toEarn > 0) {
    kept.push(copy.day.upTo(toEarn))
  }
  const rest = [copy.day.things(classified.length + kid.tasks.length)]
  // The next thing goes unsaid under news: it is the row directly below.
  if (!notice && next) {
    const { title } = cleanTitle(next.entry.title, next.entry.where)
    const near = relativeTime(now, next.entry.start, next.entry.end)
    rest.push(
      near ? copy.day.nextIn(title, near) : copy.day.nextAt(title, timeRange(next.entry.start, null)),
    )
  }
  const keptLine = kept.join(' · ')
  // A no-break space before the dot: a flex item drops a leading plain one.
  const restLine = `${keptLine ? '\u00a0· ' : ''}${rest.join(' · ')}`

  const balance = points ? points.balance : 0

  // Two rewards on the open card; one on the dashboard.
  //
  // The dashboard used to show none, on the arithmetic that two cards have no
  // room for a bar apiece — which is true of two bars and not of one. A star
  // that shows nothing anywhere a child passes is a star that does nothing,
  // and the bar is the whole point of having starred it. The one shown is
  // the one nearest done, because that is the one worth walking past.
  const wanted = points?.saving_for ?? []
  const nearest = [...wanted].sort(
    (first, second) => first.cost - balance - (second.cost - balance),
  )
  // One bar on the open card too: the first reward they starred. Two bars
  // was two answers to "what am I saving for", and the card has one row.
  const saving = claimable ? wanted.slice(0, 1) : []

  // On the dashboard the bar rides under the points rather than taking a row
  // of its own. The card is full — two agenda rows, an open routine and its
  // chores come to 428 of the 434 there are — and the header is not, because
  // its height is the avatar's and the number under the name does not use
  // it. So this costs nothing, and it is where points belong anyway.
  //
  // No words on it: the glyph at the end of the track is the thing being
  // saved for, which is what the bar in kid mode already leads with. The
  // name and the gap are on the open card, one tap away.
  const mini = claimable ? null : (nearest[0] ?? null)
  const miniBar = mini ? (
    <span
      className="save-mini"
      role="img"
      aria-label={`${mini.name}, ${copy.day.toGo(Math.max(0, mini.cost - balance))}`}
    >
      <span
        className="save-fill"
        style={{
          width: `${Math.round(
            (mini.cost > 0 ? Math.min(1, balance / mini.cost) : 1) * 100,
          )}%`,
        }}
      />
      <Icon name={glyphFor(mini.glyph)} size={18} className="save-glyph" />
    </span>
  ) : null

  const head = (
    <>
      <Avatar name={kid.name} avatar={kid.avatar} size={avatarSize} nodding={nodding} />
      <h2 className="kid-name">{kid.name}</h2>
      <Balance points={points} large={claimable} under={underBalance ?? miniBar} />
    </>
  )

  // The agenda's own "+N more": a row at the foot of the rows on the
  // dashboard, where it opens the list at this child; a word on the end of
  // the headline in kid mode, where the card has no list to open.
  // Squeezed out altogether by the chips, the agenda is the headline's
  // "+N more" and draws nothing of its own.
  const agendaFolded = plan !== null && plan.agenda === 0 && hiddenAgenda > 0
  const moreAgenda =
    plan && !agendaFolded && hiddenAgenda > 0 ? (
      <li className="row row-more">
        {onMore ? (
          <button type="button" className="row-more-tap" onClick={() => onMore(kid.id)}>
            {copy.day.moreRow(hiddenAgenda)}
          </button>
        ) : (
          copy.day.moreRow(hiddenAgenda)
        )}
      </li>
    ) : null

  return (
    // On the wall, and on the rail beside an open card, the whole card is
    // the way in: a child aims at their card, not at their name on it. The
    // buttons inside it (the chips, the dots, "+N more") keep their own jobs.
    <section
      className={['kid', compact ? 'kid-compact' : '', budgeted ? 'kid-budgeted' : '']
        .filter(Boolean)
        .join(' ')}
      style={kidStyle(kid)}
      data-kid-card={kid.id}
      onClick={
        onOpen && !claimable
          ? (event) => {
              if (!(event.target as Element).closest('button')) {
                onOpen(kid.id)
              }
            }
          : undefined
      }
    >
      {onOpen ? (
        <button type="button" className="kid-head kid-head-tap" onClick={() => onOpen(kid.id)}>
          {head}
        </button>
      ) : (
        <div className="kid-head">{head}</div>
      )}
      {/* One line, on the day, in their own colour. It is the only thing on
          this screen that is not information. */}
      {kid.birthday && !compact ? (
        <p className="kid-bunting">
          <Illustration name="party" size={26} />
          {copy.day.happyBirthday(kid.name)}
        </p>
      ) : null}

      {/* The headline is the agenda's heading as well as its summary: it
          sits directly above the rows and already says how many things today
          holds, so a "Today" over the top of it would be the same word twice. */}
      {compact ? null : (
        <p className="kid-headline">
          <span className="kid-headline-what clamp-1">
            {keptLine ? <span className="kid-headline-keep clamp-1">{keptLine}</span> : null}
            <span className="kid-headline-rest clamp-1">{restLine}</span>
          </span>
          {(!plan || agendaFolded) && hiddenAgenda > 0 ? (
            <span className="more">{copy.day.more(hiddenAgenda)}</span>
          ) : null}
        </p>
      )}
      {/* My week: a dot a day from today — filled where they picked a meal,
          ringed where a pick of theirs is contested. Its own 16px line under
          the headline; the button reaches past it to a finger's 44px. */}
      {marks && !compact && !claimable ? (
        <div className="kid-week-line">
          <button
            type="button"
            className="kid-week"
            aria-label={copy.day.myWeek}
            onClick={() => onWeek?.(kid.id)}
          >
            {marks.dots.map((dot, index) => (
              <span key={index} className={`kid-week-dot kid-week-${dot}`} aria-hidden="true" />
            ))}
          </button>
        </div>
      ) : null}
      {compact && hiddenAgenda > 0 ? (
        <h3 className="kid-section">
          {copy.day.today}
          <span className="more">{copy.day.more(hiddenAgenda)}</span>
        </h3>
      ) : null}
      {agendaFolded ? null : agenda.length === 0 && !moreAgenda ? (
        // Drawn, not sentenced: an afternoon with nothing in it is a good
        // thing, and a line of grey text saying so reads as a fault.
        <p className="empty empty-drawn">
          <Illustration name="kite" size={plan ? 32 : 44} />
          {copy.day.freeAfternoon}
        </p>
      ) : (
        <ul className="rows">
          {agenda.map(({ entry, status }, index) => {
            const { title, where } = cleanTitle(entry.title, entry.where)
            const school = entry.source === 'school'
            const near = entry.all_day ? null : relativeTime(now, entry.start, entry.end)
            return (
              <li
                key={`${entry.title}-${entry.start ?? 'all'}-${index}`}
                className={`row row-${status}`}
              >
                {/* Whose row, as a 6px dot in its colour: the kid's own, or
                    school green. The row now or next gets a ring round it. */}
                <span
                  className={[
                    'row-dot',
                    school ? 'row-dot-school' : '',
                    isAccented(status) ? 'row-dot-on' : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  aria-hidden="true"
                />
                {/* When it starts, never when it ends: within the hour the
                    row says "in 20 min" instead, and the range was the most
                    expensive and least read thing on the card. */}
                <span className="row-time clamp-1">
                  {entry.all_day ? copy.day.allDay : (near ?? timeRange(entry.start, null))}
                </span>
                {/* The title is the row: its natural width, ellipsised only
                    if it alone would overrun. The place takes what is left
                    and is not drawn under 120px of it. */}
                <span className="row-title clamp-1">{title}</span>
                <span className="hide-under-120">
                  {where ? <span className="row-where clamp-1">{where}</span> : null}
                </span>
                {school ? <Icon name="school" size={20} className="row-glyph" /> : null}
              </li>
            )
          })}
          {moreAgenda}
        </ul>
      )}

      {!showTasks ? null : kid.tasks.length === 0 ? (
        <p className="empty empty-drawn">
          <Illustration name="cat" size={plan ? 32 : 44} />
          {copy.day.nothingToDo}
        </p>
      ) : (
        // Every to-do of the day as a chip, routine order then task order,
        // wrapping as it must: no headers, no "+N more", nothing scrolling.
        <ul className={layout.dense ? 'chips chips-dense' : 'chips'}>
          {inChipOrder(kid.tasks).map((task) => (
            <TaskChip
              key={task.id}
              task={task}
              claimable={claimable}
              long={layout.long.has(task.id)}
              onClaim={onClaim}
              onOpen={onOpen && !claimable ? () => onOpen(kid.id, task.id) : undefined}
              pulse={pulse === task.id}
              undoing={undoing === task.id}
              onHold={onHold}
              deciding={deciding === task.id}
              onApprove={onApprove}
              onDecline={onDecline}
            />
          ))}
        </ul>
      )}

      {plan?.foot ? (
        <p className="kid-foot">
          <span className="kid-foot-earned">{copy.day.approvedToday(approved)}</span>
          {' · '}
          <span className="kid-foot-left">{copy.day.stillToEarn(toEarn)}</span>
        </p>
      ) : null}

      {belowTasks}

      {saving.length > 0 ? (
        <div className="saving">
          {saving.map((pick) => {
            const short = Math.max(0, pick.cost - balance)
            const along = pick.cost > 0 ? Math.min(1, balance / pick.cost) : 1
            return (
              <div className="save" key={pick.reward_id}>
                <div className="save-line">
                  <span className="save-name clamp-1">{pick.name}</span>
                  <span className="save-left">
                    {short === 0 ? copy.day.ready : copy.day.toGo(short)}
                  </span>
                </div>
                <div className="save-track">
                  <span className="save-fill" style={{ width: `${Math.round(along * 100)}%` }} />
                  <Icon name={glyphFor(pick.glyph)} size={20} className="save-glyph" />
                </div>
              </div>
            )
          })}
        </div>
      ) : null}

      {footer}
      <Confetti fire={cheer} tokens={CHEER_TOKENS} />
    </section>
  )
}
