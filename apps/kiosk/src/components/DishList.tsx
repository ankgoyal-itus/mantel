import { Fragment } from 'react'

import type { PickOption, Protein } from '../api/types'
import { copy } from '../copy'
import { groupByCuisine } from '../screens/kid/cuisines'
import Icon from './icons/Icon'

/**
 * The catalog for one slot, grouped by cuisine: the kid picker's list, and
 * the parent's.
 *
 * For a child a dish they cannot have says why and does not respond, because
 * the rules are the point of letting them choose at all. A parent may choose
 * anything; the same reasons stay on as warnings, so "not a meat day" is
 * read before the chicken is.
 */
export default function DishList({
  options,
  busy = false,
  parent = false,
  alsoName = '',
  onChoose,
}: {
  options: PickOption[]
  busy?: boolean
  /** Every dish tappable, the reasons shown as warnings. */
  parent?: boolean
  /** The header over another slot's dishes ("Also good for dinner"). */
  alsoName?: string
  onChoose: (option: PickOption, protein: Protein) => void
}) {
  return (
    <ul className={parent ? 'picker picker-parent' : 'picker'}>
      {groupByCuisine(options, alsoName).map((group) => (
        <Fragment key={group.key || 'plain'}>
          {group.name ? <li className="pick-group">{group.name}</li> : null}
          {group.items.map((option) => {
            const open = parent || option.pickable
            // Veg is the default and needs no button of its own: the row is
            // the tap. The other ways to cook it are chips, and the API has
            // already dropped the ones the day's diet rule forbids. A parent
            // settles the dish; how it is cooked stays with the plan.
            const ways = parent ? [] : option.proteins.filter((protein) => protein !== 'veg')
            // A reason it cannot be chosen, or — still choosable — a word
            // about it ("we had this Tuesday").
            const warning = !option.pickable && option.why ? option.why : null
            const aside = option.repeat_day
              ? copy.picker.hadThis(option.repeat_day)
              : (option.warning ?? null)
            return (
              <li key={option.id} className={open ? 'pick' : 'pick pick-out'}>
                {open ? (
                  <button
                    type="button"
                    className="pick-tap"
                    disabled={busy}
                    onClick={() => onChoose(option, 'veg')}
                  >
                    <span className="pick-name">{option.name}</span>
                    {option.treat ? <Icon name="star" size={20} className="pick-treat" /> : null}
                  </button>
                ) : (
                  <span className="pick-name">{option.name}</span>
                )}
                {open ? (
                  <span className="pick-ways">
                    {parent && warning ? <span className="pick-warn">{warning}</span> : null}
                    {aside ? <span className="pick-warn">{aside}</span> : null}
                    {ways.map((protein) => (
                      <button
                        key={protein}
                        type="button"
                        className="choice"
                        disabled={busy}
                        onClick={() => onChoose(option, protein)}
                      >
                        {copy.picker.plus(protein)}
                      </button>
                    ))}
                  </span>
                ) : warning ? (
                  <span className="pick-why">{warning}</span>
                ) : null}
              </li>
            )
          })}
        </Fragment>
      ))}
    </ul>
  )
}
