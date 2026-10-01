import type { Day, DayPicks, PointsSummary, TaskEntry, Weather } from '../api/types'
import { useNow } from '../components/useNow'
import { copy } from '../copy'
import { clock12, parseApiDate } from '../format'
import '../styles/day.css'
import ComingUp from './day/ComingUp'
import DayPlan from './day/DayPlan'
import FamilyStrip from './day/FamilyStrip'
import Header from './day/Header'
import KidColumn, { cardFitsWhole, plannedCardHeight } from './day/KidColumn'
import { minutesOfDay } from './day/agenda'
import { SCREEN, dashboardChipWidth, kidsRowHeight } from './day/budget'
import { weekMarks } from './day/myWeek'

/** The least room the Coming up card is drawn in: its head and three rows. */
const COMING_UP_MIN = 160

/** Under this much leftover, not even the two-day Coming up is added. */
const COMPACT_MIN = 60

/** What the leftover under the kid cards becomes. */
type Room = 'full' | 'compact' | 'none'

/** From 20:00 the header stops saying the weekday and says Tonight. */
const TONIGHT_HOUR = 20

/** Where the list opens: filtered to one child, or at one day — the
    family's rows only, from one of the family's pills. */
export type ListRequest = { kid?: string; date?: string; family?: boolean }

export type DayScreenProps = {
  today: Day | null
  tomorrow: Day | null
  /** The days after today, for the Coming up card when there is room. */
  upcoming?: Day[]
  /** Seven days of meal picks from today, for each child's "My week". */
  week?: DayPicks[]
  /** The dots on a child's card: their week strip, in kid mode. */
  onOpenWeek?: (kidId: string) => void
  weather: Weather | null
  onOpenMonth?: () => void
  /** Balances, keyed by kid id. Absent until the first fetch lands. */
  points?: Record<string, PointsSummary>
  /** Tapping a kid's face or name opens their own card. */
  onOpenKid?: (kidId: string, taskId?: string) => void
  /** How many claims and requests wait on a parent. */
  pending?: number
  /** True while a parent session is live. */
  session?: boolean
  /** The pill in the corner: the visible way in to the parent screen. */
  onParents?: () => void
  onParentsDone?: () => void
  /** When the night screen takes over. Closes the evening greeting. */
  nightStart?: string
  /** A long press on a waiting row: the way in to deciding it here. */
  onHoldTask?: (kidId: string, task: TaskEntry) => void
  /** The task being decided in place, once a parent is through the PIN. */
  deciding?: { kid: string; taskId: string } | null
  onApprove?: (task: TaskEntry) => void
  onDecline?: (task: TaskEntry) => void
  /** Per kid, a counter bumped when a parent says yes. One burst each. */
  cheers?: Record<string, number>
  /** The stage's height in pixels, which is what the kid cards are planned
      against. The shell measures it from innerHeight. */
  height?: number
  /** The stage's width, which the chips wrap in. */
  width?: number
  /** "+N more" and "N events": the list, filtered or opened at a day. */
  onOpenList?: (request: ListRequest) => void
}

export default function DayScreen({
  today,
  tomorrow,
  upcoming = [],
  week = [],
  onOpenWeek,
  weather,
  onOpenMonth,
  points = {},
  onOpenKid,
  pending = 0,
  session = false,
  onParents,
  onParentsDone,
  nightStart,
  onHoldTask,
  deciding = null,
  onApprove,
  onDecline,
  cheers = {},
  height = 768,
  width = 1024,
  onOpenList,
}: DayScreenProps) {
  const now = useNow()

  if (!today) {
    return (
      <div className="screen screen-center">
        <div className="clock">{clock12(now)}</div>
        <p className="empty">{copy.shell.waitingForApi}</p>
      </div>
    )
  }

  const jar = points.family ?? null
  const tonight = now.getHours() >= TONIGHT_HOUR
  const forecast = weather ?? today.weather
  // Saturday and Sunday, read off the payload's own date rather than the
  // device's: if the API is serving a stale day, the screen should agree
  // with the day it is actually showing.
  const showing = parseApiDate(today.date)
  const weekend = showing.getDay() === 0 || showing.getDay() === 6

  const minutes = minutesOfDay(now)
  const budget = kidsRowHeight(height)

  // The leftover goes to Coming up first: when both cards fit whole with
  // 160px under them to spare — their rows as they are, the footer being
  // the first thing to give — three more days go there, and the cards keep
  // their natural height. Only when they would not does the leftover go to
  // the cards, which then fill the band. Counted from the plan, not measured
  // after paint.
  //
  // Three cases, from what the cards would leave under them:
  //   - 160px or more (or both cards fit whole in the rest once the footer
  //     gives way): the bottom row keeps its 168 and Coming up takes the
  //     rest, three days of it;
  //   - 60 to 160: the meal rows go from 40 to 34, which gives 18 back, and
  //     a two-day Coming up fits in what there is;
  //   - under 60: nothing is added and the cards take the band.
  const chipWidth = dashboardChipWidth(width)
  const roomWithComingUp = budget - COMING_UP_MIN - SCREEN.gap
  const tallest = Math.max(
    ...today.kids.map((kid) => plannedCardHeight(kid, weekend, budget, chipWidth)),
  )
  const leftover = budget - tallest
  const room: Room =
    upcoming.length === 0
      ? 'none'
      : leftover >= COMING_UP_MIN + SCREEN.gap ||
          today.kids.every((kid) => cardFitsWhole(kid, weekend, roomWithComingUp, chipWidth))
        ? 'full'
        : leftover >= COMPACT_MIN
          ? 'compact'
          : 'none'
  const comingUp = room !== 'none'
  const cardBudget = room === 'full' ? roomWithComingUp : budget

  // One grid, the same in both orientations: header, family strip, the kids,
  // today and tomorrow. Every band but the kids' is a fixed height, and the
  // kids' is what is left — at 1024x768 that is 372px, which KidColumn plans
  // its rows against. A card ends where its content does; whatever the band
  // has over is space under the cards, never inside them.
  return (
    <div
      className={[
        'screen day',
        comingUp ? 'day-coming-up' : '',
        room === 'compact' ? 'day-compact-meals' : '',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <Header
        today={today}
        weather={forecast}
        now={now}
        tonight={tonight}
        onOpenMonth={onOpenMonth}
        pending={pending}
        session={session}
        onParents={onParents}
        onParentsDone={onParentsDone}
        nightStart={nightStart}
      />

      <FamilyStrip
        // A new day, or a changed calendar, is a new set of widths to measure.
        key={today.family_agenda.map((entry) => `${entry.start}${entry.title}`).join('|')}
        entries={today.family_agenda}
        jar={jar ? jar.balance : null}
        now={minutes}
        onMore={onOpenList ? () => onOpenList({ date: today.date }) : undefined}
        onPill={onOpenList ? () => onOpenList({ date: today.date, family: true }) : undefined}
      />

      <div className="day-kids">
        {today.kids.map((kid) => (
          <KidColumn
            key={kid.id}
            kid={kid}
            now={minutes}
            points={points[kid.id] ?? null}
            onOpen={onOpenKid}
            onMore={onOpenList ? (kidId) => onOpenList({ kid: kidId }) : undefined}
            marks={week.length > 0 ? weekMarks(week, kid.id) : undefined}
            onWeek={onOpenWeek}
            budget={cardBudget}
            chipWidth={chipWidth}
            weekend={weekend}
            cheer={cheers[kid.id] ?? 0}
            onHold={onHoldTask ? (task) => onHoldTask(kid.id, task) : undefined}
            deciding={deciding && deciding.kid === kid.id ? deciding.taskId : null}
            onApprove={onApprove}
            onDecline={onDecline}
          />
        ))}
      </div>

      {/* Today and tomorrow, side by side: what is being eaten, for the day
          you are in and the one you are about to be. */}
      <div className="day-bottom">
        <DayPlan day={today} label={copy.night.today} />
        {tomorrow ? (
          <DayPlan
            day={tomorrow}
            label={copy.tomorrow.label}
            weather={forecast}
            showDate
            onOpenList={onOpenList ? (date) => onOpenList({ date }) : undefined}
          />
        ) : null}
      </div>

      {room === 'full' ? <ComingUp days={upcoming.slice(0, 3)} /> : null}
      {room === 'compact' ? <ComingUp days={upcoming.slice(0, 2)} compact /> : null}
    </div>
  )
}
