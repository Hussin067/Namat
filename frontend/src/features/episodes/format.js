// Locale-aware formatting. Every function takes the locale from useI18n(),
// so Arabic gets Arabic month names, word order and grammar (e.g. "ساعتان").

const cache = new Map()
function formatter(Type, locale, options) {
  const id = `${Type.name}|${locale}|${JSON.stringify(options)}`
  if (!cache.has(id)) cache.set(id, new Type(locale, options))
  return cache.get(id)
}

const isArabic = (locale) => locale.startsWith('ar')

export const formatDateTime = (iso, locale) =>
  formatter(Intl.DateTimeFormat, locale, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(iso))

export const formatDate = (iso, locale) =>
  formatter(Intl.DateTimeFormat, locale, { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(iso))

export const formatShortDate = (date, locale) =>
  formatter(Intl.DateTimeFormat, locale, { day: 'numeric', month: 'short' }).format(date)

export const formatTime = (date, locale) =>
  formatter(Intl.DateTimeFormat, locale, { hour: 'numeric', minute: '2-digit' }).format(date)

export function durationMinutes(episode) {
  if (!episode.ended_at) return null
  return Math.round((new Date(episode.ended_at) - new Date(episode.started_at)) / 60000)
}

/** "2 hr 30 min" / "ساعتان و30 دقيقة". Returns null for an ongoing episode. */
export function formatDuration(minutes, locale) {
  if (minutes == null) return null
  const unitDisplay = isArabic(locale) ? 'long' : 'short'
  const unit = (u, n) => formatter(Intl.NumberFormat, locale, { style: 'unit', unit: u, unitDisplay }).format(n)
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (!hours) return unit('minute', rest)
  if (!rest) return unit('hour', hours)
  return formatter(Intl.ListFormat, locale, { type: 'unit', style: isArabic(locale) ? 'long' : 'narrow' }).format([
    unit('hour', hours),
    unit('minute', rest),
  ])
}

export function formatRelative(iso, locale, now = Date.now()) {
  const rtf = formatter(Intl.RelativeTimeFormat, locale, { numeric: 'auto' })
  const diffMinutes = Math.round((new Date(iso) - now) / 60000)
  const abs = Math.abs(diffMinutes)
  if (abs < 60) return rtf.format(diffMinutes, 'minute')
  if (abs < 60 * 24) return rtf.format(Math.round(diffMinutes / 60), 'hour')
  return rtf.format(Math.round(diffMinutes / (60 * 24)), 'day')
}

/** "YYYY-MM-DDTHH:mm" in local time, the format <input type="datetime-local"> uses. */
export function toLocalInputValue(date) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}
