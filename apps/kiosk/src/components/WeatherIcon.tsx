/** The eight weather keys the API emits, drawn inline. No icon fonts. */

const SUN = <circle cx="12" cy="12" r="5" />
const RAYS = (
  <g strokeLinecap="round">
    <line x1="12" y1="1" x2="12" y2="3.5" />
    <line x1="12" y1="20.5" x2="12" y2="23" />
    <line x1="1" y1="12" x2="3.5" y2="12" />
    <line x1="20.5" y1="12" x2="23" y2="12" />
    <line x1="4.2" y1="4.2" x2="6" y2="6" />
    <line x1="18" y1="18" x2="19.8" y2="19.8" />
    <line x1="19.8" y1="4.2" x2="18" y2="6" />
    <line x1="6" y1="18" x2="4.2" y2="19.8" />
  </g>
)
const CLOUD = <path d="M7 19h10a4 4 0 0 0 0-8 6 6 0 0 0-11.6-1.4A3.6 3.6 0 0 0 7 19z" />
const MOON = <path d="M20.5 15.3A8.6 8.6 0 0 1 9.2 4a8.6 8.6 0 1 0 11.3 11.3z" />

function drops(count: number) {
  const xs = count === 3 ? [8, 12, 16] : [9, 15]
  return (
    <g strokeLinecap="round">
      {xs.map((x) => (
        <line key={x} x1={x} y1="19.5" x2={x - 1.5} y2="23" />
      ))}
    </g>
  )
}

const SHAPES: Record<string, React.ReactNode> = {
  clear: (
    <>
      {SUN}
      {RAYS}
    </>
  ),
  partly: (
    <>
      <circle cx="9" cy="8.5" r="3.6" />
      <path d="M8 20h9a3.6 3.6 0 0 0 0-7.2 5.4 5.4 0 0 0-10.3-1.1A3.2 3.2 0 0 0 8 20z" />
    </>
  ),
  clear_night: MOON,
  partly_night: (
    <>
      <path d="M17.6 10.4A6.2 6.2 0 0 1 9.4 2.3a6.2 6.2 0 1 0 8.2 8.1z" />
      <path d="M8 20h9a3.6 3.6 0 0 0 0-7.2 5.4 5.4 0 0 0-8.6-2.6A3.2 3.2 0 0 0 8 20z" />
    </>
  ),
  cloudy: CLOUD,
  fog: (
    <>
      <path d="M7 15h10a4 4 0 0 0 0-8 6 6 0 0 0-11.6-1.4A3.6 3.6 0 0 0 7 15z" />
      <g strokeLinecap="round">
        <line x1="4" y1="19" x2="20" y2="19" />
        <line x1="6" y1="22.5" x2="18" y2="22.5" />
      </g>
    </>
  ),
  drizzle: (
    <>
      <path d="M7 16h10a4 4 0 0 0 0-8 6 6 0 0 0-11.6-1.4A3.6 3.6 0 0 0 7 16z" />
      {drops(2)}
    </>
  ),
  rain: (
    <>
      <path d="M7 16h10a4 4 0 0 0 0-8 6 6 0 0 0-11.6-1.4A3.6 3.6 0 0 0 7 16z" />
      {drops(3)}
    </>
  ),
  snow: (
    <>
      <path d="M7 16h10a4 4 0 0 0 0-8 6 6 0 0 0-11.6-1.4A3.6 3.6 0 0 0 7 16z" />
      <g strokeLinecap="round">
        <line x1="8" y1="20" x2="8" y2="23" />
        <line x1="6.5" y1="21.5" x2="9.5" y2="21.5" />
        <line x1="16" y1="20" x2="16" y2="23" />
        <line x1="14.5" y1="21.5" x2="17.5" y2="21.5" />
      </g>
    </>
  ),
  storm: (
    <>
      <path d="M7 15h10a4 4 0 0 0 0-8 6 6 0 0 0-11.6-1.4A3.6 3.6 0 0 0 7 15z" />
      <path d="M13 17l-3.5 4h3l-1.5 4" strokeLinejoin="round" />
    </>
  ),
}

export default function WeatherIcon({
  icon,
  size = 44,
  night = false,
}: {
  icon: string
  size?: number
  night?: boolean
}) {
  // A sun after dark reads as broken. Only clear and partly have a night face;
  // rain looks the same at midnight.
  const key = night && (icon === 'clear' || icon === 'partly') ? `${icon}_night` : icon
  const shape = SHAPES[key] ?? SHAPES.cloudy
  return (
    <svg
      className="wx-icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      aria-hidden="true"
      focusable="false"
    >
      {shape}
    </svg>
  )
}
