import { useEffect } from 'react'

import type { Config } from '../api/types'
import type { Underlying } from '../mode/machine'
import { kidPaletteCss } from './kidPalette'

/** The one <style> element the children's colours are written into. */
const PALETTE_ID = 'kid-palette'

/**
 * Flips the night palette, and writes each child's colours as CSS.
 *
 * The children come from /api/config, so their variables are written here as
 * a small stylesheet (kidPalette.ts) rather than living in theme.css. What it
 * writes does not depend on which palette is up: the day forms and the night
 * forms are both rules, keyed on the attribute set below, so the colours are
 * right the instant the attribute changes rather than a render behind it.
 */
export function useTheme(config: Config | null, underlying: Underlying): void {
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', underlying === 'NIGHT' ? 'night' : 'day')
  }, [underlying])

  useEffect(() => {
    if (!config) {
      return
    }
    let sheet = document.getElementById(PALETTE_ID)
    if (!sheet) {
      sheet = document.createElement('style')
      sheet.id = PALETTE_ID
      document.head.appendChild(sheet)
    }
    sheet.textContent = kidPaletteCss(config.family.kids)
  }, [config])
}
