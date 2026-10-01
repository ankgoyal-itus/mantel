import { useEffect } from 'react'

type Sentinel = { release: () => Promise<void> }
type WakeLockApi = { request: (type: 'screen') => Promise<Sentinel> }

/**
 * Keep-awake for the foreground tab. Safari has had this since 16.4 and both
 * iPads run 18.7, so it does hold; it still dies with the tab, which is why
 * Auto-Lock = Never and Guided Access remain the real mechanism.
 */
export function useWakeLock(): void {
  useEffect(() => {
    const api = (navigator as Navigator & { wakeLock?: WakeLockApi }).wakeLock
    if (!api) {
      return
    }

    let released = false
    let sentinel: Sentinel | null = null

    const request = () => {
      api.request('screen').then(
        (lock) => {
          if (released) {
            void lock.release()
          } else {
            sentinel = lock
          }
        },
        () => {
          // Denied (often because the tab is hidden); the next visibility
          // change tries again.
        },
      )
    }

    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        request()
      }
    }

    request()
    document.addEventListener('visibilitychange', onVisible)

    return () => {
      released = true
      document.removeEventListener('visibilitychange', onVisible)
      if (sentinel) {
        void sentinel.release()
      }
    }
  }, [])
}
