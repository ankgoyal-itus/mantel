import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { shouldFire } from '../confetti'
import { copy } from '../copy'
import { getJson } from '../api/client'
import { useLive, useLiveNonce } from '../api/live'
import { approveClaim, declineClaim, sessionOpen, signOut } from '../api/parent'
import type { Feeling, PinState, TaskEntry } from '../api/types'
import { useAgenda } from '../api/useAgenda'
import { usePhotos } from '../api/usePhotos'
import { usePending, usePoints } from '../api/usePoints'
import { useMantelData } from '../api/useMantelData'
import DayScreen, { type ListRequest } from '../screens/DayScreen'
import FrameScreen from '../screens/FrameScreen'
import KidScreen from '../screens/kid/KidScreen'
import ListScreen from '../screens/ListScreen'
import MonthScreen from '../screens/MonthScreen'
import NightScreen from '../screens/NightScreen'
import ParentScreen from '../screens/parent/ParentScreen'
import PinPad from '../screens/parent/PinPad'
import StaleDot from './StaleDot'
import { useDailyReload, useReloadFlag, useVersionReload } from './useReload'
import type { Filter } from '../screens/list/rows'
import { minutesOfDay } from '../screens/day/agenda'
import { WAKE_GUARD_MS } from '../mode/machine'
import { type CardArea, planTap, wakes } from './tap'
import { useMode } from './useMode'
import { useParentSession } from './useParentSession'
import { useStage } from './useStage'
import { useTheme } from './useTheme'
import { useWakeLock } from './useWakeLock'

/** Long enough that a glance at the clock never opens the PIN pad. */
const LONG_PRESS_MS = 1500

function pointOf(event: Event): { x: number; y: number } | null {
  if ('clientX' in event) {
    const mouse = event as MouseEvent
    return { x: mouse.clientX, y: mouse.clientY }
  }
  const touch = (event as TouchEvent).touches?.[0]
  return touch ? { x: touch.clientX, y: touch.clientY } : null
}

export default function Shell() {
  const liveNonce = useLiveNonce()
  const live = useLive()
  const data = useMantelData(liveNonce)
  const settings = data.config ? data.config.settings : null
  const photos = usePhotos(settings ? settings.refresh_minutes : 5)
  const { state, dispatch } = useMode(settings)
  // Fetched the first time the list is opened, then kept for the session.
  const agenda = useAgenda(state.mode === 'LIST')
  const stage = useStage()

  useWakeLock()
  // Parent mode is always dim, whatever it was opened from.
  // The parent screen used to force the dim palette, from when dim was the
  // only palette worth having. Now that day is paper, a parent opening it at
  // four in the afternoon should get the same room the dashboard is in.
  useTheme(data.config, state.underlying)
  useDailyReload(settings ? settings.daily_reload : '04:00')
  useVersionReload(data.version, state)
  // A reload asked for arrives on the live stream at once, or on the poll.
  useReloadFlag(
    data.lastUpdated === null ? undefined : (live.reloadAt ?? data.reloadAt),
    state.mode,
  )

  const [askingPin, setAskingPin] = useState(false)
  // Remembered for the session: someone reading the almanac is usually
  // going to look at more than one month.
  const [panchangMode, setPanchangMode] = useState(false)
  const [listFilters, setListFilters] = useState<Filter[]>([])
  // The day the list opens at, when it is opened from a count on the
  // dashboard rather than from the month.
  const [listStart, setListStart] = useState<string | null>(null)
  // Bumped whenever a claim or an approval lands, so the balances refetch
  // then rather than at the end of the five minute poll.
  const [pointsNonce, setPointsNonce] = useState(0)
  const [pinned, setPinned] = useState<PinState>({ pins: {} })
  // What each child tapped tonight. Held here rather than fetched on every
  // night render: the check-in is one tap and the answer is on the screen
  // before the API confirms it.
  const [felt, setFelt] = useState<Record<string, Feeling>>({})
  // Which waiting row is showing its Yes and Not yet, and the row a parent
  // held down before the PIN pad came up in front of it.
  const [deciding, setDeciding] = useState<{ kid: string; taskId: string; claimId: number } | null>(
    null,
  )
  const heldRef = useRef<{ kid: string; taskId: string; claimId: number } | null>(null)
  // One burst per kid per approval. A balance that went up is a parent
  // having said yes, which is the one signal that means the same thing
  // wherever the yes was said — the approvals tab, a row on the dashboard,
  // or an award. Counted here rather than at each call site so that two
  // screens watching the same number still see one rise.
  //
  // Derived while rendering rather than in an effect, the way Balance counts
  // its bounces: a balance arriving is not an external system to synchronise
  // with, and the lint rule that forbids the effect is right.
  const [cheers, setCheers] = useState<{
    seen: Record<string, number>
    counts: Record<string, number>
  }>({ seen: {}, counts: {} })

  const kidIds = (data.config?.family.kids ?? []).map((kid) => kid.id)
  // Both move with the live version too, so an approval on a phone is on
  // the wall — and bounces the balance — within a second.
  const points = usePoints(kidIds, pointsNonce + liveNonce)
  const pending = usePending(pointsNonce + liveNonce)
  // The pill asks the API whether the ten minutes are still running, rather
  // than keeping a timer of its own beside a cookie it cannot read.
  const parent = useParentSession()

  // Which cards are latched. Read once: a PIN is set from the parent screen,
  // which reloads the kiosk when it closes.
  useEffect(() => {
    let cancelled = false
    void getJson<PinState>('/api/kids/pins').then(
      (state) => {
        if (!cancelled) {
          setPinned(state)
        }
      },
      () => undefined,
    )
    return () => {
      cancelled = true
    }
  }, [])

  const balances: Record<string, number> = {}
  const risen: string[] = []
  for (const [kidId, summary] of Object.entries(points)) {
    balances[kidId] = summary.balance
    if (shouldFire(cheers.seen[kidId] ?? null, summary.balance)) {
      risen.push(kidId)
    }
  }
  if (risen.length > 0 || Object.keys(balances).length !== Object.keys(cheers.seen).length) {
    // Adjusting state while rendering, which React re-runs immediately. The
    // first sighting of a number is not a rise, so nothing fires when the
    // dashboard first loads into an empty kitchen.
    const counts = { ...cheers.counts }
    for (const kidId of risen) {
      counts[kidId] = (counts[kidId] ?? 0) + 1
    }
    setCheers({ seen: balances, counts })
  }

  // Where a kid's screen opens: their card, or — from the dots on the wall —
  // their week of meals.
  const [kidStart, setKidStart] = useState<'none' | 'meal'>('none')
  // The chip a kid tapped on the wall, which pulses once in their screen.
  const [kidPulse, setKidPulse] = useState<string | null>(null)
  const openKid = useCallback(
    (kid: string, taskId?: string) => {
      setKidStart('none')
      setKidPulse(taskId ?? null)
      dispatch({ type: 'kid-open', kid, now: Date.now() })
    },
    [dispatch],
  )
  const openWeek = useCallback(
    (kid: string) => {
      setKidStart('meal')
      setKidPulse(null)
      dispatch({ type: 'kid-open', kid, now: Date.now() })
    },
    [dispatch],
  )
  const closeKid = useCallback(() => dispatch({ type: 'kid-close', now: Date.now() }), [dispatch])

  const openList = useCallback(() => {
    setListStart(null)
    dispatch({ type: 'list-open', now: Date.now() })
  }, [dispatch])
  // From the dashboard: "+N more" on a card is that child's list, and a count
  // of events is the list at that day with nothing filtered out of it.
  const openListFor = useCallback(
    (request: ListRequest) => {
      setListFilters(
        request.kid ? [request.kid] : request.family ? ['family'] : [],
      )
      setListStart(request.date ?? null)
      dispatch({ type: 'list-open', now: Date.now() })
    },
    [dispatch],
  )
  const closeList = useCallback(
    () => dispatch({ type: 'list-close', now: Date.now() }),
    [dispatch],
  )

  const openMonth = useCallback(() => dispatch({ type: 'month-open', now: Date.now() }), [dispatch])
  const closeMonth = useCallback(
    () => dispatch({ type: 'month-close', now: Date.now() }),
    [dispatch],
  )

  const rootRef = useRef<HTMLDivElement | null>(null)
  const modeRef = useRef(state.mode)
  // The whole state, for the pointer listeners below, which are attached
  // once and read it when a finger lands.
  const stateRef = useRef(state)
  // Set the instant a tap wakes the screen, before the reducer's own
  // justWokeUntil has rendered: the click that follows the waking
  // pointerdown can arrive in the same frame.
  const deafRef = useRef(0)
  // A short tap on the clock during a peek goes back to the night; a long
  // one is still the way in to the parent screen.
  const clockTapRef = useRef(false)
  // Where the two cards were, the last time the dashboard was up. Measured
  // after paint rather than read during render, which is what the lint rules
  // in this project exist to stop — and kept because the frame that covers
  // them is exactly when the answer is wanted.
  const cardsRef = useRef<CardArea[]>([])
  const tapsRef = useRef<number[]>([])
  const pressRef = useRef<number | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    modeRef.current = state.mode
    stateRef.current = state
  }, [state])

  useEffect(() => {
    if (state.mode !== 'DAY') {
      return
    }
    const found: CardArea[] = []
    for (const node of document.querySelectorAll('[data-kid-card]')) {
      const kid = node.getAttribute('data-kid-card')
      const box = node.getBoundingClientRect()
      if (kid && box.width > 0) {
        found.push({
          kid,
          left: box.left,
          top: box.top,
          right: box.right,
          bottom: box.bottom,
        })
      }
    }
    if (found.length > 0) {
      cardsRef.current = found
    }
  }, [state.mode, data.today, stage.width, stage.height])

  useEffect(() => {
    const node = rootRef.current
    if (!node) {
      return
    }

    const cancelPress = () => {
      if (pressRef.current !== null) {
        window.clearTimeout(pressRef.current)
        pressRef.current = null
      }
    }

    const deafUntil = () => Math.max(stateRef.current.justWokeUntil, deafRef.current)

    const onDown = (event: Event) => {
      const now = Date.now()
      const mode = modeRef.current
      const target = event.target as HTMLElement | null
      // The night screen's own controls act there rather than waking the day.
      const live = mode === 'NIGHT' && target?.closest('[data-night-live]') != null
      // Three quick taps in the top-left corner open diagnostics; the tap that
      // wakes the frame or the night screen is swallowed, and so is anything
      // in the 600ms after. The rules live in tap.ts.
      const plan = planTap(mode, pointOf(event), tapsRef.current, now, {
        live,
        deafUntil: deafUntil(),
      })
      tapsRef.current = plan.taps

      if (plan.consume) {
        event.stopPropagation()
        event.preventDefault()
      }
      if (plan.diag) {
        navigate('/diag')
        return
      }

      // The wake: the day comes up, and nothing under the finger hears about
      // it — not the kid's head, not the Parents pill, not a long press.
      if (wakes(mode, live)) {
        cancelPress()
        deafRef.current = now + WAKE_GUARD_MS
        dispatch({ type: 'touch', now })
        return
      }
      if (plan.consume || live) {
        return
      }

      // A long press on the clock is the way in to parent mode: invisible to
      // a passing tap, and only from the two screens that show a clock.
      const onClock = target ? target.closest('[data-clock]') !== null : false
      if (onClock && (mode === 'DAY' || mode === 'NIGHT')) {
        cancelPress()
        clockTapRef.current = stateRef.current.peekUntil !== null
        pressRef.current = window.setTimeout(() => {
          pressRef.current = null
          clockTapRef.current = false
          setAskingPin(true)
        }, LONG_PRESS_MS)
      }

      dispatch({ type: 'touch', now })
    }

    // The rest of a swallowed tap: its pointerup and its click land on the
    // day screen that replaced the frame, and must not do anything there.
    const onRest = (event: Event) => {
      if (Date.now() < deafUntil()) {
        event.stopPropagation()
        event.preventDefault()
      }
    }

    const onUp = () => {
      // Released before the long press fired: during a peek, back to night.
      if (clockTapRef.current && pressRef.current !== null) {
        clockTapRef.current = false
        cancelPress()
        dispatch({ type: 'peek-end', now: Date.now() })
        return
      }
      clockTapRef.current = false
      cancelPress()
    }

    // A key is a hand on the machine too (a laptop running the kiosk). These
    // two listeners are the only things that restart idle: data landing, the
    // live stream and its heartbeats, the version poll and the clock tick
    // never dispatch a touch.
    const onKey = () => dispatch({ type: 'touch', now: Date.now() })
    window.addEventListener('keydown', onKey, { capture: true })

    // Pointer Events have been in Safari since 13; both iPads run 18.7.
    node.addEventListener('pointerdown', onDown, { capture: true, passive: false })
    node.addEventListener('pointerup', onUp, { capture: true })
    for (const name of ['pointercancel', 'pointermove'] as const) {
      node.addEventListener(name, cancelPress, { capture: true })
    }
    for (const name of ['pointerup', 'click', 'contextmenu'] as const) {
      node.addEventListener(name, onRest, { capture: true })
    }
    return () => {
      cancelPress()
      window.removeEventListener('keydown', onKey, { capture: true })
      node.removeEventListener('pointerdown', onDown, { capture: true })
      node.removeEventListener('pointerup', onUp, { capture: true })
      for (const name of ['pointercancel', 'pointermove'] as const) {
        node.removeEventListener(name, cancelPress, { capture: true })
      }
      for (const name of ['pointerup', 'click', 'contextmenu'] as const) {
        node.removeEventListener(name, onRest, { capture: true })
      }
    }
  }, [dispatch, navigate])

  const kidColours: Record<string, string> = {}
  const kidNames: Record<string, string> = {}
  for (const kid of data.config?.family.kids ?? []) {
    // The drawn shade, so the month's bars and legend lighten at night too.
    kidColours[kid.id] = `var(--shade-${kid.id}, ${kid.color})`
    kidNames[kid.id] = kid.name
  }

  // A parent holding a waiting row. The ten minutes a PIN buys are the API's
  // own session, so a second approval inside that window skips the pad; the
  // pad itself is unchanged, and the row it was opened for is remembered
  // across it. A failure to reach the API reads as no session, which costs a
  // PIN entry and never a wrong approval.
  const holdTask = useCallback((kidId: string, task: TaskEntry) => {
    if (task.claim_id === null) {
      return
    }
    const row = { kid: kidId, taskId: task.id, claimId: task.claim_id }
    void sessionOpen().then((open) => {
      if (open) {
        setDeciding(row)
        return
      }
      heldRef.current = row
      setAskingPin(true)
    })
  }, [])

  // The pill. A live session goes straight through; otherwise the pad, and
  // the pad's own success handler decides where to land.
  const openParents = useCallback(() => {
    heldRef.current = null
    if (parent.open) {
      dispatch({ type: 'parent-open', now: Date.now() })
      return
    }
    setAskingPin(true)
  }, [dispatch, parent.open])

  const endParents = useCallback(() => {
    void signOut().then(() => parent.refresh())
    if (modeRef.current === 'PARENT') {
      dispatch({ type: 'parent-close', now: Date.now() })
    }
  }, [dispatch, parent])

  const settle = useCallback(
    (decide: (claimId: number) => Promise<unknown>) => {
      const row = deciding
      if (!row) {
        return
      }
      setDeciding(null)
      void decide(row.claimId)
        .then(() => setPointsNonce((count) => count + 1))
        .catch(() => setPointsNonce((count) => count + 1))
    },
    [deciding],
  )

  let screen = (
    <DayScreen
      today={data.today}
      tomorrow={data.tomorrow}
      upcoming={data.upcoming}
      weather={data.weather}
      onOpenMonth={openMonth}
      points={points}
      onOpenKid={openKid}
      week={data.week}
      onOpenWeek={openWeek}
      pending={pending}
      session={parent.open}
      onParents={openParents}
      onParentsDone={endParents}
      nightStart={settings ? settings.night.start : undefined}
      onHoldTask={holdTask}
      cheers={cheers.counts}
      deciding={deciding}
      onApprove={() => settle(approveClaim)}
      onDecline={() => settle(declineClaim)}
      height={stage.height}
      width={stage.width}
      onOpenList={openListFor}
    />
  )
  if (state.mode === 'MONTH') {
    const today = data.today?.date ?? new Date().toISOString().slice(0, 10)
    screen = (
      <MonthScreen
        initialYm={today.slice(0, 7)}
        today={today}
        kidColours={kidColours}
        kidNames={kidNames}
        panchang={panchangMode}
        onPanchangChange={setPanchangMode}
        onShowList={openList}
        onDone={closeMonth}
      />
    )
  } else if (state.mode === 'LIST') {
    screen = (
      <ListScreen
        agenda={agenda}
        kids={data.config?.family.kids ?? []}
        today={data.today?.date ?? new Date().toISOString().slice(0, 10)}
        filters={listFilters}
        onFiltersChange={setListFilters}
        startDate={listStart}
        onShowMonth={openMonth}
        onDone={closeList}
      />
    )
  } else if (state.mode === 'KID' && state.kid) {
    const open = data.today?.kids.find((kid) => kid.id === state.kid) ?? null
    const other = data.today?.kids.find((kid) => kid.id !== state.kid) ?? null
    if (open) {
      screen = (
        <KidScreen
          // A different kid is a different screen: their own claims, their
          // own sheet, their own pad.
          key={open.id}
          kid={open}
          other={other}
          now={minutesOfDay(new Date())}
          points={points}
          // The code, unless they gave it in the last two minutes of using
          // the screen (the reducer's kidGrace, cleared when it runs out).
          locked={pinned.pins[open.id] === true && state.kidGrace?.kid !== open.id}
          onUnlock={() => dispatch({ type: 'kid-unlock', kid: open.id, now: Date.now() })}
          pulse={kidPulse}
          onSwitch={(kidId, areas) => {
            if (areas.length > 0) {
              cardsRef.current = areas
            }
            setKidStart('none')
            setKidPulse(null)
            dispatch({ type: 'kid-open', kid: kidId, now: Date.now() })
          }}
          height={stage.height}
          width={stage.width}
          onDone={closeKid}
          onChanged={() => setPointsNonce((count) => count + 1)}
          startOn={kidStart}
          from={cardsRef}
        />
      )
    }
  } else if (state.mode === 'FRAME') {
    screen = (
      <FrameScreen
        photos={photos}
        slideSeconds={settings ? settings.slide_seconds : 20}
        night={state.underlying === 'NIGHT'}
        weather={data.weather}
        chip={settings?.frame?.chip ?? true}
        chipLarge={settings?.frame?.size === 'large'}
      />
    )
  } else if (state.mode === 'NIGHT') {
    screen = (
      <NightScreen
        today={data.today}
        tomorrow={data.tomorrow}
        weather={data.weather}
        nightEnd={settings ? settings.night.end : undefined}
        pending={pending}
        session={parent.open}
        onParents={openParents}
        onParentsDone={endParents}
        onOpenMonth={openMonth}
        asking={settings?.feelings?.enabled === true}
        felt={felt}
        onFelt={(kidId, feeling) => setFelt((said) => ({ ...said, [kidId]: feeling }))}
      />
    )
  } else if (state.mode === 'PARENT') {
    screen = (
      <ParentScreen
        kids={data.config?.family.kids ?? []}
        parents={data.config?.family.parents ?? []}
        pending={pending}
        idleMinutes={settings?.points?.parent_idle_minutes}
        // A decision in parent mode moves a balance the wall is showing: read
        // them again, which is also what makes the number bounce.
        onPointsChanged={() => setPointsNonce((count) => count + 1)}
        onDone={() => {
          dispatch({ type: 'parent-close', now: Date.now() })
          parent.refresh()
          setPointsNonce((count) => count + 1)
        }}
      />
    )
  }

  return (
    <div className="stage" ref={rootRef} style={{ width: stage.width, height: stage.height }}>
      {/* DAY, NIGHT, MONTH, LIST and FRAME are laid out upright too. What
          still asks to be turned is what was drawn for the wide screen only:
          a child's own card (KID mode, and its code pad behind it), the
          parent screen on an iPad, and the parent PIN pad. */}
      {stage.portrait && (state.mode === 'KID' || state.mode === 'PARENT' || askingPin) ? (
        <div className="screen screen-center">
          <div className="rotate">{copy.shell.turnSideways}</div>
        </div>
      ) : (
        <>
          {/* Keyed on the mode, so every change of screen — DAY and KID,
              MONTH and LIST, NIGHT, the frame — fades in over 200ms. */}
          <div key={state.mode} className="screen-wrap mode-in">
            {screen}
          </div>
          {['FRAME', 'PARENT', 'MONTH', 'LIST', 'KID'].includes(state.mode) ? null : (
            <StaleDot lastUpdated={data.lastUpdated} />
          )}
          {askingPin ? (
            <PinPad
              pending={pending}
              onOpen={() => {
                setAskingPin(false)
                parent.refresh()
                // Opened from a row rather than from the clock: go back to
                // that row with the pair on it, not to the parent screen.
                const held = heldRef.current
                heldRef.current = null
                if (held) {
                  setDeciding(held)
                  return
                }
                dispatch({ type: 'parent-open', now: Date.now() })
              }}
              onCancel={() => {
                heldRef.current = null
                setAskingPin(false)
              }}
            />
          ) : null}
        </>
      )}
    </div>
  )
}
