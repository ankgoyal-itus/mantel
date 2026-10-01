import { describe, expect, it } from 'vitest'

import { isPhoneSize, parentRequested } from './usePhone'

describe('who gets the parent screen instead of the kiosk', () => {
  it('draws the line above every phone and below both iPads, either way up', () => {
    // The iPads, landscape and portrait.
    expect(isPhoneSize(1024, 768)).toBe(false)
    expect(isPhoneSize(768, 1024)).toBe(false)
    // The largest phones, both ways up.
    expect(isPhoneSize(430, 932)).toBe(true)
    expect(isPhoneSize(932, 430)).toBe(true)
  })

  it('opens on the parent screen when the URL asks, at any width', () => {
    expect(parentRequested('?parent=1')).toBe(true)
    expect(parentRequested('?foo=bar&parent=1')).toBe(true)
  })

  it('leaves the kiosk alone otherwise', () => {
    expect(parentRequested('')).toBe(false)
    expect(parentRequested('?parent=0')).toBe(false)
    expect(parentRequested('?parents=1')).toBe(false)
  })
})
