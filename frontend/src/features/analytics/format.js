import { parseDay } from './analyticsService.js'

const cache = new Map()
const dateFormat = (locale, options) => {
  const id = `${locale}|${JSON.stringify(options)}`
  if (!cache.has(id)) cache.set(id, new Intl.DateTimeFormat(locale, options))
  return cache.get(id)
}

/**
 * Label for a time bucket ('YYYY-MM-DD' = start of the day, ISO week or month).
 * style 'short' for axis ticks, 'long' for tooltips and the data tables.
 */
export function formatBucket(value, interval, locale, style = 'short') {
  const day = parseDay(value)
  if (interval === 'month') {
    return dateFormat(locale, style === 'short' ? { month: 'short', year: '2-digit' } : { month: 'long', year: 'numeric' }).format(day)
  }
  return dateFormat(locale, style === 'short' ? { day: 'numeric', month: 'short' } : { day: 'numeric', month: 'long', year: 'numeric' }).format(day)
}

/** "1 – 30 Sep 2026", in the user's language. */
export function formatRange(start, end, locale) {
  return dateFormat(locale, { day: 'numeric', month: 'short', year: 'numeric' }).formatRange(parseDay(start), parseDay(end))
}
