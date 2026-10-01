import { describe, expect, it } from 'vitest'

import { qrPath } from './QrCode'

describe('the QR code for the second iPad', () => {
  it('encodes a LAN URL as a square grid of modules', () => {
    const code = qrPath('http://10.0.0.20:8000/')
    // Version 2 or so: 25 modules a side, and a good share of them dark.
    expect(code.size).toBeGreaterThanOrEqual(21)
    expect(code.path.split('h1v1').length - 1).toBeGreaterThan(100)
  })
})
