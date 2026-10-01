/**
 * One burst, 900ms, when a parent says yes.
 *
 * This is the only thing in Mantel that exists purely to be enjoyed. Every
 * review of every wall display for children says the same thing about it: the
 * confetti is what the kids talk about, and it is what makes the screen
 * something they walk up to rather than something they are sent to.
 *
 * So it is deliberately small. One burst, never a loop, never on a timer,
 * never for anything a child did by themselves — only for the moment somebody
 * said yes, because being believed is the thing being celebrated. It is drawn
 * on a canvas over one card rather than the screen, so the other child's card
 * does not flicker for something that is not theirs.
 *
 * Reduced motion turns it off entirely rather than shortening it: a person
 * who has asked for less movement has not asked for a faster burst.
 */

export const BURST_MS = 900
export const PARTICLE_COUNT = 80

/** Gravity and drag in canvas units, tuned so a piece falls out of a card. */
const GRAVITY = 1400
const DRAG = 0.86

export type Particle = {
  x: number
  y: number
  vx: number
  vy: number
  spin: number
  turn: number
  colour: string
  size: number
}

/**
 * Whether an approval just happened.
 *
 * A balance that went up is a parent having said yes — to a chore, or to an
 * award. It is the one signal that means the same thing on every screen, and
 * taking it here rather than from each caller is what keeps the burst to one
 * per approval: two screens watching the same number both see one rise.
 *
 * A first sighting is not a rise. Nothing fires on the first paint of the
 * day, which would otherwise greet an empty kitchen every morning.
 */
export function shouldFire(before: number | null, after: number | null): boolean {
  return before !== null && after !== null && after > before
}

/**
 * Where the pieces start and how fast.
 *
 * Thrown upward from the middle of the card in a fan, because a burst that
 * only falls reads as something breaking. `random` is injected so the shape
 * of a burst can be asserted rather than watched.
 */
export function makeParticles(
  width: number,
  height: number,
  colours: readonly string[],
  random: () => number = Math.random,
  count: number = PARTICLE_COUNT,
): Particle[] {
  const made: Particle[] = []
  for (let n = 0; n < count; n += 1) {
    // A fan between 30 and 150 degrees, measured up from the horizontal.
    const angle = (30 + random() * 120) * (Math.PI / 180)
    const speed = 260 + random() * 340
    made.push({
      x: width * (0.3 + random() * 0.4),
      y: height * 0.55,
      vx: Math.cos(angle) * speed * (random() < 0.5 ? -1 : 1),
      vy: -Math.sin(angle) * speed,
      spin: random() * Math.PI * 2,
      turn: (random() - 0.5) * 12,
      colour: colours[n % colours.length],
      size: 5 + random() * 6,
    })
  }
  return made
}

/** One frame. `seconds` is the step, not the elapsed time. */
export function advance(particle: Particle, seconds: number): Particle {
  const vx = particle.vx * DRAG ** (seconds * 60)
  const vy = particle.vy * DRAG ** (seconds * 60) + GRAVITY * seconds
  return {
    ...particle,
    x: particle.x + vx * seconds,
    y: particle.y + vy * seconds,
    vx,
    vy,
    spin: particle.spin + particle.turn * seconds,
  }
}

/** Fading out over the last third, so nothing vanishes mid-air. */
export function alphaAt(elapsed: number): number {
  const fadeFrom = BURST_MS * 0.66
  if (elapsed <= fadeFrom) {
    return 1
  }
  return Math.max(0, 1 - (elapsed - fadeFrom) / (BURST_MS - fadeFrom))
}
