import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import ParentPill from './ParentPill'

const noop = () => {}

describe('the parents pill', () => {
  it('says what it is and carries no badge when nothing waits', () => {
    const html = renderToStaticMarkup(<ParentPill onOpen={noop} onDone={noop} />)

    expect(html).toContain('Parents')
    expect(html).not.toContain('parents-badge')
  })

  it('carries the count when approvals are waiting', () => {
    const html = renderToStaticMarkup(<ParentPill pending={3} onOpen={noop} onDone={noop} />)

    expect(html).toContain('parents-badge')
    expect(html).toContain('>3<')
  })

  it('turns into the session and its way out', () => {
    const html = renderToStaticMarkup(
      <ParentPill session pending={2} onOpen={noop} onDone={noop} />,
    )

    expect(html).toContain('Parent mode')
    expect(html).toContain('Done')
    // The count belongs on the way in, not on a screen already open.
    expect(html).not.toContain('parents-badge')
  })

  it('is a button, so a tap has somewhere to land', () => {
    expect(renderToStaticMarkup(<ParentPill onOpen={noop} onDone={noop} />)).toContain(
      '<button type="button"',
    )
  })
})
