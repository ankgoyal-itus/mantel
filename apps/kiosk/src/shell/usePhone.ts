import { useEffect, useState } from 'react'

/**
 * Under this, the screen is a phone and the kiosk modes do not belong.
 *
 * Measured on the shorter side, so turning a device over does not change
 * what it is. This was the width, at 900 — which put an iPad held upright,
 * 768 wide, on the phone's side of the line, and the dashboard is laid out
 * for portrait now. The iPads' short side is 768; the largest phone's is
 * under 450 either way up. 600 is well clear of both.
 */
export const PHONE_SHORT_SIDE = 600

/** Whether a screen this size is a phone. */
export function isPhoneSize(width: number, height: number): boolean {
  return Math.min(width, height) < PHONE_SHORT_SIDE
}

function isPhone(): boolean {
  return isPhoneSize(window.innerWidth, window.innerHeight)
}

/** True on a phone-sized screen, re-read on resize and rotation. */
export function usePhone(): boolean {
  const [phone, setPhone] = useState(() => isPhone())

  useEffect(() => {
    const read = () => setPhone(isPhone())
    read()
    window.addEventListener('resize', read)
    window.addEventListener('orientationchange', read)
    return () => {
      window.removeEventListener('resize', read)
      window.removeEventListener('orientationchange', read)
    }
  }, [])

  return phone
}

/** `?parent=1` — the bookmarkable way in, at any width. */
export function parentRequested(search: string): boolean {
  return new URLSearchParams(search).get('parent') === '1'
}
