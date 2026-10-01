import { useCallback } from 'react'

import { type SignIn, signIn } from '../../api/parent'
import Icon from '../../components/icons/Icon'
import Keypad, { type KeypadResult } from '../../components/Keypad'
import { copy } from '../../copy'

function message(result: SignIn): string {
  if (result.ok) {
    return ''
  }
  switch (result.reason) {
    case 'wrong':
      return copy.parent.tryAgain(result.remaining)
    case 'locked':
      return copy.parent.lockedFor(result.retryAfter)
    case 'unconfigured':
      return copy.parent.noPinSet
    case 'offline':
      return copy.parent.apiSilent
  }
}

/** The parent's keypad: the lock, "Parents only", and the API's session. */
export default function PinPad({
  onOpen,
  onCancel,
  pending = 0,
}: {
  onOpen: () => void
  onCancel: () => void
  /** Said here because this pad is only ever opened by a parent. */
  pending?: number
}) {
  const submit = useCallback(async (pin: string): Promise<KeypadResult> => {
    const result = await signIn(pin)
    if (result.ok) {
      return { ok: true }
    }
    return {
      ok: false,
      message: message(result),
      lockedFor: result.reason === 'locked' ? result.retryAfter : undefined,
    }
  }, [])

  return (
    <Keypad
      variant="parent"
      title={
        <>
          <Icon name="lock" size={20} className="pin-lock" />
          {copy.parent.title}
        </>
      }
      caption={copy.parent.enterPin}
      submit={submit}
      onOpen={onOpen}
      onCancel={onCancel}
      note={
        pending > 0 ? <p className="pin-waiting">{copy.parent.thingsWaiting(pending)}</p> : null
      }
    />
  )
}
