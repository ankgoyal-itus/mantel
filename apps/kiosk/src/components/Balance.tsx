import { type ReactNode, useState } from 'react'

import type { PointsSummary } from '../api/types'
import { copy } from '../copy'
import { flameFor, flameSize } from '../streak'
import Icon from './icons/Icon'

/**
 * A kid's points, beside their name.
 *
 * Two sizes: 28 on the dashboard, where it is one fact among many, and 40 in
 * kid mode, where it is what they came to look at. The week's total is not
 * here at either: kid mode draws the week as its own strip under the
 * routines, total and all.
 *
 * The number bounces once when it changes, and only then. `bumps` counts real
 * changes from a number we had already seen, so the first paint of the day is
 * still, and remounting the span on that count is what restarts the
 * animation. This is the only motion on the dashboard besides the flame.
 */
/**
 * Under this, the card says what to do instead of what the number is. "0 pts"
 * on day one reads as a failure rather than a beginning, and a single digit
 * is not worth the space it takes beside a name.
 */
const SHOW_NUMBER_FROM = 10

export default function Balance({
  points,
  large = false,
  under,
}: {
  points: PointsSummary | null
  large?: boolean
  /** A line beneath the number: cash saved in kid mode, the bar on the
      dashboard. */
  under?: ReactNode
}) {
  const balance = points ? points.balance : null
  const [seen, setSeen] = useState<{ value: number | null; bumps: number }>({
    value: balance,
    bumps: 0,
  })

  if (seen.value !== balance) {
    // Adjusting state while rendering, which React re-runs immediately. A
    // first sighting is not a change, so it does not count as a bump.
    setSeen({
      value: balance,
      bumps: seen.value !== null && balance !== null ? seen.bumps + 1 : seen.bumps,
    })
  }

  if (!points) {
    return null
  }

  // Three days, seven and fourteen, each a size bigger. A flame that is the
  // same at three days and at thirty says the thirty did not matter.
  const flame = flameFor(points.streak_days)
  return (
    <div className={large ? 'balance balance-large' : 'balance'}>
      <span className="balance-line">
        {flame === 'none' ? null : (
          <Icon
            name="flame"
            size={flameSize(flame, large)}
            className={`balance-flame balance-flame-${flame}`}
          />
        )}
        <span
          key={seen.bumps}
          className={points.balance < SHOW_NUMBER_FROM ? 'balance-points balance-start' : 'balance-points'}
          data-bump={seen.bumps || undefined}
        >
          {points.balance < SHOW_NUMBER_FROM
            ? copy.day.startEarning
            : copy.kid.points(points.balance)}
        </span>
      </span>
      {under}
    </div>
  )
}
