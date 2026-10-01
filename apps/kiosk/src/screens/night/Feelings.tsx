import { useState } from 'react'

import { recordFeeling } from '../../api/points'
import type { Feeling } from '../../api/types'
import { copy } from '../../copy'

/** Worst last, so a child scanning left to right finds "fine" first. */
export const FACES: readonly Feeling[] = ['great', 'good', 'okay', 'meh', 'rough']

/** The mouth of each face, on the 24 grid the rest of the icons use. */
const MOUTHS: Record<Feeling, string> = {
  great: 'M8 14.5a4.5 4.5 0 0 0 8 0',
  good: 'M8.5 14.5a4 4 0 0 0 7 0',
  okay: 'M8.5 15h7',
  meh: 'M8.5 15.5c1.5-.8 5.5-.8 7 0',
  rough: 'M8 16a4.5 4.5 0 0 1 8 0',
}

function Face({ feeling }: { feeling: Feeling }) {
  return (
    <svg
      width="40"
      height="40"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="12" cy="12" r="9" />
      <path d="M9 10h.01M15 10h.01" />
      <path d={MOUTHS[feeling]} />
    </svg>
  )
}

/**
 * "How was today", once, at bedtime.
 *
 * Five faces and one tap, on the night screen and nowhere else. What a child
 * says goes to the weekly digest and to no screen anybody else will see.
 *
 * The absences are the design. There is no streak, because a child who misses
 * Tuesday has not failed at having feelings. There is no reminder, because a
 * screen that keeps asking until you answer is not asking. And a night nobody
 * answered leaves no gap: the row simply stays as it was.
 */
export default function Feelings({
  kidId,
  chosen,
  onChosen,
}: {
  kidId: string
  /** What was already tapped tonight, if anything. */
  chosen: Feeling | null
  onChosen: (kidId: string, feeling: Feeling) => void
}) {
  const [busy, setBusy] = useState(false)

  const choose = (feeling: Feeling) => {
    setBusy(true)
    // Said on the screen before the API answers: a child should not watch a
    // face wait for a network. Nothing is lost if the write fails — it is
    // one evening's mood, and it will be asked again tomorrow.
    onChosen(kidId, feeling)
    recordFeeling(kidId, feeling)
      .catch(() => undefined)
      .finally(() => setBusy(false))
  }

  return (
    <div className="feelings" data-night-live>
      <span className="feelings-title">{chosen ? copy.feelings.thanks : copy.feelings.title}</span>
      <span className="feelings-faces">
        {FACES.map((feeling) => (
          <button
            key={feeling}
            type="button"
            className={feeling === chosen ? 'feeling feeling-on' : 'feeling'}
            aria-label={copy.feelings.faces[feeling]}
            disabled={busy}
            onClick={() => choose(feeling)}
          >
            <Face feeling={feeling} />
          </button>
        ))}
      </span>
    </div>
  )
}
