import { useEffect, useRef } from 'react'

import { BURST_MS, advance, alphaAt, makeParticles } from '../confetti'

/**
 * The burst, over one card.
 *
 * Absolutely positioned and pointer-transparent, so it covers the card it
 * belongs to without taking a tap from anything underneath. It draws nothing
 * until `fire` changes, and nothing at all for a viewer who has asked for
 * reduced motion — off, not shortened: somebody who wants less movement has
 * not asked for a faster burst.
 *
 * The canvas is sized in the effect rather than from a layout read during
 * render, which is what this project's lint rules exist to stop.
 */
export default function Confetti({
  fire,
  tokens,
}: {
  /** A counter. Any change from the last one it saw starts a burst. */
  fire: number
  /** CSS custom properties to paint with, resolved against this card. */
  tokens: readonly string[]
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const seen = useRef(fire)

  useEffect(() => {
    if (fire === seen.current) {
      return
    }
    seen.current = fire

    const canvas = canvasRef.current
    if (!canvas || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return
    }
    const box = canvas.parentElement?.getBoundingClientRect()
    if (!box || box.width === 0) {
      return
    }
    const ratio = window.devicePixelRatio || 1
    canvas.width = Math.round(box.width * ratio)
    canvas.height = Math.round(box.height * ratio)
    const context = canvas.getContext('2d')
    if (!context) {
      return
    }
    context.scale(ratio, ratio)

    // A canvas cannot be handed a var(), so the card's own tokens are read
    // off the element here — which also means the burst follows the theme.
    const style = getComputedStyle(canvas.parentElement as Element)
    const colours = tokens
      .map((token) => style.getPropertyValue(token).trim())
      .filter((colour) => colour.length > 0)
    if (colours.length === 0) {
      return
    }

    let pieces = makeParticles(box.width, box.height, colours)
    const started = performance.now()
    let last = started
    let frame = 0

    const draw = (at: number) => {
      const elapsed = at - started
      if (elapsed >= BURST_MS) {
        context.clearRect(0, 0, box.width, box.height)
        return
      }
      const step = Math.min(0.05, (at - last) / 1000)
      last = at
      pieces = pieces.map((piece) => advance(piece, step))

      context.clearRect(0, 0, box.width, box.height)
      context.globalAlpha = alphaAt(elapsed)
      for (const piece of pieces) {
        context.save()
        context.translate(piece.x, piece.y)
        context.rotate(piece.spin)
        context.fillStyle = piece.colour
        context.fillRect(-piece.size / 2, -piece.size / 4, piece.size, piece.size / 2)
        context.restore()
      }
      context.globalAlpha = 1
      frame = window.requestAnimationFrame(draw)
    }

    frame = window.requestAnimationFrame(draw)
    return () => {
      window.cancelAnimationFrame(frame)
      context.clearRect(0, 0, box.width, box.height)
    }
  }, [fire, tokens])

  return <canvas ref={canvasRef} className="confetti" aria-hidden="true" />
}
