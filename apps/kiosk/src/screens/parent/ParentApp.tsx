import { useEffect, useState } from 'react'

import { signOut } from '../../api/parent'
import { useMantelData } from '../../api/useMantelData'
import { usePending } from '../../api/usePoints'
import { underlyingAt } from '../../mode/machine'
import { toModeSettings } from '../../shell/useMode'
import { useParentSession } from '../../shell/useParentSession'
import { useTheme } from '../../shell/useTheme'
import ParentScreen from './ParentScreen'
import PinPad from './PinPad'

/**
 * Mantel on a phone: the parent screen, and nothing else.
 *
 * A phone in a pocket is not a wall display. None of the kiosk modes make
 * sense there — no idle timer, no photo frame, no night screen — and the one
 * thing a parent wants from a phone is the thing the iPad makes them walk
 * over for. So the small screen opens on the PIN pad and lands on the tabs.
 *
 * `?parent=1` does the same at any width, which is what makes it a
 * bookmarkable home-screen icon rather than a width accident.
 */
export default function ParentApp({ onDashboard }: { onDashboard: () => void }) {
  const data = useMantelData()
  const [nonce, setNonce] = useState(0)
  const pending = usePending(nonce)
  const parent = useParentSession()
  const [entered, setEntered] = useState(false)

  const kids = data.config?.family.kids ?? []
  const open = parent.open || entered

  // Paper by day and the dark after hours, the same hours as the wall: the
  // phone is the same app, and a white screen at eleven at night is not.
  const settings = data.config?.settings ?? null
  const [hour, setHour] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setHour(Date.now()), 60000)
    return () => window.clearInterval(timer)
  }, [])
  useTheme(data.config, underlyingAt(hour, toModeSettings(settings)))

  if (!open) {
    return (
      <div className="parent-app">
        <PinPad
          pending={pending}
          onOpen={() => {
            setEntered(true)
            parent.refresh()
          }}
          // Cancelling on a phone is the way to the dashboard, not a way out
          // of the app: there is nothing else here.
          onCancel={onDashboard}
        />
      </div>
    )
  }

  return (
    <div className="parent-app">
      <ParentScreen
        kids={kids}
        parents={data.config?.family.parents ?? []}
        pending={pending}
        idleMinutes={settings?.points?.parent_idle_minutes}
        onDone={() => {
          void signOut().then(() => parent.refresh())
          setEntered(false)
          setNonce((count) => count + 1)
        }}
        onDashboard={onDashboard}
      />
    </div>
  )
}
