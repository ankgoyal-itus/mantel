/**
 * The whole icon set: rounded line work at 1.75px, drawn on a 24 grid.
 *
 * Bundled as components rather than files because nothing here may reach a
 * CDN and an icon font would be a second typeface to load. No emoji appears
 * anywhere in the UI — they render differently on every iPad and cannot take
 * a colour token.
 */

export type IconName =
  | 'sun'
  | 'moon'
  | 'cloud'
  | 'partly'
  | 'fog'
  | 'drizzle'
  | 'rain'
  | 'snow'
  | 'storm'
  | 'school'
  | 'leaf'
  | 'lock'
  | 'clock'
  | 'calendar'
  | 'camera'
  | 'meal'
  | 'flame'
  | 'ice-cream'
  | 'cake'
  | 'cup'
  | 'dinner'
  | 'coin'
  | 'jar'
  | 'family'
  | 'storefront'
  | 'house'
  | 'frame'
  | 'game'
  | 'star'
  | 'check'
  | 'gear'
  | 'info'
  | 'chevron-left'
  | 'chevron-right'
  | 'plus'
  | 'minus'
  | 'close'
  | 'refresh'
  | 'pen'

const PATHS: Record<IconName, string> = {
  sun: 'M12 4.5v-2M12 21.5v-2M4.5 12h-2M21.5 12h-2M6.7 6.7 5.3 5.3M18.7 18.7l-1.4-1.4M6.7 17.3l-1.4 1.4M18.7 5.3l-1.4 1.4M12 7.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9Z',
  moon: 'M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5Z',
  cloud: 'M7.5 19h9.5a4 4 0 0 0 .4-8 6 6 0 0 0-11.6 1.6A3.7 3.7 0 0 0 7.5 19Z',
  partly: 'M17 5.5V4M21 9h1.5M19.6 6.4 20.7 5.3M14.4 6.4 13.3 5.3M17 6.5a2.5 2.5 0 0 1 2.4 3.2M6.5 19.5h9a3.75 3.75 0 0 0 .4-7.5 5.6 5.6 0 0 0-10.9 1.5 3.5 3.5 0 0 0 1 6Z',
  fog: 'M7 15.5h9.5a3.6 3.6 0 0 0 .4-7.2 5.5 5.5 0 0 0-10.7 1.5A3.4 3.4 0 0 0 7 15.5ZM4 19h16M7 22h10',
  drizzle: 'M7.5 15h9.5a3.8 3.8 0 0 0 .4-7.6 5.7 5.7 0 0 0-11 1.5A3.5 3.5 0 0 0 7.5 15ZM9 18.5l-1 2M14 18.5l-1 2M19 18.5l-1 2',
  rain: 'M7.5 14.5H17a3.8 3.8 0 0 0 .4-7.6 5.7 5.7 0 0 0-11 1.5 3.5 3.5 0 0 0 1.1 6.1ZM8.5 17.5l-1.5 4M13 17.5l-1.5 4M17.5 17.5l-1.5 4',
  snow: 'M7.5 14.5H17a3.8 3.8 0 0 0 .4-7.6 5.7 5.7 0 0 0-11 1.5 3.5 3.5 0 0 0 1.1 6.1ZM8.5 19h.01M12 21h.01M15.5 19h.01M12 17.5h.01',
  storm: 'M7.5 14.5H17a3.8 3.8 0 0 0 .4-7.6 5.7 5.7 0 0 0-11 1.5 3.5 3.5 0 0 0 1.1 6.1ZM13 16.5l-3 4h4l-3 4',
  school: 'M12 3.5 2.5 9 12 14.5 21.5 9 12 3.5ZM6 11v6.5c0 1.5 2.7 3 6 3s6-1.5 6-3V11M21.5 9v5',
  leaf: 'M20 4c0 9-5.5 13.5-11.5 13.5C8.5 8.5 14 4 20 4ZM6 20c1.5-4 4.5-7.5 8.5-9.5',
  clock: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 7.6V12l2.9 1.7',
  calendar: 'M5 6.5h14A1.5 1.5 0 0 1 20.5 8v11A1.5 1.5 0 0 1 19 20.5H5A1.5 1.5 0 0 1 3.5 19V8A1.5 1.5 0 0 1 5 6.5ZM8 3.5v5M16 3.5v5M3.5 12h17',
  lock: 'M6.5 10.5h11a1.5 1.5 0 0 1 1.5 1.5v7a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 5 19v-7a1.5 1.5 0 0 1 1.5-1.5ZM8.5 10.5V7a3.5 3.5 0 1 1 7 0v3.5M12 14.5v2.5',
  camera: 'M4.5 7.5h3l1.5-2.5h6l1.5 2.5h3A1.5 1.5 0 0 1 21 9v9a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18V9a1.5 1.5 0 0 1 1.5-1.5ZM12 16.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z',
  meal: 'M6 3.5v8a2.5 2.5 0 0 0 5 0v-8M8.5 11.5v9M6 3.5v5M11 3.5v5M17.5 3.5c-2 0-3 3-3 6s1 3.5 3 3.5v7.5',
  flame: 'M12 3s5 4.5 5 9a5 5 0 0 1-10 0c0-1.7.8-3 1.5-4 .3 1.2 1 2 2 2 .8 0 1.3-.7 1.3-1.7C11.8 6.5 12 4.5 12 3Z',
  'ice-cream': 'M8 11h8l-4 9.5L8 11ZM9 11a3 3 0 0 1 6 0M10.3 8.3a2.6 2.6 0 0 1 3.4 0',
  cake: 'M4.5 20.5h15v-6a2 2 0 0 0-2-2h-11a2 2 0 0 0-2 2v6ZM4.5 16.6c1.5 0 1.5 1.4 3 1.4s1.5-1.4 3-1.4 1.5 1.4 3 1.4 1.5-1.4 3-1.4M12 12.5V9.5M12 6.5V5',
  cup: 'M6.5 8.5h11l-1 11a2 2 0 0 1-2 1.8h-5a2 2 0 0 1-2-1.8l-1-11ZM5.5 8.5h13M9.8 5.5l.6-2h3.2l.6 2',
  dinner: 'M12 4.5a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15ZM12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7',
  coin: 'M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17ZM12 7.5v9M14.5 9.8c0-1.3-1.1-2.3-2.5-2.3s-2.5 1-2.5 2.3 1.1 1.9 2.5 2.2 2.5.9 2.5 2.2-1.1 2.3-2.5 2.3-2.5-1-2.5-2.3',
  // A small house: the family, at home, with nothing on.
  house: 'M4 11.5 12 5l8 6.5M6 10v9.5h12V10M10 19.5v-5h4v5',
  // A picture frame: the photos, before there are any.
  frame: 'M4.5 5h15v14h-15ZM7.5 16l3.5-4.5 2.5 3 1.5-2 2.5 3.5M15.5 9.5h.01',
  // A shop front with its awning: a meal eaten out.
  storefront: 'M4 9.5 5.5 4h13L20 9.5M4 9.5a2.7 2.7 0 0 0 5.3 0 2.7 2.7 0 0 0 5.4 0 2.7 2.7 0 0 0 5.3 0M5.5 11.5V20h13v-8.5M10 20v-5h4v5',
  // The family: two heads and shoulders, for a row that is everybody's.
  family: 'M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM16.5 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM2.5 20a5.5 5.5 0 0 1 11 0M11 20a5.5 5.5 0 0 1 11 0',
  // The family jar: a lid, and a body with a line of what is in it.
  jar: 'M8 3.5h8v3H8ZM7 6.5h10a1 1 0 0 1 1 1V18a2.5 2.5 0 0 1-2.5 2.5h-7A2.5 2.5 0 0 1 6 18V7.5a1 1 0 0 1 1-1ZM6 12.5h12',
  game: 'M8.5 9.5h7a5 5 0 0 1 4.9 6l-.4 2.2a2.2 2.2 0 0 1-4 1L14 16.5h-4l-2 2.2a2.2 2.2 0 0 1-4-1l-.4-2.2a5 5 0 0 1 4.9-6ZM7.5 12v2.5M6.25 13.25h2.5M15.5 12.5h.01M17.5 14.5h.01',
  star: 'M12 3.8l2.6 5.3 5.9.9-4.2 4.1 1 5.8L12 17.1l-5.3 2.8 1-5.8-4.2-4.1 5.9-.9L12 3.8Z',
  // The parent screen's own: a settings app needs a handful a wall does not.
  check: 'M4.5 12.5l5 5 10-11',
  gear: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1',
  info: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 11v5.5M12 7.5h.01',
  'chevron-left': 'M14.5 5.5 8 12l6.5 6.5',
  'chevron-right': 'M9.5 5.5 16 12l-6.5 6.5',
  plus: 'M12 5v14M5 12h14',
  minus: 'M5 12h14',
  close: 'M6 6l12 12M18 6 6 18',
  refresh: 'M19.5 8.5A8 8 0 0 0 5 7.2M4.5 15.5A8 8 0 0 0 19 16.8M19.5 3.5v5h-5M4.5 20.5v-5h5',
  pen: 'M4 20h4L19.5 8.5a2.1 2.1 0 0 0-3-3L5 17v3ZM14.5 7.5l2 2',
}

/**
 * Every name there is a path for.
 *
 * rewards.yaml names a glyph per reward, and a file the family edits can name
 * one that does not exist. Checking against this turns that into a star
 * rather than a blank space.
 */
export const ICONS: readonly IconName[] = Object.keys(PATHS) as IconName[]

export default function Icon({
  name,
  size = 24,
  className,
}: {
  name: IconName
  size?: number
  className?: string
}) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {/* 1.75px at every size: the one line the whole app is drawn in. */}
      <path d={PATHS[name]} vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

/** The weather code the API sends, as an icon name. */
export function weatherIcon(icon: string, night: boolean): IconName {
  if (icon === 'clear') {
    return night ? 'moon' : 'sun'
  }
  const known: IconName[] = ['cloud', 'partly', 'fog', 'drizzle', 'rain', 'snow', 'storm']
  return known.includes(icon as IconName) ? (icon as IconName) : 'cloud'
}
