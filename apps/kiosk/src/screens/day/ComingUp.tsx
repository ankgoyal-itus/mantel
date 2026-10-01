import type { Day } from '../../api/types'
import Avatar from '../../components/Avatar'
import Icon from '../../components/icons/Icon'
import { copy } from '../../copy'
import { isOut, mealName } from '../../out'
import { timeRange } from '../../format'
import { kidVars } from '../../kidVars'
import { classifyAgenda } from './agenda'
import { cleanTitle, splitOwner } from './titles'

/** "Thu 24", the head of a row. */
function dayHead(date: string): string {
  const [year, month, day] = date.split('-').map(Number)
  const when = new Date(year, month - 1, day)
  return `${when.toLocaleDateString('en-US', { weekday: 'short' })} ${when.getDate()}`
}

/**
 * The next three days, one line each, in the room the band has over.
 *
 * Only drawn when there is that room — upright, or on a day the children's
 * cards are short — so it never takes a row from them; otherwise the space
 * is simply the end of the screen. Each line is the day, what each child has
 * on (their face, then the thing), what the family has on, and dinner. It is
 * a glance, so it clamps rather than wraps: the list screen has the rest.
 */
export default function ComingUp({ days, compact = false }: { days: Day[]; compact?: boolean }) {
  return (
    // Compact: two days, no title row, 24px lines — what fits in 60 to 160px
    // once the meal rows have given 18 back.
    <section className={compact ? 'cu-card cu-card-compact' : 'cu-card'} aria-label={copy.day.comingUp}>
      {compact ? null : (
        <h3 className="dp-head">
          <span className="dp-label">{copy.day.comingUp}</span>
        </h3>
      )}
      <ul className="cu-rows">
        {days.map((day) => {
          const items = [
            ...day.kids.flatMap((kid) =>
              classifyAgenda(kid.agenda, 0).map(({ entry }) => ({
                key: `${kid.id}-${entry.title}-${entry.start ?? 'all'}`,
                kid,
                title: cleanTitle(entry.title, entry.where).title,
                start: entry.start,
              })),
            ),
            ...classifyAgenda(day.family_agenda, 0).map(({ entry }) => ({
              key: `family-${entry.title}-${entry.start ?? 'all'}`,
              kid: null,
              title: splitOwner(entry.title).title,
              start: entry.start,
            })),
          ].sort((a, b) => (a.start ?? '').localeCompare(b.start ?? ''))
          const dinner = day.meals.dinner
          return (
            <li key={day.date} className="cu-row">
              <span className="cu-day">{dayHead(day.date)}</span>
              <span className="cu-events clamp-1">
                {items.length === 0 ? (
                  <span className="cu-nothing">{copy.day.nothingOn}</span>
                ) : (
                  items.map((item) => (
                    <span
                      key={item.key}
                      className="cu-item"
                      style={item.kid ? kidVars(item.kid.id, item.kid.color) : undefined}
                    >
                      {item.kid ? (
                        <Avatar name={item.kid.name} avatar={item.kid.avatar} size={24} />
                      ) : null}
                      {item.start ? (
                        <span className="cu-time">{timeRange(item.start, null)}</span>
                      ) : null}
                      {item.title}
                    </span>
                  ))
                )}
              </span>
              {dinner ? (
                <span className="cu-dinner clamp-1">
                  <Icon
                    name={isOut(dinner.id) ? 'storefront' : 'meal'}
                    size={24}
                    className={isOut(dinner.id) ? 'cu-glyph meal-out-glyph' : 'cu-glyph'}
                  />
                  {mealName(dinner)}
                </span>
              ) : null}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
