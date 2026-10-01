/** The kiosk talks only to the API, always through here. */

const TIMEOUT_MS = 8000

export async function getJson<T>(path: string): Promise<T> {
  // A poll that never returns would freeze the chip on a stale time, so it is
  // cut off well before Safari's own much longer timeout.
  const controller = typeof AbortController === 'function' ? new AbortController() : null
  const timer = controller ? window.setTimeout(() => controller.abort(), TIMEOUT_MS) : null
  try {
    const response = await fetch(path, {
      signal: controller ? controller.signal : undefined,
      cache: 'no-store',
    })
    if (!response.ok) {
      throw new Error(`${path} returned ${response.status}`)
    }
    return (await response.json()) as T
  } finally {
    if (timer !== null) {
      window.clearTimeout(timer)
    }
  }
}
