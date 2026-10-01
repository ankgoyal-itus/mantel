import { copy } from '../copy'
import Icon from './icons/Icon'

/**
 * The way in to the parent screen, in the corner of DAY and NIGHT.
 *
 * Before this, the only ways in were a long press on the clock and a triple
 * tap in a corner — both of which a parent had to be told about, and neither
 * of which a visitor could be shown. The pill says the door is there; the PIN
 * still says who may open it.
 *
 * It is the only element on either screen that leads anywhere a kid should
 * not go, which is what keeps that rule easy to check.
 */
export default function ParentPill({
  pending = 0,
  session = false,
  onOpen,
  onDone,
}: {
  /** Approvals waiting, shown as a badge. */
  pending?: number
  /** True while the ten minutes a PIN bought are still running. */
  session?: boolean
  onOpen: () => void
  onDone: () => void
}) {
  if (session) {
    // Signed in, and saying so: a parent should never wonder whether the
    // screen is still theirs, and Done is how they hand it back.
    return (
      <div className="parents parents-on">
        <button type="button" className="parents-open" onClick={onOpen}>
          {copy.parent.modeOn}
        </button>
        <span className="parents-sep" aria-hidden="true">
          ·
        </span>
        <button type="button" className="parents-done" onClick={onDone}>
          {copy.parent.done}
        </button>
      </div>
    )
  }

  return (
    <button type="button" className="parents" onClick={onOpen}>
      <Icon name="lock" size={20} className="parents-glyph" />
      <span className="parents-word">{copy.parent.pill}</span>
      {pending > 0 ? <span className="parents-badge">{pending}</span> : null}
    </button>
  )
}
