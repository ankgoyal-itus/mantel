import { useEffect, useId, useState } from 'react'

import { recentPlaces } from '../api/points'
import { copy } from '../copy'

/**
 * Where, for a meal eaten out: the places used lately as chips, and one
 * optional line to type a new one. The same on the parent's sheet and in the
 * kid's picker. Forty characters at most, which the API also holds to.
 */
export default function PlaceField({
  value,
  onChange,
  onPick,
}: {
  value: string
  onChange: (place: string) => void
  /** Given, a chip is the whole answer and saves at once — the parent's
      sheet, where a place used before is three taps from the grid. */
  onPick?: (place: string) => void
}) {
  const id = useId()
  const [recent, setRecent] = useState<string[]>([])

  useEffect(() => {
    let cancelled = false
    recentPlaces()
      .then((found) => !cancelled && setRecent(found))
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="place-field">
      {recent.length > 0 ? (
        <div className="place-chips">
          {recent.map((place) => (
            <button
              key={place}
              type="button"
              className={place === value ? 'place-chip place-chip-on' : 'place-chip'}
              onClick={() => (onPick ? onPick(place) : onChange(place === value ? '' : place))}
            >
              {place}
            </button>
          ))}
        </div>
      ) : null}
      <label className="place-label" htmlFor={id}>
        {copy.out.where}
      </label>
      <input
        id={id}
        className="place-input"
        type="text"
        maxLength={40}
        autoComplete="off"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  )
}
