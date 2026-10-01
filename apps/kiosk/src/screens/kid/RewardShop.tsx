import { useEffect, useState } from 'react'

import { getJson } from '../../api/client'
import { askForReward, markSavingFor, myRewards } from '../../api/points'
import type { PointsSummary, Redemption, Reward, TaskEntry } from '../../api/types'
import Icon, { type IconName } from '../../components/icons/Icon'
import { copy } from '../../copy'

/** What each fulfilment kind is called once a parent has said yes. */
const STATE: Record<Redemption['status'], string> = {
  requested: copy.shop.asked,
  approved: copy.shop.approved,
  scheduled: copy.shop.approved,
  fulfilled: copy.shop.done,
  declined: copy.shop.declined,
  refunded: copy.shop.declined,
}

/** What a row says it came to. A cash reward says how much, and whether it
    is still coming or has been handed over. */
function stateOf(row: Redemption): string {
  const cash = row.fulfilment_ref?.match(/^cash:(\d+)$/)
  if (cash && row.status === 'approved') {
    return copy.shop.cashComing(Number(cash[1]))
  }
  if (cash && row.status === 'fulfilled') {
    return copy.shop.cashPaid(Number(cash[1]))
  }
  return STATE[row.status]
}

function glyphOf(name: string): IconName {
  const known: IconName[] = ['ice-cream', 'cake', 'cup', 'meal', 'dinner', 'coin', 'game', 'star']
  return known.includes(name as IconName) ? (name as IconName) : 'star'
}

function day(iso: string): string {
  const at = new Date(iso)
  return Number.isNaN(at.getTime())
    ? ''
    : at.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

/**
 * What points are for.
 *
 * Every reward is shown, including the ones a child cannot afford and the
 * ones that are not switched on: a reward you cannot see is a reward you
 * cannot save towards. What changes is how solid the card looks.
 */
export default function RewardShop({
  kidId,
  points,
  jar,
  tasks = [],
  onDone,
  onChanged,
}: {
  kidId: string
  points: PointsSummary | null
  jar: PointsSummary | null
  /** Today's list, so the nudge can name a real way to earn. */
  tasks?: readonly TaskEntry[]
  onDone: () => void
  onChanged: () => void
}) {
  const [rewards, setRewards] = useState<Reward[]>([])
  const [mine, setMine] = useState<Redemption[]>([])
  const [asking, setAsking] = useState<Reward | null>(null)
  /** The shop opens filtered; this is the way out to the rest of it. */
  const [showAll, setShowAll] = useState(false)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    void getJson<Reward[]>('/api/rewards').then(
      (loaded) => {
        if (!cancelled) {
          // A meal reward that is switched off is not "Coming soon": meal
          // picks are free now, so it is simply not a thing to save for.
          setRewards(loaded.filter((reward) => reward.enabled || reward.fulfilment !== 'meal'))
        }
      },
      () => undefined,
    )
    return () => {
      cancelled = true
    }
  }, [])

  const [refresh, setRefresh] = useState(0)
  useEffect(() => {
    let cancelled = false
    myRewards(kidId)
      .then((loaded) => {
        if (!cancelled) {
          setMine(loaded)
        }
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [kidId, refresh])

  const asked = new Set(
    mine.filter((row) => row.status === 'requested').map((row) => row.reward_id),
  )
  // What they are already saving for, from the summary the card draws bars
  // from, so the star and the bar can never disagree.
  const starred = new Set((points?.saving_for ?? []).map((pick) => pick.reward_id))

  const star = (rewardId: string) => {
    setBusy(true)
    markSavingFor(kidId, rewardId)
      .then(() => onChanged())
      .catch(() => setNote(copy.shop.notYet))
      .finally(() => setBusy(false))
  }

  const ask = (reward: Reward) => {
    setBusy(true)
    askForReward(kidId, reward.id)
      .then(() => {
        setNote(copy.shop.askedFor(reward.name))
        setAsking(null)
        setRefresh((count) => count + 1)
        onChanged()
      })
      .catch(() => setNote(copy.shop.notYet))
      .finally(() => setBusy(false))
  }

  const balanceFor = (reward: Reward) =>
    reward.family ? (jar ? jar.balance : 0) : points ? points.balance : 0

  // The shop opens on what this child can actually have today. Everything
  // else is one tap away, rather than nine tiles of things they cannot.
  const affordableNow = rewards.filter(
    (reward) => reward.enabled && balanceFor(reward) >= reward.cost,
  )
  // Nothing affordable is the state a child starts in, and it used to be the
  // worst screen in the app: nine tiles at 40% saying "N more", which reads
  // as nine things being refused at once. Three of them, in full colour, is
  // the same truth said as a shortlist — and the shortfall on a tile you can
  // see properly is a goal rather than a rejection.
  const nothingYet = affordableNow.length === 0
  const cheapest = [...rewards]
    .filter((reward) => reward.enabled)
    .sort((first, second) => first.cost - second.cost)
  const goals = new Set(nothingYet && !showAll ? cheapest.slice(0, 3).map((it) => it.id) : [])
  const shown = showAll || nothingYet ? rewards : affordableNow

  // The nudge names the cheapest thing to do and the cheapest thing to get,
  // both from this child's own screen, so the gap between them is arithmetic
  // a seven-year-old can do.
  const earner = [...tasks]
    .filter((task) => task.points > 0)
    .sort((first, second) => first.points - second.points)[0]
  const goal = cheapest[0]
  const nudge =
    nothingYet && !showAll && earner && goal
      ? copy.shop.nudge(earner.title, earner.points, goal.name, goal.cost)
      : ''

  return (
    <div className="shop">
      <div className="shop-bar">
        <h2 className="shop-title">{copy.shop.title}</h2>
        <button type="button" className="shop-toggle" onClick={() => setShowAll(!showAll)}>
          {showAll ? copy.shop.showAffordable : copy.shop.showAll}
        </button>
        <button type="button" className="kid-done" onClick={onDone}>
          {copy.shop.back}
        </button>
      </div>

      {nudge ? <p className="shop-nudge">{nudge}</p> : null}

      <div className="shop-grid">
        {shown.map((reward) => {
          const affordable = reward.enabled && balanceFor(reward) >= reward.cost
          const waiting = asked.has(reward.id)
          // Drawn in full, though it cannot be tapped yet: this is one of the
          // three a child is closest to, and it is being shown as the target.
          const isGoal = goals.has(reward.id)
          const classes = ['shop-card']
          if ((affordable || isGoal) && !waiting) {
            classes.push('shop-card-open')
          } else {
            classes.push('shop-card-dim')
          }
          if (isGoal && !affordable) {
            classes.push('shop-card-goal')
          }
          return (
            <div key={reward.id} className="shop-tile">
              {/* Starring is the one decision here that is entirely the
                  child's: it asks nobody, costs nothing, and can be undone
                  by tapping it again. So it is its own small target on the
                  corner of the tile rather than part of asking for it. */}
              {reward.enabled ? (
                <button
                  type="button"
                  className={starred.has(reward.id) ? 'shop-star shop-star-on' : 'shop-star'}
                  aria-label={starred.has(reward.id) ? copy.shop.saving : copy.shop.save}
                  disabled={busy}
                  onClick={() => star(reward.id)}
                >
                  <Icon name="star" size={22} />
                </button>
              ) : null}
            <button
              type="button"
              className={classes.join(' ')}
              disabled={!affordable || waiting || busy}
              onClick={() => setAsking(reward)}
            >
              <Icon
                name={glyphOf(reward.glyph)}
                size={(affordable || isGoal) && !waiting ? 48 : 32}
                className="shop-glyph"
              />
              <span className="shop-name">{reward.name}</span>
              <span className="shop-cost">{copy.kid.points(reward.cost)}</span>
              {!reward.enabled ? (
                // A lock says "not yet" faster than two words do, and leaves
                // the tile looking like the others rather than like an error.
                <Icon name="lock" size={20} className="shop-state-glyph" />
              ) : waiting ? (
                <span className="shop-state">{copy.shop.asked}</span>
              ) : !affordable ? (
                <span className={isGoal ? 'shop-state shop-state-goal' : 'shop-state'}>
                  {copy.shop.shortfall(reward.cost - balanceFor(reward))}
                </span>
              ) : reward.family ? (
                // A family reward is paid from the jar, so the jar is the
                // number that matters beside it.
                <span className="shop-state">{copy.shop.jarHas(jar ? jar.balance : 0)}</span>
              ) : null}
            </button>
            </div>
          )
        })}
      </div>

      <h3 className="shop-heading">{copy.shop.mine}</h3>
      {mine.length === 0 ? (
        <p className="empty">{copy.shop.noneYet}</p>
      ) : (
        <ul className="shop-mine">
          {mine.slice(0, 2).map((row) => (
            <li key={row.id} className="shop-mine-row">
              <Icon name={glyphOf(row.glyph)} size={22} className="shop-mine-glyph" />
              <span className="shop-mine-name">{row.name}</span>
              <span className="shop-mine-state">{stateOf(row)}</span>
              <span className="shop-mine-when">{day(row.requested_at)}</span>
            </li>
          ))}
        </ul>
      )}
      {note ? <p className="shop-note">{note}</p> : null}

      {asking ? (
        <div className="confirm">
          <div className="confirm-card">
            <p className="confirm-question">
              {copy.shop.confirm(asking.name, asking.cost)}
            </p>
            <div className="confirm-actions">
              <button
                type="button"
                className="decide decide-yes"
                disabled={busy}
                onClick={() => ask(asking)}
              >
                {copy.shop.yes}
              </button>
              <button type="button" className="decide" onClick={() => setAsking(null)}>
                {copy.shop.no}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
