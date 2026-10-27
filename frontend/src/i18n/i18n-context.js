import { createContext, useContext } from 'react'

export const LANGUAGE_STORAGE_KEY = 'namat-lang'
export const LANGUAGES = ['en', 'ar']

/** Locale used for dates and numbers. Arabic keeps Western digits to match the form inputs. */
export const LOCALES = { en: 'en', ar: 'ar-u-nu-latn' }

export const I18nContext = createContext(null)

/** { lang, dir, locale, setLang, t(key, vars) } */
export function useI18n() {
  const value = useContext(I18nContext)
  if (!value) throw new Error('useI18n must be used inside <I18nProvider>')
  return value
}
