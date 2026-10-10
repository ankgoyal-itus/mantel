/**
 * Hand-maintained mirror of the API's response models.
 *
 * The API writes its JSON schema to services/api/schema/*.json on every test
 * run, so a change on that side shows up as a diff there. When it does, update
 * this file to match.
 */

export type Kid = {
  id: string
  name: string
  color: string
  avatar: string | null
  /** MM-DD, or null. No year is stored anywhere. */
  birthday?: string | null
}
export type Parent = { id: string; name: string; birthday?: string | null }
export type Family = { kids: Kid[]; parents: Parent[] }

export type Location = { name: string; lat: number; lon: number }
export type Units = { temp: 'F' | 'C' }
export type NightSettings = {
  start: string
  end: string
  idle_minutes: number
  frame: boolean
}
export type DateRange = { from: string; to: string; name: string }
export type School = { no_school: string[]; breaks: DateRange[] }
export type Protein = 'veg' | 'egg' | 'chicken' | 'fish'
/**
 * settings.diet, as the API actually sends it.
 *
 * This said `no_non_veg_dates`, which the API has never had a field called.
 * Nothing read it, so nothing noticed — until a card did, and `undefined`
 * has no `.length`, and the whole parent screen went blank. A hand-written
 * type only checks what it was told, so the names here are the names in
 * mantel_api/models.py: Diet, around line 240.
 */
export type Diet = {
  vegetarian: string[]
  non_veg_ok: string[]
  non_veg_days: Weekday[]
  /** Matched by name against the festival feeds; each runs for span_days. */
  no_non_veg_festivals: { match: string; span_days: number }[]
  /** Named by hand, for the festivals no feed carries. */
  no_non_veg_dates_extra: DateRange[]
  /** Manual exceptions the other way: a day the rule is lifted. */
  non_veg_ok_dates: { date: string; reason: string }[]
}
export type CalendarFeed = { id: string; kid: string; url_env: string }

export type PointsSettings = {
  streak_bonus: number
  streak_days: number
  roblox_per_week: number
  deductions: boolean
  parent_idle_minutes: number
}

/** settings.banks: the least a child may cash out, and the Roblox sizes. */
export type BankSettings = { cash_out_min_cents: number; roblox_use_sizes: number[] }

export type AllowanceSettings = { amount_note: string; reminder_hour: number }

export type Settings = {
  timezone: string
  location: Location
  units: Units
  night: NightSettings
  idle_minutes: number
  slide_seconds: number
  refresh_minutes: number
  daily_reload: string
  school: School
  calendars: CalendarFeed[]
  diet: Diet
  points: PointsSettings
  banks?: BankSettings
  allowance: AllowanceSettings
  feelings: { enabled: boolean }
  /** The clock and weather chip on the photo frame. */
  frame?: { chip: boolean; size: 'regular' | 'large' }
}

export type Config = { family: Family; settings: Settings }

export type Weekday = 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun'

export type AgendaEntry = {
  start: string | null
  end: string | null
  title: string
  where: string | null
  note: string | null
  source: string
  /** kid | family | school | holiday | festival, for the list view's filter. */
  source_kind: string | null
  all_day: boolean
  calendar_id: string | null
}

export type ClaimStatus = 'none' | 'claimed' | 'approved' | 'declined'

export type Routine = 'morning' | 'afternoon' | 'evening'

export type TaskEntry = {
  id: string
  title: string
  /** Who ticks it off. A parent's task shows a lock and does not respond. */
  claim: 'kid' | 'parent'
  /** What has happened to it today, so the dashboard can show it unopened. */
  status: ClaimStatus
  points: number
  /** Which container it sits in on the card. */
  routine: Routine
  /** The waiting claim, so the dashboard can approve the row in place. */
  claim_id: number | null
  /** 'week': done once a week, and its status is the week's. */
  every?: 'day' | 'week'
}

export type Claim = {
  id: number
  kid_id: string
  task_id: string
  date: string
  status: 'claimed' | 'approved' | 'declined'
  claimed_at: string
  decided_at: string | null
  decided_by: string | null
}

export type SavingFor = {
  reward_id: string
  name: string
  glyph: string
  cost: number
}

export type Feeling = 'great' | 'good' | 'okay' | 'meh' | 'rough'

export type PointsSummary = {
  kid_id: string
  balance: number
  this_week: number
  /** Earned on each day of this week, Monday first. */
  week_days?: number[]
  streak_days: number
  /** Up to two rewards they have starred, in the order they chose them. */
  saving_for: SavingFor[]
  /** The piggy bank, in cents, and the Roblox bank, in minutes. */
  cash_cents?: number
  roblox_minutes?: number
  /** The newest reward approved into either bank, for the card's toast. */
  last_deposit?: BankRow | null
}

export type LedgerRow = {
  id: number
  kid_id: string
  delta: number
  reason_kind: 'task' | 'award' | 'redeem' | 'refund' | 'adjust' | 'jar'
  reason_ref: string | null
  note: string | null
  actor: 'kid' | 'parent'
  created_at: string
  /** What a parent may do to put it right; empty once corrected. */
  can?: ('undo' | 'move')[]
}

export type Reward = {
  id: string
  name: string
  cost: number
  fulfilment: 'manual' | 'allowance' | 'meal' | 'policy' | 'bank'
  glyph: string
  family: boolean
  enabled: boolean
  days: number | null
  minutes: number | null
  /** For bank: dollars into the piggy bank (or `minutes` into the Roblox bank). */
  dollars?: number | null
}

export type PinState = { pins: Record<string, boolean> }

export type Redemption = {
  id: number
  kid_id: string
  reward_id: string
  points: number
  status: 'requested' | 'approved' | 'scheduled' | 'fulfilled' | 'declined' | 'refunded'
  requested_at: string
  decided_at: string | null
  fulfilment_ref: string | null
  note: string | null
  name: string
  glyph: string
}

export type Todo = {
  ref: string
  kind: 'manual' | 'allowance' | 'cashout' | 'roblox'
  kid_id: string
  title: string
  day: number | null
  days: number | null
  due: string | null
  /** The reward a redemption to-do is for: "dinner_out" offers Plan it. */
  reward_id?: string | null
  /** A bank request: the cash to pay, or the Roblox time to give. */
  cents?: number | null
  minutes?: number | null
  request_id?: number | null
}

export type DigestKid = {
  kid_id: string
  name: string
  earned: number
  spent: number
  approved: Record<string, string[]>
  redemptions: string[]
  /** Money and Roblox time in and out of their banks: "+$5 · $5 cash". */
  bank?: string[]
  picks: string[]
}

export type Digest = {
  week: string
  start: string
  end: string
  kids: DigestKid[]
  /** The meals eaten out that week: "Sat dinner: Out · Taqueria Luna". */
  out?: string[]
}

/** One dish chosen for a proposed slot, and the children who chose it. */
export type MealChoice = { id: string; name: string; kids: string[] }

export type MealSlotName = 'breakfast' | 'lunch' | 'dinner'

export type ApprovalItem = {
  /** A chore claimed, a reward asked for, or a meal a child picked. */
  kind: 'claim' | 'redemption' | 'meal' | 'treat'
  id: number
  kid_id: string
  title: string
  points: number
  when: string
  note: string | null
  /** For a meal: the slot, each dish chosen and by whom, and the plan they
      replaced. Contested ("Parents decide") when there is more than one. */
  date?: string | null
  slot?: MealSlotName | null
  choices?: MealChoice[]
  plan_name?: string | null
  contested?: boolean
  /** A treat pick waiting on a parent's OK. */
  pick_id?: number | null
}

export type KidDay = {
  id: string
  name: string
  color: string
  avatar: string | null
  agenda: AgendaEntry[]
  tasks: TaskEntry[]
  /** True on their birthday, which the card says out loud. */
  birthday: boolean
}

export type MealSlot = {
  name: string
  note: string | null
  kids_protein: Protein
  id: string | null
  /** Whose choice this was. A kid who picked a meal should see their name. */
  picked_by: string[]
  /** A pick is a proposal until a parent says yes. */
  confirmed: boolean
  /** The catalog dish a parent planned, when a pick replaced it. */
  plan?: string | null
  /** Each child's own choice while the slot is a proposal (14c). */
  picks?: Record<string, { id: string; kids_protein?: Protein; reward?: number | null }>
}

/** Two children, two different dishes, one slot: a parent decides. */
export function isContested(slot: MealSlot): boolean {
  if (slot.confirmed || !slot.picks) {
    return false
  }
  return new Set(Object.values(slot.picks).map((pick) => pick.id)).size > 1
}

export type PickOption = {
  id: string
  name: string
  treat: boolean
  cost: number
  proteins: Protein[]
  pickable: boolean
  why: string | null
  /** What kind of food it is; the picker groups the list by it. */
  cuisine: string
  /** True when this is what the house ate in that slot the day before. */
  yesterday: boolean
  /** Said, not enforced: "we had this Tuesday". Still pickable. */
  warning?: string | null
  /** The weekday of that repeat, for the kiosk to say itself. */
  repeat_day?: string | null
  /** Another slot's dish, offered here too: listed last, under one header. */
  also?: boolean
  /** Lunch out or Dinner out: a place, drawn as a tile rather than a dish. */
  out?: boolean
}

export type PickStatus = 'proposed' | 'chosen' | 'moved' | 'passed'

/** One child's choice for one meal, as the picks table holds it. */
export type PickRow = {
  id: number
  kid_id: string
  date: string
  slot: MealSlotName
  dish_id: string
  kids_protein: Protein
  status: PickStatus
  decided_by: string | null
  decided_at: string | null
  moved_to: string | null
  created_at: string
  note: string | null
  name: string
  treat: boolean
}

/** One meal as it resolves: the plan, the picks, and what it comes to. */
export type SlotView = {
  date: string
  slot: MealSlotName
  plan: MealSlot | null
  picks: PickRow[]
  resolved: MealSlot | null
  contested: boolean
  locked: boolean
  decided: boolean
}

export type DayPicks = { date: string; breakfast: SlotView; lunch: SlotView; dinner: SlotView }

export type DecisionResult = {
  slot: MealSlotName
  winner_kid_id: string
  winner_date: string
  loser_kid_id: string | null
  loser_date: string | null
}
export type DayMeals = {
  breakfast: MealSlot | null
  lunch: MealSlot | null
  dinner: MealSlot | null
  snack: MealSlot | null
}

export type WeatherNow = { temp: number; label: string; icon: string; is_day: boolean }
export type WeatherDay = {
  high: number
  low: number
  precip_pct: number | null
  sunrise: string
  sunset: string
  label: string
  icon: string
}
export type Weather = {
  now: WeatherNow | null
  today: WeatherDay | null
  tomorrow: WeatherDay | null
  stale: boolean
  fetched_at: string | null
}

export type CalendarKind = 'kid' | 'family' | 'holiday' | 'festival' | 'school'

export type Observance = { name: string; kind: CalendarKind; calendar_id: string }

/** Whether the kids may eat meat today, and why not when they may not. */
export type DayDiet = { non_veg_ok: boolean; reasons: string[] }

export type Day = {
  date: string
  weekday: Weekday
  is_school_day: boolean
  school_note: string | null
  kids: KidDay[]
  family_agenda: AgendaEntry[]
  meals: DayMeals
  observances: Observance[]
  diet: DayDiet
  weather: Weather
}

export type DishSlot = 'breakfast' | 'lunch' | 'dinner' | 'snack' | 'salad'

export type Dish = {
  id: string
  name: string
  slot: DishSlot
  protein: Protein[]
  cuisine: string
  minutes: number
  lunchbox: boolean
  weekend: boolean
  treat: boolean
  two_ways: string
  recipe_url: string
}

export type Photo = {
  id: string
  url: string
  w: number
  h: number
  /** "2024-06-14", or null when the file carried no capture date. */
  taken_at: string | null
  /** The nearest town when the photo carried a fix, resolved by the API
      from a bundled gazetteer. The coordinates are never sent. */
  place?: string | null
  /** When it arrived, which is what the parent screen reports. */
  added_at?: string | null
  /** The stored file's size, for the total on the parent screen. */
  bytes?: number
}

export type FestivalRule = { match: string; span_days: number }

/** One festival, its aliases folded in. The aliases are never drawn. */
export type FestivalGroup = { name: string; span_days: number; matches: string[] }

export type KidEdit = { id: string; name: string; avatar: string | null; color: string }

/** Everything the parent screen may change, written back in one PUT. */
export type ParentSettings = {
  night_start: string
  night_end: string
  idle_minutes: number
  night_idle_minutes: number
  night_frame: boolean
  slide_seconds: number
  refresh_minutes: number
  /** Settings → Photos: the clock and weather chip, and its size. */
  frame_chip?: boolean
  frame_chip_size?: 'regular' | 'large'
  diet: {
    non_veg_days: Weekday[]
    /** The file's own list, alias by alias: what a write carries. */
    festivals: FestivalRule[]
    extra_dates: DateRange[]
    /** The same, once per festival, for the screen. Derived; not written. */
    groups?: FestivalGroup[]
  }
  points: PointsSettings
  banks?: BankSettings
  kids: KidEdit[]
}

export type MealCell = {
  name: string
  note: string
  /** The catalog dish, when it was picked from the list rather than typed. */
  id: string
  /** Whose pick it was, if a kid chose it. */
  picked_by: string[]
  /** False while it is still a proposal. */
  confirmed: boolean
  /** The plan a pick replaced, by name. */
  plan_name: string
  /** True when the children chose different dishes. */
  contested: boolean
  choices: MealChoice[]
}

export type MealDay = {
  date: string
  breakfast: MealCell
  lunch: MealCell
  dinner: MealCell
}

export type PanchangLimb = { name: string; index: number; ends_at: string | null }
export type PanchangTithi = PanchangLimb & { paksha: string }
export type PanchangSchool = { is_school_day: boolean; note: string | null }

export type PanchangDay = {
  date: string
  sunrise: string | null
  sunset: string | null
  moonrise: string | null
  moonset: string | null
  vaara: string
  tithi: PanchangTithi
  nakshatra: PanchangLimb
  yoga: PanchangLimb
  karana: PanchangLimb
  masa: { name: string; adhika: boolean }
  samvat: { vikram: number; shaka: number }
  flags: string[]
  observances: Observance[]
  school: PanchangSchool
  diet: DayDiet
  meals: Record<string, string | null>
}

/** One cell of the month grid. */
export type MonthDay = {
  date: string
  weekday: Weekday
  tithi_short: string
  paksha: string
  nakshatra: string
  masa: string
  flags: string[]
  observances: string[]
  school: PanchangSchool
  /** Kids with a school event that day. */
  school_kids: string[]
  /** "Dwadashi": the tithi by name, for panchang mode. */
  tithi_name?: string
  /** Kids with anything on that day, from any feed: a bar each. */
  kids?: string[]
  /** The first observance is a holiday rather than a festival. */
  holiday?: boolean
  /** Something on the family's own calendars. */
  family?: boolean
  non_veg_ok: boolean
  has_meals: boolean
}

export type PanchangMonth = { ym: string; days: MonthDay[] }

export type ContentStatus = {
  family: string
  settings: string
  schedule: string
  meals: string
  'meals-catalog': string
  tasks: string
}

export type Health = {
  status: string
  version: string
  time: string
  content: ContentStatus
  weather: string
  calendars: Record<string, string>
  school_year?: string
  diet_days?: string
  ledger?: string
  /** Set when a parent asks both iPads to reload. */
  reload_at?: string | null
}

export type CalendarRow = {
  id: string
  kind: string
  kid: string | null
  /** The feed's own name from settings.yaml, when it has one. */
  name?: string | null
  state: 'ok' | 'stale' | 'error' | 'not_configured' | 'never'
  fetched_at: string | null
  detail: string
  /** For a private feed, the .env variable its URL lives in. */
  env: string | null
}

export type About = { version: string; lan_url: string; launchd: string; upload_token: boolean }

export type DietDay = { date: string; non_veg_ok: boolean; reasons: string[] }

/** One occurrence of a school series, as the parent screen lists it. */
export type SeriesEvent = {
  title: string
  date: string
  start: string | null
  end: string | null
  where: string | null
  calendar_id: string
}

/** A group of school events a parent decides about at once. */
export type Series = {
  series: string
  title: string
  count: number
  next_date: string | null
  rule: string | null
  always: boolean
  shown_to: string[]
  events: SeriesEvent[]
}

export type SeriesEdit = {
  series?: string
  kids?: string[]
  default?: 'hide' | 'show'
}

/** The state version the screens watch (/api/version, /api/events). */
export type VersionInfo = { version: number; changed_at: string | null }

export type BankAccount = 'cash' | 'roblox'

/** One line of a child's bank: cents for cash, minutes for Roblox. */
export type BankRow = {
  id: number
  kid_id: string
  account: BankAccount
  delta: number
  reason_kind: 'deposit' | 'cashout' | 'use' | 'adjust'
  reason_ref: string | null
  note: string | null
  actor: 'kid' | 'parent' | 'system'
  created_at: string
}

/** A cash-out or a Roblox use, waiting on a parent. It holds its amount. */
export type BankRequest = {
  id: number
  kid_id: string
  account: BankAccount
  amount: number
  status: 'requested' | 'done' | 'declined'
  requested_at: string
  decided_at: string | null
  bank_id: number | null
}

export type KidBank = {
  kid_id: string
  cash: { cents: number; available_cents: number; pending: BankRequest[] }
  roblox: {
    minutes: number
    available_minutes: number
    pending: BankRequest[]
    uses_this_week: number
    per_week: number
    sizes: number[]
  }
  cash_out_min_cents: number
  recent: BankRow[]
}

export type ParentBanks = { kids: KidBank[]; todos: Todo[] }
