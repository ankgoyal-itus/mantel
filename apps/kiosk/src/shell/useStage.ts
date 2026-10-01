import { useEffect, useState } from 'react'

export type Stage = { width: number; height: number; portrait: boolean }

function measure(): Stage {
  // Old Safari lies about 100vh, so the stage is sized in pixels instead.
  const width = window.innerWidth
  const height = window.innerHeight
  return { width, height, portrait: height > width }
}

export function useStage(): Stage {
  const [stage, setStage] = useState<Stage>(() => measure())

  useEffect(() => {
    const read = () => setStage(measure())
    read()
    window.addEventListener('resize', read)
    window.addEventListener('orientationchange', read)
    return () => {
      window.removeEventListener('resize', read)
      window.removeEventListener('orientationchange', read)
    }
  }, [])

  return stage
}
