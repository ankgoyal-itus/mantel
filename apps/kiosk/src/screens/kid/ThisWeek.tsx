import type { PointsSummary } from '../../api/types'
import { copy } from '../../copy'

/** The tallest a day's bar is drawn, for the best day of the week. */
const BAR_MAX = 60

const DAYS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']

/**
 * This week, Monday to Sunday: a bar a day for the points earned, in their
 * colour, and the total. The best day of the week is the full 60px, so a
 * quiet week still has a shape; a day with nothing has no bar at all.
 */
export default function ThisWeek({
  points,
  today,
}: {
  points: PointsSummary | null
  /** Monday is 0. */
  today: number
}) {
  const days = points?.week_days ?? [0, 0, 0, 0, 0, 0, 0]
  const best = Math.max(...days, 1)
  const total = points ? points.this_week : 0
  return (
    <section className="this-week" aria-label={copy.kid.thisWeekSaid(total)}>
      <h3 className="this-week-head">
        <span>{copy.kid.thisWeekTitle}</span>
        <span className="this-week-total">+{total}</span>
      </h3>
      <div className="this-week-days" aria-hidden="true">
        {days.map((earned, index) => (
          <div key={index} className={index === today ? 'tw-day tw-today' : 'tw-day'}>
            <span className="tw-track">
              {earned > 0 ? (
                <span
                  className="tw-bar"
                  style={{ height: `${Math.max(4, Math.round((earned / best) * BAR_MAX))}px` }}
                />
              ) : null}
            </span>
            <span className="tw-letter">{DAYS[index]}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
