import { createContext, useContext } from 'react'

export const THEME_STORAGE_KEY = 'namat-theme'
export const THEMES = ['light', 'dark']

export const ThemeContext = createContext(null)

/** { theme: 'light'|'dark', setTheme } */
export function useTheme() {
  const value = useContext(ThemeContext)
  if (!value) throw new Error('useTheme must be used inside <ThemeProvider>')
  return value
}
