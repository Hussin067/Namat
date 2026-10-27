import { useCallback, useEffect, useMemo, useState } from 'react'
import { I18nContext, LANGUAGE_STORAGE_KEY, LANGUAGES, LOCALES } from './i18n-context.js'
import ar from './messages/ar.js'
import en from './messages/en.js'

const MESSAGES = { en, ar }

// The language choice is a UI preference, like the theme, so localStorage is fine.
function readLang() {
  try {
    const saved = localStorage.getItem(LANGUAGE_STORAGE_KEY)
    return LANGUAGES.includes(saved) ? saved : 'en'
  } catch {
    return 'en'
  }
}

function lookup(messages, key) {
  return key.split('.').reduce((node, part) => (node == null ? undefined : node[part]), messages)
}

function createTranslator(lang) {
  const plurals = new Intl.PluralRules(lang)
  return function t(key, vars = {}) {
    let entry = lookup(MESSAGES[lang], key) ?? lookup(MESSAGES.en, key)
    if (entry && typeof entry === 'object' && typeof vars.count === 'number') {
      entry = entry[vars.count === 0 && entry.zero ? 'zero' : plurals.select(vars.count)] ?? entry.other
    }
    if (typeof entry !== 'string') {
      if (import.meta.env.DEV) console.warn(`[i18n] missing text for "${key}"`)
      return key
    }
    return entry.replace(/\{(\w+)\}/g, (match, name) => (name in vars ? String(vars[name]) : match))
  }
}

export default function I18nProvider({ children }) {
  const [lang, setLangState] = useState(readLang)
  const dir = lang === 'ar' ? 'rtl' : 'ltr'
  const t = useMemo(() => createTranslator(lang), [lang])

  // Mirror the choice onto <html> so the browser, screen readers and CSS
  // (:lang, logical properties) all follow it.
  useEffect(() => {
    const root = document.documentElement
    root.lang = lang
    root.dir = dir
    document.title = t('meta.title')
  }, [lang, dir, t])

  const setLang = useCallback((next) => {
    if (!LANGUAGES.includes(next)) return
    setLangState(next)
    try {
      localStorage.setItem(LANGUAGE_STORAGE_KEY, next)
    } catch {
      // Storage blocked: the choice still applies for this visit.
    }
  }, [])

  const value = useMemo(() => ({ lang, dir, locale: LOCALES[lang], setLang, t }), [lang, dir, setLang, t])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}
