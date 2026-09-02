import { type ReactNode, useEffect } from 'react'
import {
  ThemeContext,
  type ThemeContextValue,
} from '../contexts/ThemeContext'

const STORAGE_KEY = 'fullstack-template-theme'

const LIGHT_THEME: ThemeContextValue = {
  preference: 'light',
  resolvedTheme: 'light',
  setPreference: () => undefined,
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    window.localStorage.removeItem(STORAGE_KEY)
    document.documentElement.dataset.theme = 'light'
    document.documentElement.style.colorScheme = 'light'
  }, [])

  return <ThemeContext.Provider value={LIGHT_THEME}>{children}</ThemeContext.Provider>
}
