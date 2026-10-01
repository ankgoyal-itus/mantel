import { type RefObject, useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

import { claimTask, undoClaim, verifyKidPin } from '../../api/points'
import type { ClaimStatus, KidDay, PointsSummary, TaskEntry } from '../../api/types'
import Avatar from '../../components/Avatar'
import Icon from '../../components/icons/Icon'
import Keypad, { type KeypadResult } from '../../components/Keypad'
import { copy } from '../../copy'
import { kidVars } from '../../kidVars'
import '../../styles/kid.css'
import { kidCardHeight, kidChipWidth } from '../day/budget'
import KidColumn from '../day/KidColumn'
import type { CardArea } from '../../shell/tap'
import JarSheet from './JarSheet'
import ThisWeek from './ThisWeek'
import MealPicker from './MealPicker'
import RewardShop from './RewardShop'

/** The card growing from its DAY position into KID mode. */
const GROW_MS = 260

/** How long a claim can be taken back by tapping the chip again. */
export const UNDO_MS = 5000

/** The claim just made: which chip, when, and — once the API has answered —
    the claim to take back. */
type Recent = { taskId: string; claimId: number | null; at: number }

/**
 * One kid's own screen.
 *
 * Their card takes two thirds of the width and their colour banners it; the
 * other child shrinks to a rail rather than disappearing, because the
 * dashboard is shared and a card that vanishes reads as a card that was
 * taken away.
 */
export default function KidScreen({
  kid,
  other,
  now,
  points,
  locked,
  onUnlock,
  height,
  width = 1024,
  onDone,
  onChanged,
  startOn = 'none',
  from,
  pulse = null,
  onSwitch,
}: {
  kid: KidDay
  other: KidDay | null
  now: number
  points: Record<string, PointsSummary>
  /** Their code is set and has not been given in the last two minutes of
      their using the screen: the pad first. */
  locked: boolean
  /** The code was right. The shell holds it for two minutes. */
  onUnlock: () => void
  /** The stage's height, which the open card is planned against. */
  height: number
  /** The stage's width, which the chips wrap in. */
  width?: number
  onDone: () => void
  /** Tells the shell a balance or a claim moved, so it refetches. */
  onChanged: () => void
  /** Opened from the dots on the wall: straight to the week of meals. */
  startOn?: 'none' | 'meal'
  /** Where the two cards were on DAY, so this one can grow from there.
      Read once, as the card opens. */
  from?: RefObject<CardArea[]>
  /** The chip tapped on the wall, to pulse once as the card opens. */
  pulse?: string | null
  /** The other kid's rail card, tapped: their screen instead, the cards
      trading places from where they are now. */
  onSwitch?: (kidId: string, areas: CardArea[]) => void
}) {
  const unlocked = !locked
  const rootRef = useRef<HTMLDivElement | null>(null)
  const otherId = other ? other.id : null

  // The tapped card grows from where it was on DAY into the wide layout, and
  // the other card slides to its rail: 260ms of transform and opacity, run
  // once as the card opens (or unlocks), never a relayout.
  useLayoutEffect(() => {
    const root = rootRef.current
    const areas = from?.current ?? []
    if (!unlocked || !root || areas.length === 0) {
      return
    }
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      return
    }
    const grow = (selector: string, kidId: string | null) => {
      const card = root.querySelector<HTMLElement>(selector)
      const was = areas.find((area) => area.kid === kidId)
      if (!card || !was || typeof card.animate !== 'function') {
        return
      }
      const now = card.getBoundingClientRect()
      if (now.width === 0 || now.height === 0) {
        return
      }
      const moved = [
        `translate(${was.left - now.left}px, ${was.top - now.top}px)`,
        `scale(${(was.right - was.left) / now.width}, ${(was.bottom - was.top) / now.height})`,
      ].join(' ')
      const animation = card.animate(
        [
          { transformOrigin: '0 0', transform: moved, opacity: 0.6 },
          { transformOrigin: '0 0', transform: 'none', opacity: 1 },
        ],
        { duration: GROW_MS, easing: 'ease-out' },
      )
      animation.id = 'kid-grow'
    }
    grow('.kid-mode-main .kid', kid.id)
    grow('.kid-mode-rail .kid', otherId)
  }, [unlocked, from, kid.id, otherId])
  // What this screen has changed since the last poll. The API is the truth;
  // this is so a tap lands on the screen now rather than in five minutes.
  const [changed, setChanged] = useState<Record<string, ClaimStatus>>({})
  const [recent, setRecent] = useState<Recent | null>(null)
  const [sheet, setSheet] = useState<'none' | 'shop' | 'jar' | 'meal'>(startOn)

  // The five seconds a claim can be taken back in end on their own, and the
  // chip's "Tap again to undo" settles to "Waiting · +2".
  useEffect(() => {
    if (recent === null) {
      return
    }
    const timer = window.setTimeout(
      () => setRecent((current) => (current === recent ? null : current)),
      Math.max(0, recent.at + UNDO_MS - Date.now()),
    )
    return () => window.clearTimeout(timer)
  }, [recent])

  const claim = useCallback(
    (task: TaskEntry) => {
      const held = recent
      const undoable =
        held !== null && held.taskId === task.id && Date.now() - held.at < UNDO_MS

      if (undoable) {
        // Before the API has answered there is nothing to take back yet;
        // the tap is ignored rather than guessed at.
        if (held.claimId === null) {
          return
        }
        setChanged((current) => ({ ...current, [task.id]: 'none' }))
        setRecent(null)
        void undoClaim(held.claimId)
          .then(onChanged)
          .catch(() => setChanged((current) => ({ ...current, [task.id]: 'claimed' })))
        return
      }
      if (task.status === 'claimed' || changed[task.id] === 'claimed') {
        return // claimed, and past the moment for changing your mind
      }

      setChanged((current) => ({ ...current, [task.id]: 'claimed' }))
      const mine: Recent = { taskId: task.id, claimId: null, at: Date.now() }
      setRecent(mine)
      void claimTask(kid.id, task.id)
        .then((made) => {
          setRecent((current) =>
            current !== null && current.taskId === task.id ? { ...current, claimId: made.id } : current,
          )
          onChanged()
        })
        .catch(() => {
          setRecent(null)
          setChanged((current) => ({ ...current, [task.id]: 'none' }))
        })
    },
    [changed, kid.id, onChanged, recent],
  )

  const verify = useCallback(
    async (code: string): Promise<KeypadResult> => {
      const result = await verifyKidPin(kid.id, code)
      return result.ok ? { ok: true } : { ok: false, message: copy.keypad.tryAgain }
    },
    [kid.id],
  )

  // Where the two cards are now, so the switch can run from here.
  const switchTo = (otherKid: string) => {
    const root = rootRef.current
    const box = (selector: string) => root?.querySelector(selector)?.getBoundingClientRect()
    const main = box('.kid-mode-main .kid')
    const rail = box('.kid-mode-rail .kid')
    const areas: CardArea[] = []
    if (main && rail) {
      // The other kid's card grows from the rail; this one goes to it.
      areas.push({ kid: otherKid, left: rail.left, top: rail.top, right: rail.right, bottom: rail.bottom })
      areas.push({ kid: kid.id, left: main.left, top: main.top, right: main.right, bottom: main.bottom })
    }
    onSwitch?.(otherKid, areas)
  }

  if (!unlocked) {
    return (
      <div className="screen kid-mode" style={kidVars(kid.id, kid.color)}>
        <Keypad
          variant="kid"
          title={
            <>
              <Avatar name={kid.name} avatar={kid.avatar} size={24} />
              <span className="keypad-name">{kid.name}</span>
            </>
          }
          caption={copy.keypad.yourCode}
          submit={verify}
          onOpen={onUnlock}
          onCancel={onDone}
        />
      </div>
    )
  }

  const shown: KidDay = {
    ...kid,
    tasks: kid.tasks.map((task) =>
      changed[task.id] !== undefined ? { ...task, status: changed[task.id] } : task,
    ),
  }

  return (
    <div className="screen kid-mode" style={kidVars(kid.id, kid.color)} ref={rootRef}>
      <div className="kid-mode-band">
        <h1 className="kid-mode-name">{kid.name}</h1>
        <button type="button" className="kid-done" onClick={onDone}>
          {copy.kid.done}
        </button>
      </div>

      {/* The week of meals takes the whole screen: seven days across needs
          the other child's rail too, or no dish name fits a column. */}
      <div className={sheet === 'meal' ? 'kid-mode-body kid-mode-wide' : 'kid-mode-body'}>
        <div className="kid-mode-main">
          {sheet === 'meal' ? (
            <MealPicker
              kid={kid}
              other={other}
              onDone={() => setSheet('none')}
              onChanged={onChanged}
            />
          ) : sheet === 'shop' ? (
            <RewardShop
              kidId={kid.id}
              points={points[kid.id] ?? null}
              jar={points.family ?? null}
              tasks={kid.tasks}
              onDone={() => setSheet('none')}
              onChanged={onChanged}
            />
          ) : (
            <KidColumn
              kid={shown}
              now={now}
              avatarSize={56}
              points={points[kid.id] ?? null}
              claimable
              nodding
              pulse={pulse}
              undoing={recent?.taskId ?? null}
              budget={kidCardHeight(height)}
              chipWidth={kidChipWidth(width)}
              onClaim={claim}
              underBalance={
                // Their cash, on their own card and nowhere else: money on
                // the kitchen wall is a thing siblings compare.
                (points[kid.id]?.dollars_owed ?? 0) > 0 ? (
                  <span className="balance-under">
                    <span className="cash-saved">
                      {copy.kid.cashSaved(points[kid.id]?.dollars_owed ?? 0)}
                    </span>
                  </span>
                ) : null
              }
              belowTasks={
                <ThisWeek points={points[kid.id] ?? null} today={(new Date().getDay() + 6) % 7} />
              }
              footer={
                <div className="kid-actions">
                  <button type="button" className="kid-action" onClick={() => setSheet('shop')}>
                    <Icon name="coin" size={30} className="kid-action-glyph" />
                    {copy.kid.rewards}
                  </button>
                  <button type="button" className="kid-action" onClick={() => setSheet('meal')}>
                    <Icon name="meal" size={30} className="kid-action-glyph" />
                    {copy.kid.pickMeal}
                  </button>
                  {/* The jar is the rarest thing a child does here, so it is
                      the small one: the glyph and what is in it, opening the
                      sheet that says what it buys. */}
                  <button type="button" className="jar-button" onClick={() => setSheet('jar')}>
                    <Icon name="jar" size={24} className="kid-action-glyph" />
                    {copy.day.familyJar(points.family?.balance ?? 0)}
                  </button>
                </div>
              }
            />
          )}
        </div>
        {other ? (
          <div className="kid-mode-rail">
            <KidColumn
              kid={other}
              now={now}
              avatarSize={24}
              showTasks={false}
              compact
              points={points[other.id] ?? null}
              onOpen={onSwitch ? () => switchTo(other.id) : undefined}
            />
          </div>
        ) : null}
      </div>

      {sheet === 'jar' ? (
        <JarSheet
          kidId={kid.id}
          points={points[kid.id] ?? null}
          jar={points.family ?? null}
          onDone={() => setSheet('none')}
          onChanged={onChanged}
        />
      ) : null}
    </div>
  )
}
