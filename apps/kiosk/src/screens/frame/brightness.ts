import { useEffect, useState } from 'react'

/**
 * How bright a photo is under the chip's corner, as relative luminance.
 *
 * The chip's pill carries the contrast, and a frosted pill that reads on a
 * lawn washes out on a white sky. So the top-right of each photo is drawn
 * small into a canvas and its bright end measured — the 90th percentile, not
 * the mean, because one patch of sky behind the numbers is enough to lose
 * them. Anything that cannot be measured counts as bright: the safe answer
 * is the darker pill.
 */

/** Above this, the spec's 0.34 pill no longer gives the time 3:1 and the
    small line 4.5:1, and the chip switches to its deeper pill. */
export const BRIGHT_ABOVE = 0.175

const SAMPLE_W = 64
const SAMPLE_H = 48

function channel(value: number): number {
  const c = value / 255
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
}

/** The 90th-percentile luminance of RGBA pixels. */
export function brightEnd(pixels: ArrayLike<number>): number {
  const levels: number[] = []
  for (let index = 0; index + 3 < pixels.length; index += 4) {
    levels.push(
      0.2126 * channel(pixels[index]) +
        0.7152 * channel(pixels[index + 1]) +
        0.0722 * channel(pixels[index + 2]),
    )
  }
  if (levels.length === 0) {
    return 1
  }
  levels.sort((a, b) => a - b)
  return levels[Math.min(levels.length - 1, Math.floor(levels.length * 0.9))]
}

function measure(url: string): Promise<number> {
  return new Promise((resolve) => {
    const image = new Image()
    image.onload = () => {
      try {
        const canvas = document.createElement('canvas')
        canvas.width = SAMPLE_W
        canvas.height = SAMPLE_H
        const context = canvas.getContext('2d')
        if (!context) {
          resolve(1)
          return
        }
        // The top-right: the last third across, the top quarter down.
        const width = image.naturalWidth || SAMPLE_W
        const height = image.naturalHeight || SAMPLE_H
        context.drawImage(
          image,
          width * (2 / 3),
          0,
          width / 3,
          height / 4,
          0,
          0,
          SAMPLE_W,
          SAMPLE_H,
        )
        resolve(brightEnd(context.getImageData(0, 0, SAMPLE_W, SAMPLE_H).data))
      } catch {
        resolve(1)
      }
    }
    image.onerror = () => resolve(1)
    image.src = url
  })
}

/** Whether the corner under the chip is bright, for this photo. */
export function useBrightCorner(url: string | null, dimmed: boolean): boolean {
  const [level, setLevel] = useState<{ url: string | null; value: number }>({
    url: null,
    value: 1,
  })

  useEffect(() => {
    if (!url) {
      return
    }
    let cancelled = false
    void measure(url).then((value) => {
      if (!cancelled) {
        setLevel({ url, value })
      }
    })
    return () => {
      cancelled = true
    }
  }, [url])

  // Not measured yet counts as bright, until it is.
  const value = level.url === url ? level.value : 1
  // At night the whole photo sits under a sheet of black at 50%, which
  // takes a luminance down to about a fifth.
  return (dimmed ? value * 0.22 : value) > BRIGHT_ABOVE
}
