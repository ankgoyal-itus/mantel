/** A Tuesday with something in every corner of the layout. Tests only. */

import type { AgendaEntry, Day, MealSlot, TaskEntry, Weather } from '../../api/types'

function entry(partial: Partial<AgendaEntry> & { title: string }): AgendaEntry {
  return {
    start: null,
    end: null,
    where: null,
    note: null,
    source: 'schedule',
    source_kind: null,
    all_day: false,
    calendar_id: null,
    ...partial,
  }
}

export const WEATHER: Weather = {
  now: { temp: 68, label: 'Partly cloudy', icon: 'partly', is_day: true },
  today: {
    high: 79,
    low: 56,
    precip_pct: 40,
    sunrise: '2026-09-29T06:59',
    sunset: '2026-09-29T18:55',
    label: 'Rain',
    icon: 'rain',
  },
  tomorrow: {
    high: 74,
    low: 52,
    precip_pct: 10,
    sunrise: '2026-09-30T07:00',
    sunset: '2026-09-30T18:53',
    label: 'Clear',
    icon: 'clear',
  },
  stale: false,
  fetched_at: '2026-09-29T07:00:00-07:00',
}

/** A meal slot as the API sends it. A parent's plan unless a test says so. */
export function meal(
  name: string,
  extra: Partial<MealSlot> = {},
): MealSlot {
  return {
    name,
    note: null,
    kids_protein: 'veg',
    id: null,
    picked_by: [],
    confirmed: true,
    ...extra,
  }
}

/** A to-do row as the API sends it. Untouched today unless a test says so. */
export function task(
  id: string,
  title: string,
  extra: Partial<TaskEntry> = {},
): TaskEntry {
  return {
    id,
    title,
    claim: 'kid',
    status: 'none',
    points: 10,
    routine: 'afternoon',
    claim_id: null,
    ...extra,
  }
}

export const TODAY: Day = {
  date: '2026-09-29',
  weekday: 'tue',
  is_school_day: true,
  school_note: null,
  kids: [
    {
      id: 'mira',
      name: 'Mira',
      color: '#1F8A8A',
      avatar: 'fox',
      birthday: false,
      agenda: [
        entry({ title: 'Picture day', all_day: true, source: 'calendar', calendar_id: 'mira' }),
        entry({ title: 'Assembly', start: '09:00', end: '10:00', where: 'Gym' }),
        entry({
          title: 'Piano',
          start: '16:00',
          end: '16:45',
          where: "Ms. Lee's",
          note: 'bring the blue book',
        }),
      ],
      tasks: [
        task('hw', 'Homework'),
        task('outside', '30 min outside'),
        task('room', 'Tidy room'),
      ],
    },
    {
      id: 'kabir',
      name: 'Kabir',
      color: '#D97706',
      avatar: 'panda',
      birthday: false,
      agenda: [],
      tasks: [
        task('hw', 'Homework'),
        task('outside', '30 min outside'),
      ],
    },
  ],
  family_agenda: [entry({ title: 'Dinner with grandparents', start: '18:30', end: '19:30' })],
  observances: [],
  diet: { non_veg_ok: true, reasons: [] },
  meals: {
    breakfast: meal('Oatmeal with fruit'),
    lunch: meal('Quesadilla', { note: 'Mira: no tomato' }),
    dinner: meal('Paneer tikka', { note: 'chicken tikka for the kids', kids_protein: 'chicken' }),
    snack: null,
  },
  weather: WEATHER,
}

export const TOMORROW: Day = {
  date: '2026-09-30',
  weekday: 'wed',
  is_school_day: false,
  school_note: null,
  kids: [
    {
      id: 'mira',
      name: 'Mira',
      color: '#1F8A8A',
      avatar: 'fox',
      birthday: false,
      agenda: [entry({ title: 'Dentist', start: '10:30', end: '11:15' })],
      tasks: [],
    },
    {
      id: 'kabir',
      name: 'Kabir',
      color: '#D97706',
      avatar: 'panda',
      birthday: false,
      agenda: [entry({ title: 'Swim', start: '17:00', end: '18:00', where: 'Aquatic center' })],
      tasks: [],
    },
  ],
  family_agenda: [entry({ title: 'Library', start: '10:30', end: '11:30' })],
  observances: [
    { name: 'Diwali/Deepavali', kind: 'festival', calendar_id: 'india_holidays' },
  ],
  diet: { non_veg_ok: false, reasons: ['Diwali/Deepavali · day 1 of 4'] },
  meals: {
    breakfast: meal('Pancakes'),
    lunch: meal('Dal and rice', { note: 'lunchbox' }),
    dinner: null,
    snack: null,
  },
  weather: WEATHER,
}

/** A district feed's long titles, for layout tests. */
export const LONG_DAY: Day = {
  ...TODAY,
  kids: [
    {
      ...TODAY.kids[0],
      agenda: [
        entry({
          title: 'Cross Country meet @ Bayside Middle',
          start: '15:00',
          end: '17:00',
          source: 'school',
          source_kind: 'school',
          calendar_id: 'bayside',
        }),
        entry({
          title: '6th Grade Girls Volleyball @ NMS',
          start: '16:30',
          end: '18:00',
          source: 'school',
          source_kind: 'school',
          calendar_id: 'bayside',
        }),
        entry({
          title: 'Piano',
          start: '16:00',
          end: '16:45',
          where: "Ms. Lee's",
          note: 'bring the blue book',
        }),
      ],
      tasks: [task('hw', 'Homework')],
    },
    {
      ...TODAY.kids[1],
      agenda: [
        entry({
          title: 'League Cross Country meet @ Bayside Middle',
          start: '15:00',
          end: '17:00',
          source: 'school',
          source_kind: 'school',
          calendar_id: 'bayside',
        }),
        entry({ title: 'Science Olympiad', all_day: true, source: 'school', source_kind: 'school' }),
      ],
      tasks: [],
    },
  ],
  meals: {
    breakfast: meal('Idli and sambar'),
    lunch: meal('Pesto pasta', { note: 'Lunchbox' }),
    dinner: meal('Khichdi'),
    snack: null,
  },
}
