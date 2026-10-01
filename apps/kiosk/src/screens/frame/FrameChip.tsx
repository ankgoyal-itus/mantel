import type { Weather } from '../../api/types'
import Icon, { weatherIcon } from '../../components/icons/Icon'
import { useNow } from '../../components/useNow'
import { copy } from '../../copy'
import { clock12, degrees, meridiem } from '../../format'

/**
 * The clock and the weather over the photo, in one frosted pill top-right.
 *
 * It keeps its own clock, so the minute changes in place and the photo
 * underneath is never drawn again for it; and it sits above the crossfade,
 * so it never moves with a slide. By day the second line is today's high and
 * low; at night, tomorrow's. When the weather is old it says since when,
 * with the dot, as the night screen does.
 *
 * `bright` is the photo's corner under it, measured: over a bright sky the
 * pill deepens and the small line comes up to full ink, because the pill —
 * not the photo — has to carry the contrast.
 */
export default function FrameChip({
  weather,
  night,
  large,
  bright,
}: {
  weather: Weather | null
  night: boolean
  large: boolean
  bright: boolean
}) {
  const now = useNow()
  const current = weather?.now ?? null
  const day = night ? (weather?.tomorrow ?? null) : (weather?.today ?? null)

  const classes = ['frame-chip']
  if (night) {
    classes.push('frame-chip-night')
  }
  if (large) {
    classes.push('frame-chip-large')
  }
  if (bright) {
    classes.push('frame-chip-bright')
  }

  return (
    <div className={classes.join(' ')}>
      <span className="frame-chip-time">
        {clock12(now)}
        <span className="frame-chip-meridiem">{meridiem(now)}</span>
      </span>
      {current ? (
        <>
          <span className="frame-chip-rule" aria-hidden="true" />
          <Icon
            name={weatherIcon(current.icon, !current.is_day)}
            size={26}
            className="frame-chip-glyph"
          />
          <span className="frame-chip-weather">
            <span className="frame-chip-temp">{degrees(current.temp)}</span>
            <span className="frame-chip-range">
              {weather?.stale && weather.fetched_at ? (
                <>
                  <span className="stale-dot frame-chip-dot" aria-hidden="true" />
                  {copy.stale.since(clock12(new Date(weather.fetched_at)))}
                </>
              ) : day ? (
                night ? (
                  copy.frame.tomorrow(degrees(day.high), degrees(day.low))
                ) : (
                  copy.frame.range(degrees(day.high), degrees(day.low))
                )
              ) : null}
            </span>
          </span>
        </>
      ) : null}
    </div>
  )
}
