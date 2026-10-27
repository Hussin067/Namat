import { useCallback, useEffect, useMemo, useState } from 'react'
import { THEME_STORAGE_KEY, THEMES, ThemeContext } from './theme-context.js'

// The theme is a harmless UI setting, so localStorage is fine here.
// Tokens and health data are never stored in the browser.
// Light is the default; the device's own setting is not used.
function readTheme() {
  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY)
    return THEMES.includes(saved) ? saved : 'light'
  } catch {
    return 'light'
  }
}

function applyTheme(theme) {
  const root = document.documentElement
  if (root.dataset.theme === theme) return
  root.classList.add('theme-transition')
  window.setTimeout(() => root.classList.remove('theme-transition'), 250)
  root.dataset.theme = theme
}

export default function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(readTheme)

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  const setTheme = useCallback((next) => {
    if (!THEMES.includes(next)) return
    // Apply before re-rendering, so components that read the theme's CSS
    // variables during render (the charts) get the new colours straight away.
    applyTheme(next)
    setThemeState(next)
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next)
    } catch {
      // Storage blocked (private mode): the choice still applies for this visit.
    }
  }, [])

  const value = useMemo(() => ({ theme, setTheme }), [theme, setTheme])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
