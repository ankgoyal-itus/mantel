import { useCallback, useEffect, useState } from 'react'

import {
  answerTreat,
  approveClaim,
  approveRedemption,
  decidePick,
  setMeal,
  declineBankRequest,
  declineClaim,
  declineRedemption,
  finishTodo,
  getApprovals,
  getTodos,
} from '../../api/parent'
import { useLiveNonce } from '../../api/live'
import type { ApprovalItem, Kid, MealSlotName, Todo } from '../../api/types'
import Avatar from '../../components/Avatar'
import Icon from '../../components/icons/Icon'
import Illustration from '../../components/illustrations/Illustration'
import { copy } from '../../copy'
import { usePressGuard } from '../../usePressGuard'
import { kidVars } from '../../kidVars'
import { dollars } from '../kid/bank'
import AwardSheet from './AwardSheet'
import { Card, Pane, Toast } from './ui'
import { groupApprovals, whenSaid } from './approvals'

/** The fade a decided row leaves on. Matches pp-leave in parent.css. */
const LEAVE_MS = 200

/** How long a decided meal card says what was decided before it goes. */
const OUTCOME_MS = 10000

const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

function weekdayOf(date: string | null | undefined): string {
  if (!date) {
    return ''
  }
  const [year, month, day] = date.split('-').map(Number)
  return WEEKDAYS[new Date(year, month - 1, day).getDay()]
}

const key = (item: ApprovalItem) =>
  item.kind === 'meal' ? `meal-${item.date}-${item.slot}` : `${item.kind}-${item.id}`

/** rewards.yaml's family reward that "Plan it" goes with. */
const DINNER_OUT_REWARD = 'dinner_out'

/**
 * Everything waiting on a parent, in one list.
 *
 * Grouped by child, with their face as the head of the group, because that
 * is how a parent thinks about it — "what does she want" — and newest
 * first inside each. Meals the children picked come first of all: they have
 * a date on them, and the date is usually tomorrow. A dinner two children
 * chose differently is "Parents decide", answered with the dish rather than
 * with a yes.
 */
export default function ApprovalsSection({
  kids,
  onCount,
  onPointsChanged,
  onPlanOut,
}: {
  kids: Kid[]
  /** How many still wait, for the rail's badge. */
  onCount?: (count: number) => void
  /** A balance moved, so the wall should bounce. */
  onPointsChanged?: () => void
  /** "Plan it" on the family's Dinner out reward: to the Meals grid. */
  onPlanOut?: () => void
}) {
  const [queue, setQueue] = useState<ApprovalItem[] | null>(null)
  const [todos, setTodos] = useState<Todo[]>([])
  const [leaving, setLeaving] = useState<Set<string>>(new Set())
  const [busy, setBusy] = useState('')
  const [note, setNote] = useState({ text: '', bad: false })
  const [awarding, setAwarding] = useState(false)
  // One press per decision: a second Approve, Decline or Paid on the same
  // item inside 400ms is the same tap.
  const guard = usePressGuard()
  const pressed = (id: string) => (guard.pressed === id ? 'yes' : undefined)
  // A decided meal card keeps its place and says what was decided, for a
  // moment, before it leaves: the answer is worth reading back.
  const [outcomes, setOutcomes] = useState<Record<string, string>>({})

  const load = useCallback(() => {
    getApprovals()
      .then((found) => {
        setQueue(found)
        onCount?.(found.length)
      })
      .catch(() => setQueue([]))
    getTodos()
      .then(setTodos)
      .catch(() => setTodos([]))
  }, [onCount])

  // Another parent's approval, on another phone, lands here too.
  const live = useLiveNonce()
  useEffect(load, [load, live])

  const nameOf = (id: string) => kids.find((kid) => kid.id === id)?.name ?? id

  /** Fade the row, then take it out and ask the API what is left. */
  const settled = (item: ApprovalItem, said: string, points: boolean) => {
    setLeaving((current) => new Set(current).add(key(item)))
    setNote({ text: said, bad: false })
    if (points) {
      onPointsChanged?.()
    }
    window.setTimeout(() => {
      setQueue((current) => {
        const next = (current ?? []).filter((one) => key(one) !== key(item))
        onCount?.(next.length)
        return next
      })
      load()
    }, LEAVE_MS)
  }

  const run = (item: ApprovalItem, call: Promise<string>, points: boolean) => {
    setBusy(key(item))
    call
      .then((said) => settled(item, said, points))
      .catch(() => setNote({ text: copy.parent.approvals.failed, bad: true }))
      .finally(() => setBusy(''))
  }

  const decide = (item: ApprovalItem, approve: boolean) => {
    const who = nameOf(item.kid_id)
    if (item.kind === 'claim') {
      run(
        item,
        (approve ? approveClaim(item.id) : declineClaim(item.id)).then((summary) =>
          approve
            ? copy.parent.approvals.approvedClaim(item.title, who, summary.balance)
            : copy.parent.approvals.declined(item.title),
        ),
        approve,
      )
    } else if (item.kind === 'redemption') {
      run(
        item,
        (approve ? approveRedemption(item.id) : declineRedemption(item.id)).then(() =>
          approve
            ? copy.parent.approvals.approvedReward(item.title, who)
            : copy.parent.approvals.refunded(item.title, who),
        ),
        !approve,
      )
    }
  }

  /** A contested meal: one child's dish, or alternate — the first to pick
      keeps the day and the other's dish goes to the next day it can be. */
  const settleMeal = (item: ApprovalItem, winnerKidId: string, mode: 'choose' | 'alternate') => {
    if (!item.date || !item.slot) {
      return
    }
    const dishOf = (kidId: string | null) =>
      (item.choices ?? []).find((choice) => kidId !== null && choice.kids.includes(kidId))?.name ??
      ''
    setBusy(key(item))
    decidePick(item.date, item.slot as MealSlotName, winnerKidId, mode)
      .then((result) => {
        const said =
          mode === 'alternate' && result.loser_kid_id
            ? copy.parent.approvals.outcomeAlternate(
                nameOf(result.winner_kid_id),
                weekdayOf(result.winner_date),
                nameOf(result.loser_kid_id),
                result.loser_date ? weekdayOf(result.loser_date) : copy.parent.approvals.noDay,
              )
            : copy.parent.approvals.outcomeChose(
                nameOf(result.winner_kid_id),
                dishOf(result.winner_kid_id),
                weekdayOf(result.winner_date),
              )
        setOutcomes((current) => ({ ...current, [key(item)]: said }))
        window.setTimeout(() => {
          setOutcomes((current) => {
            const rest = { ...current }
            delete rest[key(item)]
            return rest
          })
          settled(item, said, false)
        }, OUTCOME_MS)
      })
      .catch(() => setNote({ text: copy.parent.approvals.failed, bad: true }))
      .finally(() => setBusy(''))
  }

  /** Back to the plan: both picks give way. */
  const backToPlan = (item: ApprovalItem) => {
    if (!item.date || !item.slot) {
      return
    }
    run(
      item,
      setMeal(item.date, item.slot as MealSlotName, null).then(() => copy.parent.approvals.mealPlan),
      false,
    )
  }

  const answer = (item: ApprovalItem, approve: boolean) => {
    if (item.pick_id == null) {
      return
    }
    run(
      item,
      answerTreat(item.pick_id, approve).then(() =>
        approve ? copy.parent.approvals.mealYes(item.title) : copy.parent.approvals.declined(item.title),
      ),
      false,
    )
  }

  const finish = (todo: Todo) => {
    setBusy(todo.ref)
    finishTodo(todo.ref)
      .then((left) => {
        setTodos(left)
        // Money or time out of a bank: say what was handed over, and let the
        // wall's caption catch up.
        const who = nameOf(todo.kid_id)
        if (todo.kind === 'cashout' && todo.cents) {
          setNote({ text: copy.parent.approvals.paidSaid(who, dollars(todo.cents)), bad: false })
          onPointsChanged?.()
        } else if (todo.kind === 'roblox' && todo.minutes) {
          setNote({ text: copy.parent.approvals.gaveSaid(who, todo.minutes), bad: false })
          onPointsChanged?.()
        }
      })
      .catch(() => setNote({ text: copy.parent.approvals.failed, bad: true }))
      .finally(() => setBusy(''))
  }

  /** Not this time, on a cash-out or a Roblox use: the hold ends and nothing
      leaves the bank. */
  const declineBank = (todo: Todo) => {
    if (todo.request_id == null) {
      return
    }
    setBusy(todo.ref)
    declineBankRequest(todo.request_id)
      .then((left) => {
        setTodos(left)
        setNote({ text: copy.parent.approvals.bankDeclined(nameOf(todo.kid_id)), bad: false })
      })
      .catch(() => setNote({ text: copy.parent.approvals.failed, bad: true }))
      .finally(() => setBusy(''))
  }

  const groups = groupApprovals(queue ?? [], kids)

  return (
    <Pane
      title={copy.parent.sections.approvals.title}
      description={copy.parent.sections.approvals.description}
      action={
        <button type="button" className="pp-button" onClick={() => setAwarding(true)}>
          <Icon name="star" size={20} />
          {copy.parent.approvals.award}
        </button>
      }
    >
      {queue === null ? (
        <Card>
          <p className="pp-muted">{copy.parent.loading}</p>
        </Card>
      ) : queue.length === 0 ? (
        <Card className="pp-empty">
          <Illustration name="kite" size={56} />
          <p className="pp-empty-text">{copy.parent.approvals.nothing}</p>
        </Card>
      ) : (
        groups.map((group) => {
          const kid = kids.find((one) => one.id === group.kidId)
          return (
            <Card key={group.key} className="pp-group">
              <h2 className="pp-group-head" style={kid ? kidVars(kid.id, kid.color) : undefined}>
                {kid ? (
                  <Avatar name={kid.name} avatar={kid.avatar} size={24} />
                ) : (
                  <Icon name="meal" size={28} className="pp-group-glyph" />
                )}
                <span>{kid ? kid.name : copy.parent.approvals.meals}</span>
              </h2>
              <ul className="pp-items">
                {group.items.map((item) => (
                  <li
                    key={key(item)}
                    className={leaving.has(key(item)) ? 'pp-item pp-item-leaving' : 'pp-item'}
                  >
                    {item.kind === 'meal' ? (
                      <MealItem
                        item={item}
                        kids={kids}
                        busy={busy === key(item)}
                        outcome={outcomes[key(item)] ?? null}
                        onDecide={(winner, mode) => settleMeal(item, winner, mode)}
                        onPlan={() => backToPlan(item)}
                      />
                    ) : item.kind === 'treat' ? (
                      <>
                        <div className="pp-item-text">
                          <span className="pp-item-what clamp-1">
                            {item.title === copy.out.dinner
                              ? copy.out.asks(nameOf(item.kid_id), item.note)
                              : item.title}
                          </span>
                          <span className="pp-item-when">
                            {copy.parent.approvals.slotOn(item.date ?? '', item.slot ?? 'dinner')}
                          </span>
                        </div>
                        <div className="pp-item-actions">
                          <button
                            type="button"
                            className="pp-button pp-button-accent"
                            disabled={busy === key(item)}
                            data-pressed={pressed(`${key(item)}:yes`)}
                            onClick={() =>
                              guard.press(`${key(item)}:yes`, () => answer(item, true), key(item))
                            }
                          >
                            {copy.parent.approvals.approve}
                          </button>
                          <button
                            type="button"
                            className="pp-text-button"
                            disabled={busy === key(item)}
                            data-pressed={pressed(`${key(item)}:no`)}
                            onClick={() =>
                              guard.press(`${key(item)}:no`, () => answer(item, false), key(item))
                            }
                          >
                            {copy.parent.approvals.decline}
                          </button>
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="pp-item-text">
                          <span className="pp-item-what clamp-1">
                            {item.kind === 'redemption'
                              ? copy.parent.approvals.reward(item.title, item.points)
                              : copy.parent.approvals.chore(item.title, item.points)}
                          </span>
                          <span className="pp-item-when">{whenSaid(item.when)}</span>
                        </div>
                        <div className="pp-item-actions">
                          <button
                            type="button"
                            className="pp-button pp-button-accent"
                            disabled={busy === key(item)}
                            data-pressed={pressed(`${key(item)}:yes`)}
                            onClick={() =>
                              guard.press(`${key(item)}:yes`, () => decide(item, true), key(item))
                            }
                          >
                            {copy.parent.approvals.approve}
                          </button>
                          <button
                            type="button"
                            className="pp-text-button"
                            disabled={busy === key(item)}
                            data-pressed={pressed(`${key(item)}:no`)}
                            onClick={() =>
                              guard.press(`${key(item)}:no`, () => decide(item, false), key(item))
                            }
                          >
                            {copy.parent.approvals.decline}
                          </button>
                        </div>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
          )
        })
      )}

      {todos.length > 0 ? (
        <>
          <h2 className="pp-subhead">{copy.parent.approvals.todoTitle}</h2>
          {todos.map((todo) => (
            <Card key={todo.ref} className="pp-todo">
              <div className="pp-item">
                <div className="pp-item-text">
                  <span className="pp-item-what clamp-1">
                    {todo.kind === 'allowance' && todo.day && todo.days
                      ? copy.parent.approvals.allowance(todo.day, todo.days, nameOf(todo.kid_id))
                      : todo.kind === 'cashout' && todo.cents
                        ? copy.parent.approvals.payCash(nameOf(todo.kid_id), dollars(todo.cents))
                        : todo.kind === 'roblox' && todo.minutes
                          ? copy.parent.approvals.giveRoblox(nameOf(todo.kid_id), todo.minutes)
                          : copy.parent.approvals.todo(todo.title, nameOf(todo.kid_id))}
                  </span>
                  {todo.due ? (
                    <span className="pp-item-when">{copy.parent.approvals.due(todo.due)}</span>
                  ) : null}
                </div>
                <div className="pp-item-actions">
                  {/* The family's Dinner out: say yes, then pick the night. */}
                  {todo.reward_id === DINNER_OUT_REWARD && onPlanOut ? (
                    <button type="button" className="pp-button" onClick={onPlanOut}>
                      {copy.out.planIt}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="pp-button pp-button-accent"
                    disabled={busy === todo.ref}
                    data-pressed={pressed(todo.ref)}
                    onClick={() => guard.press(todo.ref, () => finish(todo), todo.ref)}
                  >
                    {todo.kind === 'allowance' || todo.kind === 'cashout'
                      ? copy.parent.approvals.paid
                      : copy.parent.done}
                  </button>
                  {/* A child asked to take it out; a parent may say not now.
                      One group with Paid or Done: a bounced tap is one answer. */}
                  {todo.kind === 'cashout' || todo.kind === 'roblox' ? (
                    <button
                      type="button"
                      className="pp-button"
                      disabled={busy === todo.ref}
                      data-pressed={pressed(`${todo.ref}:no`)}
                      onClick={() => guard.press(`${todo.ref}:no`, () => declineBank(todo), todo.ref)}
                    >
                      {copy.parent.approvals.decline}
                    </button>
                  ) : null}
                </div>
              </div>
            </Card>
          ))}
        </>
      ) : null}

      <Toast text={note.text} bad={note.bad} />

      {awarding ? (
        <AwardSheet
          kids={kids}
          onClose={() => setAwarding(false)}
          onAwarded={(said) => {
            setNote({ text: said, bad: false })
            onPointsChanged?.()
          }}
        />
      ) : null}
    </Pane>
  )
}

/**
 * "Parents decide": one meal two children want different things for.
 *
 * The meal, each dish with the faces of whoever chose it, and three answers:
 * one child's, the other's, or Alternate — the child who picked first keeps
 * the day and the other's dish goes to the next day it can be. Once decided
 * the card says what happened, for a moment, and goes.
 */
function MealItem({
  item,
  kids,
  busy,
  outcome,
  onDecide,
  onPlan,
}: {
  item: ApprovalItem
  kids: Kid[]
  busy: boolean
  outcome: string | null
  onDecide: (winnerKidId: string, mode: 'choose' | 'alternate') => void
  onPlan: () => void
}) {
  const choices = item.choices ?? []
  const face = (id: string) => {
    const kid = kids.find((one) => one.id === id)
    return kid ? (
      <span key={id} className="pp-chip-face" style={kidVars(kid.id, kid.color)}>
        <Avatar name={kid.name} avatar={kid.avatar} size={24} />
      </span>
    ) : null
  }
  const nameOf = (id: string) => kids.find((kid) => kid.id === id)?.name ?? id
  const first = choices[0]?.kids[0] ?? null

  if (outcome) {
    return (
      <div className="pp-decide pp-decided" role="status">
        <span className="pp-item-what pp-decide-title">{item.title}</span>
        <span className="pp-item-what">{outcome}</span>
      </div>
    )
  }

  return (
    <div className="pp-decide">
      <div className="pp-item-text">
        <span className="pp-item-what pp-decide-title">{item.title}</span>
        <span className="pp-item-when">{copy.parent.approvals.parentsDecide}</span>
      </div>
      <ul className="pp-decide-dishes">
        {choices.map((choice) => (
          <li key={choice.id} className="pp-decide-dish">
            <span className="pp-faces-inline">{choice.kids.map(face)}</span>
            <span className="clamp-1">{choice.name}</span>
          </li>
        ))}
      </ul>
      <div className="pp-decide-choices">
        {choices.map((choice) =>
          choice.kids[0] ? (
            <button
              key={choice.id}
              type="button"
              className="pp-button pp-button-accent"
              disabled={busy}
              onClick={() => onDecide(choice.kids[0], 'choose')}
            >
              {copy.parent.approvals.kidsPick(nameOf(choice.kids[0]))}
            </button>
          ) : null,
        )}
        {first ? (
          <button
            type="button"
            className="pp-button"
            disabled={busy}
            onClick={() => onDecide(first, 'alternate')}
          >
            {copy.parent.approvals.alternate}
          </button>
        ) : null}
        {item.plan_name ? (
          <button type="button" className="pp-text-button" disabled={busy} onClick={onPlan}>
            {copy.parent.approvals.usePlan(item.plan_name)}
          </button>
        ) : null}
      </div>
    </div>
  )
}
