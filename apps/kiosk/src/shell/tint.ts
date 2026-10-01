/**
 * A kid's colour as a background a word can sit on.
 *
 * Eight per cent over white. Enough that the two children's pills are
 * distinguishable across the kitchen, little enough that the page's own ink
 * still clears AA on top of it — which is the whole reason the tints exist
 * rather than filling a pill with the colour and writing on it in white.
 *
 * Computed here rather than with color-mix so the value can be asserted in a
 * test: the design suite can only tell us a rendered pair fails, not which of
 * the two ends moved.
 */
const MIX = 0.08

function channels(colour: string): [number, number, number] | null {
  const hex = colour.trim().replace(/^#/, '')
  const full =
    hex.length === 3
      ? hex
          .split('')
          .map((one) => one + one)
          .join('')
      : hex
  if (!/^[0-9a-fA-F]{6}$/.test(full)) {
    return null
  }
  return [
    parseInt(full.slice(0, 2), 16),
    parseInt(full.slice(2, 4), 16),
    parseInt(full.slice(4, 6), 16),
  ]
}

/** "#3D6BFF" -> "#eff3ff". Null when the colour is not a hex we can read. */
export function tintOverWhite(colour: string, mix: number = MIX): string | null {
  const rgb = channels(colour)
  if (!rgb) {
    return null
  }
  return hex(rgb.map((value) => 255 + mix * (value - 255)))
}

function hex(rgb: number[]): string {
  return `#${rgb
    .map((value) => Math.min(255, Math.max(0, Math.round(value))))
    .map((value) => value.toString(16).padStart(2, '0'))
    .join('')}`
}

function luminance([red, green, blue]: [number, number, number]): number {
  const channel = (value: number) => {
    const scaled = value / 255
    return scaled <= 0.03928 ? scaled / 12.92 : ((scaled + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue)
}

/** WCAG contrast between two channel triples. */
function ratio(a: [number, number, number], b: [number, number, number]): number {
  const light = Math.max(luminance(a), luminance(b))
  const dark = Math.min(luminance(a), luminance(b))
  return (light + 0.05) / (dark + 0.05)
}

/** The page's own ink, which is what every colour is darkened towards. */
const INK: [number, number, number] = [0x1d, 0x24, 0x33]
/**
 * The page, not the card. --bg is a shade under --card, so a colour that
 * clears AA on white can still fail on the wall behind the cards — school
 * green lands at 4.64 on white and 4.44 on the page. Measuring against the
 * darker of the two is the only way both hold.
 */
const PAPER: [number, number, number] = [0xfb, 0xfa, 0xf7]
const AA = 4.5

/**
 * A kid's colour, dark enough to write with on a white card.
 *
 * Their colour is chosen to be found across a room, which is the opposite of
 * what a colour needs to be read in: an orange like #FF6A45 is 2.84:1 on
 * white, so a child's own name on their own card would fail the contrast rule this project
 * holds itself to. Mixing towards the page's ink rather than towards black
 * keeps the result in the same family as everything else on the page, and it
 * stops as soon as it clears AA, so the darkening is the least that works.
 *
 * Identity is not lost: the card's accent, the avatar disc, the dot and the
 * claimed fill all still use the colour itself. Only the letters move.
 */
export function readableInk(
  colour: string,
  target: number = AA,
  /** What the word sits on, when it is not the page: a chip's tint. */
  on?: string,
): string | null {
  const rgb = channels(colour)
  const ground = on === undefined ? PAPER : channels(on)
  if (!rgb || !ground) {
    return null
  }
  if (ratio(rgb, ground) >= target) {
    return hex(rgb)
  }
  const at = (mix: number): [number, number, number] =>
    rgb.map((value, index) => value + mix * (INK[index] - value)) as [number, number, number]

  // Twelve steps resolve to under half a per cent of the mix, which is finer
  // than a hex channel can hold anyway.
  let low = 0
  let high = 1
  for (let step = 0; step < 12; step += 1) {
    const mid = (low + high) / 2
    if (ratio(at(mid), ground) >= target) {
      high = mid
    } else {
      low = mid
    }
  }
  // The search works in floats and the answer is a hex, and rounding to a
  // channel can give back the tenth of a ratio point the search just won.
  // #FF6A45 lands at 4.489 that way. So the mix is nudged on until the
  // colour that actually ships clears the bar.
  for (let mix = high; mix <= 1; mix += 0.004) {
    const settled = hex(at(mix))
    if (ratio(channels(settled) as [number, number, number], ground) >= target) {
      return settled
    }
  }
  return hex(INK)
}
