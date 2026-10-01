import type { Day, Weather } from '../../api/types'
import Icon, { weatherIcon } from '../../components/icons/Icon'
import ParentPill from '../../components/ParentPill'
import { copy } from '../../copy'
import { clock12, degrees, meridiem, nameList, parseApiDate } from '../../format'
import { badgeFor } from './badges'
import Illustration from '../../components/illustrations/Illustration'
import { greetingAt } from './greeting'

/**
 * Three sizes and nothing else: the date and the temperature at heading size,
 * the clock large in the middle, the high and low small and muted.
 */
export default function Header({
  today,
  weather,
  now,
  tonight,
  onOpenMonth,
  pending = 0,
  session = false,
  onParents,
  onParentsDone,
  nightStart,
}: {
  today: Day
  weather: Weather | null
  now: Date
  tonight: boolean
  onOpenMonth?: () => void
  /** How many things wait on a parent. Drawn as one small muted dot. */
  pending?: number
  /** True while a parent session is live, which changes what the pill says. */
  session?: boolean
  /** Opens the PIN pad, or the parent screen when a session is already open. */
  onParents?: () => void
  onParentsDone?: () => void
  /** When the night screen takes over, which closes the evening greeting. */
  nightStart?: string
}) {
  // The date comes from the payload, not the device: if the API is serving a
  // stale day, the header should say which day is actually on screen.
  const date = parseApiDate(today.date)
  const current = weather ? weather.now : null
  const forecast = weather ? weather.today : null
  const badge = badgeFor(today)
  const weekday = date.toLocaleDateString(undefined, { weekday: 'long' })
  // Named in the order family.yaml lists them, which is the order the payload
  // carries through.
  // Saturday and Sunday say so in the festival colour, with the pill that
  // goes with it. A weekend should not look like a Tuesday with nothing on.
  const weekend = date.getDay() === 0 || date.getDay() === 6
  const greeting = greetingAt(now, nightStart)
  const hello =
    greeting === 'morning'
      ? copy.day.goodMorning(nameList(today.kids.map((kid) => kid.name)))
      : greeting === 'night'
        ? copy.day.goodNight
        : null

  return (
    <header className="day-header">
      <div className="day-header-left">
        {onOpenMonth ? (
          // The way into the month calendar, and the only tappable thing here.
          <button
            type="button"
            className={weekend ? 'day-date day-date-weekend clamp-1' : 'day-date clamp-1'}
            onClick={onOpenMonth}
          >
            {tonight ? copy.shell.tonight : <DateSaid date={date} weekday={weekday} />}
          </button>
        ) : (
          <div className={weekend ? 'day-date day-date-weekend clamp-1' : 'day-date clamp-1'}>
            {tonight ? copy.shell.tonight : <DateSaid date={date} weekday={weekday} />}
          </div>
        )}
        {/* One line under the date, inside the header's 88px: what kind of
            day it is, then the greeting in whatever room is over, and not at
            all when that is too little to read it in. */}
        <div className="day-sub">
          {weekend && !badge ? (
            <div className="pill clamp-1">{copy.day.weekend}</div>
          ) : null}
          {/* What kind of day it is: a label, so an outline in the page's
              ink. The calendar's colours stay on the calendar. */}
          {badge ? <div className="pill clamp-1">{badge}</div> : null}
          <span className="hide-under-140">
            {hello ? (
              <span className="day-hello clamp-1">
                {/* The sun in the morning and the moon at bedtime: the one
                    place a drawing says something the words do not. */}
                <Illustration name={greeting === 'morning' ? 'sun' : 'moon'} size={22} />
                {/* Under 900px the names go and the greeting stays whole,
                    rather than ellipsing halfway through a name. */}
                <span className="hello-long">{hello}</span>
                {greeting === 'morning' ? (
                  <span className="hello-short">{copy.day.goodMorningShort}</span>
                ) : null}
              </span>
            ) : null}
          </span>
        </div>
      </div>

      <div className="day-clock" data-clock="true">
        {clock12(now)}
        <span className="day-meridiem">{meridiem(now)}</span>
      </div>

      <div className="day-weather">
        {current ? (
          <Icon name={weatherIcon(current.icon, !current.is_day)} size={34} className="wx-icon" />
        ) : null}
        <div className="wx-text">
          <div className="wx-now">{current ? degrees(current.temp) : '—'}</div>
          <div className="wx-detail">
            {forecast ? `${degrees(forecast.high)} / ${degrees(forecast.low)}` : copy.shell.noForecast}
          </div>
        </div>
      </div>

      {onParents ? (
        <ParentPill
          pending={pending}
          session={session}
          onOpen={onParents}
          onDone={onParentsDone ?? onParents}
        />
      ) : null}
    </header>
  )
}

/** "Wednesday 23", or upright, where the header is 720 wide, "Wed 23". */
function DateSaid({ date, weekday }: { date: Date; weekday: string }) {
  return (
    <>
      <span className="day-date-long">{`${weekday} ${date.getDate()}`}</span>
      <span className="day-date-short">{`${weekday.slice(0, 3)} ${date.getDate()}`}</span>
    </>
  )
}
