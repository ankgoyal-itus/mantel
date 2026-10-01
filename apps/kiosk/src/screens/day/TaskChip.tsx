import { useRef } from 'react'

import type { TaskEntry } from '../../api/types'
import Icon from '../../components/icons/Icon'
import { copy } from '../../copy'
import { usePressGuard } from '../../usePressGuard'
import { worthLabel } from './chips'

/**
 * How long a parent holds a waiting chip on the wall before it offers to be
 * decided. Long enough that the children, who press these all day, never
 * see the PIN pad by accident.
 */
const HOLD_MS = 800

/** A second tap on a chip inside this is the same tap, bounced. The undo
    window starts after it. */
export const CHIP_GUARD_MS = 250

export type ChipState = 'open' | 'claimed' | 'approved' | 'declined' | 'parent'

/** Which of the five shades a to-do is drawn in. */
export function chipState(task: TaskEntry): ChipState {
  if (task.status === 'claimed') {
    return 'claimed'
  }
  if (task.status === 'approved') {
    return 'approved'
  }
  if (task.status === 'declined') {
    return 'declined'
  }
  return task.claim === 'parent' ? 'parent' : 'open'
}

/**
 * One to-do as a chip: a 12px ring, the title, and what it is worth.
 *
 * Five shades. Open: the chip grey, a grey ring, "+5". Waiting on a parent:
 * the kid's tint and a 2px border in their colour, "Waiting · +2". Approved:
 * the good green, the ring a filled disc with a tick. Declined: no fill, the
 * title dimmed and the worth struck through. A parent's own job: open, with
 * the lock where the ring would be.
 *
 * A chip is a button everywhere. In kid mode a tap claims it, and a second
 * inside five seconds takes it back (KidScreen) — the worth says so for
 * those five seconds. On the wall a tap opens that kid's own card, where the
 * chip pulses once; a parent can still hold a waiting chip to decide it
 * there, and the release after a hold opens nothing.
 */
export default function TaskChip({
  task,
  claimable,
  long = false,
  onClaim,
  onOpen,
  onHold,
  deciding = false,
  onApprove,
  onDecline,
  pulse = false,
  undoing = false,
}: {
  task: TaskEntry
  /** Kid mode: a tap claims. */
  claimable: boolean
  /** Too wide for the card on one line: two lines of caption instead. */
  long?: boolean
  onClaim?: (task: TaskEntry) => void
  /** On the wall: a tap opens this kid's card at this chip. */
  onOpen?: (task: TaskEntry) => void
  /** A long press on the wall: the way in to deciding it there. */
  onHold?: (task: TaskEntry) => void
  deciding?: boolean
  onApprove?: (task: TaskEntry) => void
  onDecline?: (task: TaskEntry) => void
  /** The chip the kid tapped on the wall: one 300ms pulse of their tint. */
  pulse?: boolean
  /** Just claimed: "Tap again to undo" for five seconds. */
  undoing?: boolean
}) {
  const state = chipState(task)
  const held = useRef<number | null>(null)
  // The hold fired: the release that ends it is not a tap.
  const holdFired = useRef(false)
  const lastPress = useRef(0)
  const guarded = usePressGuard(400)
  const classes = ['chip-task', `chip-task-${state}`]
  if (long) {
    classes.push('chip-task-long')
  }
  if (pulse) {
    classes.push('chip-task-pulse')
  }
  if (undoing) {
    classes.push('chip-task-undoing')
  }

  const mark =
    state === 'parent' ? (
      <Icon name="lock" size={14} className="chip-task-lock" />
    ) : state === 'approved' ? (
      <span className="chip-task-ring chip-task-tick" aria-hidden="true">
        <Icon name="check" size={10} />
      </span>
    ) : (
      <span className="chip-task-ring" aria-hidden="true" />
    )

  const inner = (
    <>
      {mark}
      <span className="chip-task-title">{task.title}</span>
      {deciding ? null : <span className="chip-task-worth">{worthLabel(task, undoing)}</span>}
    </>
  )

  const holdable = !claimable && state === 'claimed' && task.claim_id !== null && !!onHold
  const stop = () => {
    if (held.current !== null) {
      window.clearTimeout(held.current)
      held.current = null
    }
  }
  const hold = holdable
    ? {
        onPointerDown: () => {
          stop()
          holdFired.current = false
          held.current = window.setTimeout(() => {
            held.current = null
            holdFired.current = true
            onHold?.(task)
          }, HOLD_MS)
        },
        onPointerUp: stop,
        onPointerLeave: stop,
        onPointerCancel: stop,
      }
    : {}

  if (deciding) {
    return (
      <li className={[...classes, 'chip-task-deciding'].join(' ')}>
        {inner}
        <span className="row-decide">
          <button
            type="button"
            className="row-no"
            data-pressed={guarded.pressed === 'no' ? 'yes' : undefined}
            onClick={() => guarded.press('no', () => onDecline?.(task), 'decide')}
          >
            {copy.day.decline}
          </button>
          <button
            type="button"
            className="row-yes"
            data-pressed={guarded.pressed === 'yes' ? 'yes' : undefined}
            onClick={() => guarded.press('yes', () => onApprove?.(task), 'decide')}
          >
            {copy.day.approve}
          </button>
        </span>
      </li>
    )
  }

  // The wall: every chip opens its kid's card.
  if (!claimable) {
    if (!onOpen) {
      return (
        <li className={classes.join(' ')} {...hold}>
          {inner}
        </li>
      )
    }
    return (
      <li className={classes.join(' ')} {...hold}>
        <button
          type="button"
          className="chip-task-tap"
          onClick={() => {
            if (holdFired.current) {
              holdFired.current = false
              return
            }
            onOpen(task)
          }}
        >
          {inner}
        </button>
      </li>
    )
  }

  // Kid mode: a chip that looks tappable and is not is worse than one that
  // plainly is not, so a parent's job and a done one are not buttons.
  if (state === 'parent' || state === 'approved') {
    return <li className={classes.join(' ')}>{inner}</li>
  }
  return (
    <li className={classes.join(' ')}>
      <button
        type="button"
        className="chip-task-tap"
        onClick={() => {
          const now = Date.now()
          if (now - lastPress.current < CHIP_GUARD_MS) {
            return
          }
          lastPress.current = now
          onClaim?.(task)
        }}
      >
        {inner}
      </button>
    </li>
  )
}
