/**
 * Parent mode talks to the API with a cookie the browser holds and the kiosk
 * cannot read. The PIN itself is never stored here, only posted once.
 */

import type {
  About,
  ApprovalItem,
  CalendarRow,
  DecisionResult,
  DietDay,
  MealSlotName,
  ParentBanks,
  BankAccount,
  PickOption,
  PickRow,
  Digest,
  LedgerRow,
  Health,
  MealDay,
  ParentSettings,
  Photo,
  PinState,
  PointsSummary,
  Redemption,
  Series,
  SeriesEdit,
  Todo,
} from './types'

export type SignIn =
  | { ok: true }
  | { ok: false; reason: 'wrong'; remaining: number }
  | { ok: false; reason: 'locked'; retryAfter: number }
  | { ok: false; reason: 'unconfigured' }
  | { ok: false; reason: 'offline' }

/**
 * A refusal from the API, with its reason in words when it gave one.
 *
 * The settings screen keeps the old value on a failed write and says why,
 * and "settings.yaml would be invalid: …" is a reason; "returned 422" is not.
 */
export class ApiError extends Error {
  status: number
  constructor(path: string, status: number, detail: string | null) {
    super(detail ?? `${path} returned ${status}`)
    this.status = status
  }
}

async function send<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(path, { ...init, credentials: 'same-origin' })
  if (!response.ok) {
    const detail = await response
      .json()
      .then((body: { detail?: unknown }) =>
        typeof body.detail === 'string' ? body.detail : null,
      )
      .catch(() => null)
    throw new ApiError(path, response.status, detail)
  }
  return (await response.json()) as T
}

/** Seconds left on the parent session, and whether there is one. */
export async function sessionLeft(): Promise<number> {
  try {
    const response = await fetch('/api/parent/session', {
      credentials: 'same-origin',
      cache: 'no-store',
    })
    if (!response.ok) {
      return 0
    }
    const body = (await response.json()) as { open?: boolean; expires_in?: number }
    return body.open ? (body.expires_in ?? 0) : 0
  } catch {
    return 0
  }
}

function json(method: string, body?: unknown): RequestInit {
  return {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: 'no-store',
  }
}

export async function signIn(pin: string): Promise<SignIn> {
  let response: Response
  try {
    response = await fetch('/api/parent/session', {
      ...json('POST', { pin }),
      credentials: 'same-origin',
    })
  } catch {
    return { ok: false, reason: 'offline' }
  }

  if (response.ok) {
    return { ok: true }
  }
  if (response.status === 503) {
    return { ok: false, reason: 'unconfigured' }
  }

  type Detail = { remaining?: number; retry_after?: number }
  const detail: Detail = await response
    .json()
    .then((body: { detail?: Detail }) => body.detail ?? {})
    .catch((): Detail => ({}))

  if (response.status === 429) {
    return { ok: false, reason: 'locked', retryAfter: detail.retry_after ?? 60 }
  }
  return { ok: false, reason: 'wrong', remaining: detail.remaining ?? 0 }
}

/**
 * Whether the parent cookie this iPad holds is still good.
 *
 * Asked before the dashboard offers Approve and Decline on a row: a parent
 * who signed in two minutes ago should not have to type the PIN again, and
 * one who did not should not be shown buttons that will fail. A failure to
 * reach the API is a no, which costs a PIN entry and never a wrong approval.
 */
export async function sessionOpen(): Promise<boolean> {
  try {
    const response = await fetch('/api/parent/session', {
      credentials: 'same-origin',
      cache: 'no-store',
    })
    if (!response.ok) {
      return false
    }
    const body = (await response.json()) as { open?: boolean }
    return body.open === true
  } catch {
    return false
  }
}

export function signOut(): Promise<unknown> {
  return send<unknown>('/api/parent/session', json('DELETE')).catch(() => null)
}

export function getSettings(): Promise<ParentSettings> {
  return send<ParentSettings>('/api/parent/settings', json('GET'))
}

export function putSettings(settings: ParentSettings): Promise<ParentSettings> {
  return send<ParentSettings>('/api/parent/settings', json('PUT', settings))
}

export function refreshSources(): Promise<unknown> {
  return send<unknown>('/api/parent/refresh', json('POST'))
}

export function getMeals(from: string, days = 7): Promise<MealDay[]> {
  return send<MealDay[]>(`/api/parent/meals?from=${from}&days=${days}`, json('GET'))
}

export function putMeals(days: MealDay[]): Promise<MealDay[]> {
  return send<MealDay[]>('/api/parent/meals', json('PUT', { days }))
}

export function getPhotos(): Promise<Photo[]> {
  return send<Photo[]>('/api/photos', json('GET'))
}

export function deletePhoto(id: string): Promise<unknown> {
  return send<unknown>(`/api/photos/${id}`, json('DELETE'))
}

export function getHealth(): Promise<Health> {
  return send<Health>('/api/health', json('GET'))
}

export function getSchoolEvents(days = 60): Promise<Series[]> {
  return send<Series[]>(`/api/parent/school-events?days=${days}`, json('GET'))
}

/** Set who sees one series, or flip what happens to undecided ones. */
export function putSchoolEvents(edit: SeriesEdit): Promise<Series[]> {
  return send<Series[]>('/api/parent/school-events', json('PUT', edit))
}

export function getKidPins(): Promise<PinState> {
  return send<PinState>('/api/kids/pins', json('GET'))
}

/** Set a kid's four-digit code, or clear it with an empty string. */
export function putKidPin(kidId: string, pin: string): Promise<PinState> {
  return send<PinState>(`/api/kids/${kidId}/pin`, json('PUT', { pin }))
}

export function getApprovals(): Promise<ApprovalItem[]> {
  return send<ApprovalItem[]>('/api/parent/approvals', json('GET'))
}

export function approveClaim(claimId: number): Promise<PointsSummary> {
  return send<PointsSummary>(`/api/parent/claims/${claimId}/approve`, json('POST'))
}

export function declineClaim(claimId: number): Promise<PointsSummary> {
  return send<PointsSummary>(`/api/parent/claims/${claimId}/decline`, json('POST'))
}

export function awardPoints(
  kidId: string,
  points: number,
  note: string,
): Promise<PointsSummary> {
  return send<PointsSummary>(
    '/api/parent/awards',
    json('POST', { kid_id: kidId, points, note }),
  )
}

export function approveRedemption(id: number): Promise<Redemption> {
  return send<Redemption>(`/api/parent/redemptions/${id}/approve`, json('POST'))
}

export function declineRedemption(id: number): Promise<Redemption> {
  return send<Redemption>(`/api/parent/redemptions/${id}/decline`, json('POST'))
}

export function getTodos(): Promise<Todo[]> {
  return send<Todo[]>('/api/parent/todos', json('GET'))
}

export function finishTodo(ref: string): Promise<Todo[]> {
  return send<Todo[]>('/api/parent/todos/done', json('POST', { ref }))
}


/** The week, added up. Data only: nothing here is generated. */
export function getDigest(week?: string): Promise<Digest> {
  const query = week ? `?week=${encodeURIComponent(week)}` : ''
  return send<Digest>(`/api/digest${query}`, json('GET'))
}

/** Every point that moved, newest first. Parent-gated. */
/** Put a wrong row right: take it back, or move it to the other child. */
export function correctRow(
  rowId: number,
  action: 'undo' | 'move',
  toKid?: string,
): Promise<LedgerRow[]> {
  return send<LedgerRow[]>(
    `/api/parent/ledger/${rowId}/correct`,
    json('POST', { action, to_kid: toKid ?? null }),
  )
}

export function getLedger(kidId?: string, limit = 50): Promise<LedgerRow[]> {
  const query = new URLSearchParams({ limit: String(limit) })
  if (kidId) {
    query.set('kid_id', kidId)
  }
  return send<LedgerRow[]>(`/api/parent/ledger?${query.toString()}`, json('GET'))
}

/** A parent settling a contested meal: one child's dish, or — alternate —
    that dish now and the other child's on the next day it can be. */
export function decidePick(
  date: string,
  slot: MealSlotName,
  winnerKidId: string,
  mode: 'choose' | 'alternate' = 'choose',
): Promise<DecisionResult> {
  return send<DecisionResult>(
    '/api/parent/picks/decide',
    json('POST', { date, slot, winner_kid_id: winnerKidId, mode }),
  )
}

/** A parent's pen on one meal: this dish as the plan, or the plan (null).
    Either way the children's picks for it give way. */
export function setMeal(
  date: string,
  slot: MealSlotName,
  dishId: string | null,
  place: string | null = null,
): Promise<MealDay[]> {
  return send<MealDay[]>(
    '/api/parent/meals/set',
    json('POST', { date, slot, dish_id: dishId, place }),
  )
}

/** Yes or no to a treat a child picked. */
export function answerTreat(pickId: number, approve: boolean): Promise<PickRow> {
  return send<PickRow>(
    `/api/parent/picks/${pickId}/${approve ? 'approve' : 'decline'}`,
    json('POST'),
  )
}

/** The whole catalog for a slot, with why a child could not choose each. */
export function mealOptions(date: string, slot: MealSlotName): Promise<PickOption[]> {
  return send<PickOption[]>(
    `/api/parent/meals/options?slot=${slot}&date=${date}`,
    json('GET'),
  )
}

/** Which days are vegetarian, and why. Public: the wall reads it too. */
export function getDiet(from: string, days: number): Promise<DietDay[]> {
  return send<DietDay[]>(`/api/diet?from=${from}&days=${days}`, json('GET'))
}

export function getCalendars(): Promise<CalendarRow[]> {
  return send<CalendarRow[]>('/api/parent/calendars', json('GET'))
}

export function getAbout(): Promise<About> {
  return send<About>('/api/parent/about', json('GET'))
}

/** Both iPads reload on their next look at /api/health. */
export function reloadBoth(): Promise<Health> {
  return send<Health>('/api/parent/reload', json('POST'))
}

/** Both children's banks, and the cash-outs and Roblox uses waiting. */
export function getBanks(): Promise<ParentBanks> {
  return send<ParentBanks>('/api/parent/banks', json('GET'))
}

/** Birthday money, or a correction: a row of its own, never an edit. Cents
    for cash, minutes for Roblox; negative takes out. */
export function adjustBank(
  kidId: string,
  account: BankAccount,
  delta: number,
  note: string,
): Promise<ParentBanks> {
  return send<ParentBanks>(`/api/parent/banks/${kidId}/adjust`, json('POST', { account, delta, note }))
}

/** Not this time: the hold on a cash-out or Roblox use ends. */
export function declineBankRequest(requestId: number): Promise<Todo[]> {
  return send<Todo[]>(`/api/parent/banks/requests/${requestId}/decline`, json('POST'))
}
