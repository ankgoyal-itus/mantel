import { useState } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'

import { LiveProvider } from './api/live'
import Diag from './routes/Diag'
import ParentApp from './screens/parent/ParentApp'
import Shell from './shell/Shell'
import { parentRequested, usePhone } from './shell/usePhone'

/**
 * The wall or the pocket.
 *
 * A phone gets the parent screen and none of the kiosk modes; an iPad gets
 * the kiosk. `?parent=1` asks for the parent screen at any width, so the same
 * URL can be a home-screen icon called "Mantel Parents". Either way the PIN is
 * the only thing that opens it.
 */
function Home() {
  const phone = usePhone()
  const { search } = useLocation()
  const [dashboard, setDashboard] = useState(false)

  if ((phone || parentRequested(search)) && !dashboard) {
    return <ParentApp onDashboard={() => setDashboard(true)} />
  }
  return <Shell />
}

export default function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          // One live stream for the wall and the phone alike: what another
          // screen changed, this one refetches within a second.
          <LiveProvider>
            <Home />
          </LiveProvider>
        }
      />
      <Route path="/diag" element={<Diag />} />
    </Routes>
  )
}
