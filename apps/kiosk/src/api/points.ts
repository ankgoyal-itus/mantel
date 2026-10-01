/**
 * The writing half of the kiosk's API surface.
 *
 * Everything here is a child's tap: claiming a task, taking it back, opening
 * their own card. None of it moves points on its own — a claim is a request
 * until a parent decides, which happens on the parent screen.
 */

import type { Claim, DayPicks, Feeling, PickOption, PinState, PointsSummary, Redemption, SlotView } from './types'

const TIMEOUT_MS = 8000

async function send<T>(path: string, method: string, body?: unknown): Promise<T> {
  const controller = typeof AbortController === 'function' ? new AbortController() : null
  const timer = controller ? window.setTimeout(() => controller.abort(), TIMEOUT_MS) : null
  try {
    const response = await fetch(path, {
      method,
      signal: controller ? controller.signal : undefined,
      cache: 'no-store',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (!response.ok) {
      throw new Error(`${path} returned ${response.status}`)
    }
    return (response.status === 204 ? undefined : await response.json()) as T
  } finally {
    if (timer !== null) {
      window.clearTimeout(timer)
    }
  }
}

export function claimTask(kidId: string, taskId: string): Promise<Claim> {
  return send<Claim>('/api/claims', 'POST', { kid_id: kidId, task_id: taskId })
}

export function undoClaim(claimId: number): Promise<void> {
  return send<void>(`/api/claims/${claimId}`, 'DELETE')
}

export function verifyKidPin(kidId: string, pin: string): Promise<{ ok: boolean }> {
  return send<{ ok: boolean }>(`/api/kids/${kidId}/pin/verify`, 'POST', { pin })
}

export type { Claim, PickOption, PinState, PointsSummary, Redemption }

export function askForReward(kidId: string, rewardId: string): Promise<Redemption> {
  return send<Redemption>('/api/redemptions', 'POST', {
    kid_id: kidId,
    reward_id: rewardId,
  })
}

export function myRewards(kidId: string): Promise<Redemption[]> {
  return send<Redemption[]>(`/api/redemptions/${kidId}`, 'GET')
}

/** Tonight's one tap. Refused by the API while the check-in is off. */
export function recordFeeling(kidId: string, feeling: Feeling): Promise<unknown> {
  const now = new Date()
  const date = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
    now.getDate(),
  ).padStart(2, '0')}`
  return send<unknown>('/api/feelings', 'POST', { kid_id: kidId, date, feeling })
}

/** Star a reward, or unstar it. A third pick pushes the oldest one off. */
export function markSavingFor(kidId: string, rewardId: string): Promise<PointsSummary> {
  return send<PointsSummary>(`/api/kids/${kidId}/saving/${rewardId}`, 'PUT')
}

export function putInTheJar(kidId: string, points: number): Promise<PointsSummary> {
  return send<PointsSummary>('/api/jar', 'POST', { kid_id: kidId, points })
}

export function pickOptions(
  kidId: string,
  slot: string,
  date: string,
): Promise<PickOption[]> {
  const query = new URLSearchParams({ kid_id: kidId, slot, date })
  return send<PickOption[]>(`/api/picks/options?${query.toString()}`, 'GET')
}

export function pickMeal(
  kidId: string,
  date: string,
  slot: string,
  dishId: string,
  kidsProtein: string,
  place: string | null = null,
): Promise<SlotView> {
  return send<SlotView>('/api/picks', 'POST', {
    kid_id: kidId,
    date,
    slot,
    dish_id: dishId,
    kids_protein: kidsProtein,
    place,
  })
}

/** Seven days of meal picks from today: the week strip and the dots. */
export function weekPicks(days = 7): Promise<DayPicks[]> {
  return send<DayPicks[]>(`/api/picks?days=${days}`, 'GET')
}

/** A child taking their own pick back while it can still change. */
export function withdrawPick(pickId: number, kidId: string): Promise<unknown> {
  return send<unknown>(`/api/picks/${pickId}?kid_id=${kidId}`, 'DELETE')
}

/** The last ten places eaten out, most recent first: the chips above the
    "Where?" field. */
export function recentPlaces(): Promise<string[]> {
  return send<string[]>('/api/places/recent', 'GET')
}
