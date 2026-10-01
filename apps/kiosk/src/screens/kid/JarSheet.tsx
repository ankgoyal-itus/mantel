import { useState } from 'react'

import { putInTheJar } from '../../api/points'
import type { PointsSummary } from '../../api/types'
import { copy } from '../../copy'

/** What a child can spare without being asked to do arithmetic. */
const AMOUNTS = [5, 10, 25]

/**
 * Moving points from one child to the family.
 *
 * Two ledger rows that sum to zero, so the jar can always say whose points
 * are in it. Nothing is created here and nothing disappears.
 */
export default function JarSheet({
  kidId,
  points,
  jar,
  onDone,
  onChanged,
}: {
  kidId: string
  points: PointsSummary | null
  jar: PointsSummary | null
  onDone: () => void
  onChanged: () => void
}) {
  const [amount, setAmount] = useState(AMOUNTS[0])
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')
  const have = points ? points.balance : 0

  const give = () => {
    setBusy(true)
    putInTheJar(kidId, amount)
      .then(() => {
        setNote(copy.shop.jarDone(amount))
        onChanged()
      })
      .catch(() => setNote(copy.shop.notYet))
      .finally(() => setBusy(false))
  }

  return (
    <div className="confirm">
      <div className="confirm-card">
        <p className="confirm-question">{copy.shop.jarTitle}</p>
        <p className="shop-note">{copy.shop.jarWhat}</p>
        <p className="shop-note">{copy.shop.jarHas(jar ? jar.balance : 0)}</p>

        <div className="choices choices-centre">
          {AMOUNTS.map((value) => (
            <button
              key={value}
              type="button"
              className={value === amount ? 'choice choice-on' : 'choice'}
              disabled={value > have}
              onClick={() => setAmount(value)}
            >
              {value}
            </button>
          ))}
        </div>

        {note ? <p className="shop-note">{note}</p> : null}

        <div className="confirm-actions">
          <button
            type="button"
            className="decide decide-yes"
            disabled={busy || amount > have}
            onClick={give}
          >
            {copy.shop.jarGive(amount)}
          </button>
          <button type="button" className="decide" onClick={onDone}>
            {copy.kid.done}
          </button>
        </div>
      </div>
    </div>
  )
}
