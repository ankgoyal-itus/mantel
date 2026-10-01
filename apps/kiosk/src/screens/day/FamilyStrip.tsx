import { useEffect, useRef, useState } from 'react'

import type { AgendaEntry } from '../../api/types'
import Icon from '../../components/icons/Icon'
import { copy } from '../../copy'
import { timeRange } from '../../format'
import { classifyAgenda } from './agenda'
import { MORE_PILL, pillsThatFit } from './strip'
import { splitOwner } from './titles'

/** The strip's gap between pills. Mirrors .fam-row in day.css. */
const GAP = 8

/**
 * What the whole house is doing today, as a row of pills.
 *
 * Each is the time, the thing, and — when the calendar wrote "[Dad]" on
 * the end of it — whose it is, as an initial on a chip rather than as
 * brackets in the title. A pill never shrinks. When the row runs out, the
 * last pill that would have fitted becomes "+N", which opens the list at
 * today; the family jar sits pinned at the far end, outside the row, so it
 * is never the thing that gets counted away.
 *
 * Which pills fit is measured, once, from the pills as first laid out: the
 * widths are kept, so drawing fewer of them cannot change the answer and
 * set it oscillating. The strip is keyed on its entries by the day screen,
 * which is what clears them when the day changes.
 */
export default function FamilyStrip({
  entries,
  jar = null,
  now,
  onMore,
  onPill,
}: {
  entries: AgendaEntry[]
  /** Points in the family jar, or null before the balance has landed. */
  jar?: number | null
  /** Minutes past midnight, for the order the pills go in. */
  now: number
  /** The "+N" pill: the rest of today, in the list. */
  onMore?: () => void
  /** Any other pill: today in the list, the family's rows only. */
  onPill?: () => void
}) {
  const rowRef = useRef<HTMLDivElement | null>(null)
  const widths = useRef<number[]>([])
  const [fit, setFit] = useState<number | null>(null)

  const pills = classifyAgenda(entries, now).map(({ entry }) => entry)

  useEffect(() => {
    const row = rowRef.current
    if (!row || pills.length === 0) {
      return
    }
    const observer = new ResizeObserver(() => {
      for (const pill of row.querySelectorAll<HTMLElement>('[data-pill]')) {
        widths.current[Number(pill.dataset.pill)] = pill.offsetWidth
      }
      setFit(pillsThatFit(widths.current, row.clientWidth, GAP))
    })
    observer.observe(row)
    return () => observer.disconnect()
  }, [pills.length])

  const shown = fit === null ? pills : pills.slice(0, fit)
  const hidden = pills.length - shown.length

  return (
    <div className="fam">
      {pills.length === 0 ? (
        <span className="fam-none clamp-1">
          <Icon name="house" size={18} className="fam-none-glyph" />
          {copy.day.familyNone}
        </span>
      ) : (
        <div className="fam-row" ref={rowRef}>
          {shown.map((entry, index) => {
            const { title, owner } = splitOwner(entry.title)
            return (
              // A button the strip's full 44px, the pill drawn inside it, the
              // way "+N" is.
              <button
                type="button"
                key={`${entry.title}-${entry.start ?? 'all'}-${index}`}
                className="fam-tap"
                data-pill={index}
                onClick={onPill}
              >
                <span className="fam-pill">
                  <span className="fam-when">
                    {entry.all_day ? copy.day.allDay : timeRange(entry.start, null)}
                  </span>
                  <span className="fam-what">{title}</span>
                  {owner ? (
                    <span className="fam-who" title={owner}>
                      {owner.slice(0, 1)}
                    </span>
                  ) : null}
                </span>
              </button>
            )
          })}
          {hidden > 0 ? (
            <button
              type="button"
              className="fam-more"
              style={{ width: MORE_PILL }}
              onClick={onMore}
            >
              <span className="fam-more-pill">{copy.day.morePills(hidden)}</span>
            </button>
          ) : null}
        </div>
      )}
      {/* An outline in the muted ink while the jar is empty; the festival's
          tint only once there is something in it. */}
      {jar !== null ? (
        <span className={jar > 0 ? 'fam-jar fam-jar-some' : 'fam-jar'}>
          {copy.day.familyJar(jar)}
        </span>
      ) : null}
    </div>
  )
}
