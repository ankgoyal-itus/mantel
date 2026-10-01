import type { CSSProperties } from 'react'

import type {
  AgendaEntry,
  Day,
  Feeling,
  KidDay,
  MealSlot,
  Weather,
  WeatherDay,
} from '../api/types'
import Avatar from '../components/Avatar'
import Feelings from './night/Feelings'
import { kidVars } from '../kidVars'
import ParentPill from '../components/ParentPill'
import { useNow } from '../components/useNow'
import {
  clock12,
  clockIso,
  dateLong,
  dateShort,
  degrees,
  meridiem,
  parseApiDate,
  timeRange,
} from '../format'
import { toMinutes } from '../mode/machine'
import Icon from '../components/icons/Icon'
import { copy } from '../copy'
import { isOut, mealName } from '../out'
import { dayOffNote, observanceNames } from './day/badges'
import '../styles/night.css'
import { minutesOfDay } from './day/agenda'

/** Three fits the column without crowding it; the rest waits for morning. */
const MAX_PER_KID = 3
const DEFAULT_NIGHT_END = '06:30'

export type NightScreenProps = {
  today: Day | null
  tomorrow: Day | null
  weather: Weather | null
  /** settings.night.end, so the small hours know which morning is coming. */
  nightEnd?: string
  /** How many claims and requests wait on a parent, for the pill's badge. */
  pending?: number
  /** True while a parent session is live. */
  session?: boolean
  /** The pill in the corner: the visible way in to the parent screen. */
  onParents?: () => void
  onParentsDone?: () => void
  onOpenMonth?: () => void
  /** settings.feelings.enabled. Off, and none of this is drawn at all. */
  asking?: boolean
  /** What each child already tapped tonight, keyed by kid id. */
  felt?: Record<string, Feeling>
  onFelt?: (kidId: string, feeling: Feeling) => void
}

type Morning = { label: string; day: Day | null; forecast: WeatherDay | null }

/**
 * Which day the sleeping half of the house wakes into. Before midnight that is
 * tomorrow; after it, the API's "today" already is the coming morning, and a
 * 5am screen listing the day after would pack the wrong bag.
 */
export function nextMorning(
  now: Date,
  today: Day | null,
  tomorrow: Day | null,
  weather: Weather | null,
  nightEnd: string,
): Morning {
  const beforeDawn = minutesOfDay(now) < toMinutes(nightEnd)
  if (beforeDawn) {
    return { label: 'Today', day: today, forecast: weather ? weather.today : null }
  }
  return { label: 'Tomorrow', day: tomorrow, forecast: weather ? weather.tomorrow : null }
}

function entryLabel(entry: AgendaEntry): string {
  const when = entry.all_day ? '' : timeRange(entry.start, null)
  return when ? `${when} ${entry.title}` : entry.title
}

/** Themed, so useTheme's night dimming reaches the name. See KidColumn. */
function kidStyle(kid: KidDay): CSSProperties {
  return kidVars(kid.id, kid.color)
}

function Items({ entries }: { entries: AgendaEntry[] }) {
  if (entries.length === 0) {
    return <span className="night-empty">{copy.tomorrow.nothing}</span>
  }
  return (
    <span className="night-items">
      {entries.map((entry, index) => (
        <span key={`${entry.title}-${entry.start ?? 'all'}-${index}`} className="night-item">
          {entryLabel(entry)}
        </span>
      ))}
    </span>
  )
}

function KidRow({
  kid,
  asking,
  felt,
  onFelt,
}: {
  kid: KidDay
  /** True only when settings.feelings.enabled and the night has started. */
  asking: boolean
  felt: Feeling | null
  onFelt: (kidId: string, feeling: Feeling) => void
}) {
  return (
    <div className="night-row" style={kidStyle(kid)}>
      <Avatar name={kid.name} avatar={kid.avatar} size={24} />
      <span className="night-who night-who-kid">{kid.name}</span>
      <Items entries={kid.agenda.slice(0, MAX_PER_KID)} />
      {asking ? <Feelings kidId={kid.id} chosen={felt} onChosen={onFelt} /> : null}
    </div>
  )
}

function PackRow({ label, slot }: { label: string; slot: MealSlot | null }) {
  if (!slot) {
    return null
  }
  return (
    <div className="night-pack-row">
      <span className="night-pack-label">{label}</span>
      <span className="night-pack-name">{mealName(slot)}</span>
      {slot.note && !isOut(slot.id) ? <span className="night-pack-note">{slot.note}</span> : null}
    </div>
  )
}

/** Dinner is nobody's problem at bedtime — unless it is out, which is a
    thing to know before the day starts. */
function OutRow({ slot }: { slot: MealSlot }) {
  return (
    <div className="night-pack-row">
      <Icon name="storefront" size={22} className="meal-out-glyph" />
      <span className="night-pack-name">{copy.out.pack(slot.note)}</span>
    </div>
  )
}

export default function NightScreen({
  today,
  tomorrow,
  weather,
  nightEnd,
  pending = 0,
  session = false,
  onParents,
  onParentsDone,
  onOpenMonth,
  asking = false,
  felt = {},
  onFelt,
}: NightScreenProps) {
  const now = useNow()
  const morning = nextMorning(now, today, tomorrow, weather, nightEnd ?? DEFAULT_NIGHT_END)
  const day = morning.day
  const current = weather ? weather.now : null
  const forecast = morning.forecast

  // The date on the payload, not the device: if the API is serving a stale day,
  // the screen should say which one is actually on it.
  const date = today ? parseApiDate(today.date) : now
  const badge = day ? dayOffNote(day) : null
  const observances = day ? observanceNames(day.observances) : []

  const sunrise = forecast ? clockIso(forecast.sunrise) : ''
  const rain = forecast && forecast.precip_pct !== null ? `rain ${forecast.precip_pct}%` : null

  const breakfast = day ? day.meals.breakfast : null
  const lunch = day ? day.meals.lunch : null
  const dinnerOut = day && isOut(day.meals.dinner?.id) ? day.meals.dinner : null
  // Nothing at all on tomorrow: said once, not once per child.
  const quiet =
    day !== null &&
    day.family_agenda.length === 0 &&
    day.kids.every((kid) => kid.agenda.length === 0)

  return (
    <div className="screen screen-night night">
      {onParents ? (
        <ParentPill
          pending={pending}
          session={session}
          onOpen={onParents}
          onDone={onParentsDone ?? onParents}
        />
      ) : null}
      <div className="night-col">
        <div className="night-clock" data-clock="true">
          {clock12(now)}
          <span className="night-ampm">{meridiem(now)}</span>
        </div>
        {onOpenMonth ? (
          <button
            type="button"
            className="night-date night-date-button"
            data-night-live
            onClick={onOpenMonth}
          >
            {dateLong(date)}
          </button>
        ) : (
          <div className="night-date">{dateLong(date)}</div>
        )}

        {current || forecast ? (
          <div className="night-weather">
            {current ? (
              <div className="night-wx">{`${current.label} · ${degrees(current.temp)} now`}</div>
            ) : null}
            {forecast ? (
              <div className="night-wx night-wx-next">
                {[
                  `${morning.label} ${degrees(forecast.high)} / ${degrees(forecast.low)}`,
                  rain,
                  sunrise ? `sunrise ${sunrise}` : null,
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </div>
            ) : null}
          </div>
        ) : null}

        {day ? (
          <section className="night-block">
            <h2 className="night-head">
              <span>{morning.label}</span>
              <span className="night-head-date">{dateShort(parseApiDate(day.date))}</span>
              {observances.map((name) => (
                <span key={name} className="night-badge night-observance">
                  {name}
                </span>
              ))}
              {badge ? <span className="night-badge">{badge}</span> : null}
            </h2>
            {/* A tomorrow with nothing in it at all is one line and the
                moon, not a "Nothing scheduled" per child. */}
            {quiet ? (
              <p className="night-empty night-empty-day">
                <Icon name="moon" size={22} className="night-empty-glyph" />
                {copy.night.nothingTomorrow}
              </p>
            ) : null}
            {/* The children's rows stay when the check-in needs them. */}
            {quiet && !asking
              ? null
              : day.kids.map((kid) => (
                  <KidRow
                    key={kid.id}
                    kid={kid}
                    asking={asking}
                    felt={felt[kid.id] ?? null}
                    onFelt={onFelt ?? (() => undefined)}
                  />
                ))}
            {day.family_agenda.length > 0 ? (
              <div className="night-row">
                <span className="night-who">{copy.night.family}</span>
                <Items entries={day.family_agenda.slice(0, MAX_PER_KID)} />
              </div>
            ) : null}
          </section>
        ) : null}

        {/* Always there, so an empty one says so: now the children pick the
            week, a morning with nothing chosen yet is a thing to notice at
            bedtime, not a block that quietly is not drawn. */}
        <section className="night-block night-pack">
          <h2 className="night-head">
            <span>{copy.night.pack}</span>
          </h2>
          {breakfast || lunch || dinnerOut ? (
            <>
              <PackRow label="Breakfast" slot={breakfast} />
              <PackRow label="Lunch" slot={lunch} />
              {dinnerOut ? <OutRow slot={dinnerOut} /> : null}
            </>
          ) : (
            <p className="night-pack-none">{copy.night.nothingPacked}</p>
          )}
        </section>
      </div>
    </div>
  )
}
