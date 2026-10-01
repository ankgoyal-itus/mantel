/** October 2026 as the API returns it, trimmed to what the grid draws. */

import type { MonthDay, PanchangDay, PanchangMonth } from '../../api/types'

const WEEKDAYS = ['thu', 'fri', 'sat', 'sun', 'mon', 'tue', 'wed'] as const

const TITHI_NAMES = [
  'Pratipada', 'Dwitiya', 'Tritiya', 'Chaturthi', 'Panchami', 'Shashthi', 'Saptami',
  'Ashtami', 'Navami', 'Dashami', 'Ekadashi', 'Dwadashi', 'Trayodashi', 'Chaturdashi',
]

/** "S12" is Dwadashi; the fifteenth is Purnima or Amavasya by the fortnight. */
function nameOf(tithi: string): string {
  const index = Number(tithi.slice(1))
  if (index === 15) {
    return tithi.startsWith('S') ? 'Purnima' : 'Amavasya'
  }
  return TITHI_NAMES[index - 1]
}

function day(
  date: string,
  tithi: string,
  paksha: string,
  partial: Partial<MonthDay> = {},
): MonthDay {
  const number = Number(date.slice(-2))
  return {
    date,
    weekday: WEEKDAYS[(number - 1) % 7],
    tithi_short: tithi,
    tithi_name: nameOf(tithi),
    paksha,
    nakshatra: 'Chitra',
    masa: 'Ashwin',
    flags: [],
    observances: [],
    school: { is_school_day: true, note: null },
    school_kids: [],
    non_veg_ok: true,
    has_meals: false,
    ...partial,
  }
}

export const OCTOBER: PanchangMonth = {
  ym: '2026-10',
  days: [
    day('2026-10-09', 'K13', 'krishna'),
    day('2026-10-10', 'K15', 'krishna', { flags: ['amavasya'] }),
    day('2026-10-11', 'S1', 'shukla', {
      observances: ['First Day of Sharad Navratri'],
      non_veg_ok: false,
      school: { is_school_day: false, note: null },
    }),
    day('2026-10-12', 'S2', 'shukla', {
      non_veg_ok: false,
      has_meals: true,
      school_kids: ['mira', 'kabir'],
    }),
    day('2026-10-22', 'S12', 'shukla', { kids: ['kabir'], family: true }),
    day('2026-10-20', 'S10', 'shukla', {
      observances: ['Dussehra'],
      non_veg_ok: false,
    }),
    day('2026-10-23', 'S13', 'shukla', {
      school: { is_school_day: false, note: 'Teacher Work Day' },
    }),
    day('2026-10-25', 'S15', 'shukla', { flags: ['purnima'], non_veg_ok: false }),
  ],
}

export const NAVRATRI_DAY: PanchangDay = {
  date: '2026-10-11',
  sunrise: '2026-10-11T07:13:00-07:00',
  sunset: '2026-10-11T18:33:00-07:00',
  moonrise: '2026-10-11T08:02:00-07:00',
  moonset: '2026-10-11T19:20:00-07:00',
  vaara: 'Ravivara',
  tithi: { name: 'Pratipada', index: 1, ends_at: '2026-10-11T09:01:00-07:00', paksha: 'shukla' },
  nakshatra: { name: 'Chitra', index: 14, ends_at: '2026-10-11T14:30:00-07:00' },
  yoga: { name: 'Vishkambha', index: 1, ends_at: null },
  karana: { name: 'Bava', index: 2, ends_at: null },
  masa: { name: 'Ashwin', adhika: false },
  samvat: { vikram: 2083, shaka: 1948 },
  flags: [],
  observances: [
    { name: 'First Day of Sharad Navratri', kind: 'festival', calendar_id: 'india_holidays' },
  ],
  school: { is_school_day: false, note: null },
  diet: { non_veg_ok: false, reasons: ['Sharad Navratri · day 1 of 10'] },
  meals: { breakfast: 'Kanda poha', lunch: 'Dal and jeera rice', dinner: null },
}
