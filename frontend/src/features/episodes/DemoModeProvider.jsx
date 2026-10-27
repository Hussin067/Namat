import { useCallback, useMemo, useState } from 'react'
import { createDemoEpisodes } from './demoData.js'
import { DEMO_MODE_SUPPORTED, DemoModeContext } from './demo-context.js'

/**
 * Holds the demo preview in memory for the current session only. It's mounted
 * inside the signed-in area, so it resets on logout and never mixes with real data.
 */
export function DemoModeProvider({ children }) {
  const [enabled, setEnabledState] = useState(false)
  const [episodes, setEpisodes] = useState(() => (DEMO_MODE_SUPPORTED ? createDemoEpisodes() : []))

  const setEnabled = useCallback((next) => setEnabledState(DEMO_MODE_SUPPORTED && next), [])

  const addEpisode = useCallback((payload) => {
    const episode = { ...payload, id: `demo-new-${Date.now()}`, isDemo: true }
    setEpisodes((current) => [episode, ...current])
    return episode
  }, [])

  const value = useMemo(
    () => ({ enabled: DEMO_MODE_SUPPORTED && enabled, setEnabled, episodes, addEpisode }),
    [enabled, setEnabled, episodes, addEpisode],
  )
  return <DemoModeContext.Provider value={value}>{children}</DemoModeContext.Provider>
}
