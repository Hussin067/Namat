import { createContext, useContext } from 'react'

/** Demo mode is available only in development builds (`npm run dev`). */
export const DEMO_MODE_SUPPORTED = import.meta.env.DEV

export const DemoModeContext = createContext({
  enabled: false,
  setEnabled: () => {},
  episodes: [],
  addEpisode: () => {},
})

export function useDemoMode() {
  return useContext(DemoModeContext)
}
