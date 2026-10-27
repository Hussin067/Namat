import { parseDay } from '../analytics/analyticsService.js'
import { formatDate, formatDuration, formatTime } from '../episodes/format.js'
import { NUMERIC_FACTORS, YES_NO_FACTORS } from './dailyForms.js'

const number = (value, locale) => new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(Number(value))

/** What was recorded, as short text parts. Fields that weren't recorded are left out. */
export function describeEntry(kind, entry, t, locale) {
  if (kind === 'sleep') {
    const parts = [
      t('daily.sleep.range', {
        bed: formatTime(new Date(entry.bedtime), locale),
        wake: formatTime(new Date(entry.wake_time), locale),
      }),
      formatDuration(entry.duration_minutes, locale),
    ]
    if (entry.quality != null) parts.push(t('daily.sleep.qualityValue', { value: t(`daily.sleep.qualities.${entry.quality}`) }))
    if (entry.awakenings != null) parts.push(t('daily.sleep.awakeningsValue', { count: entry.awakenings }))
    return { title: t('daily.sleep.nightOf', { date: formatDate(parseDay(entry.sleep_date), locale) }), parts }
  }
  const parts = []
  if (entry.stress_level != null) parts.push(t('daily.factors.values.stress_level', { value: entry.stress_level }))
  for (const { name } of NUMERIC_FACTORS) {
    if (entry[name] != null) parts.push(t(`daily.factors.values.${name}`, { value: number(entry[name], locale) }))
  }
  for (const name of YES_NO_FACTORS) {
    if (entry[name] != null) parts.push(t(`daily.factors.values.${name}`, { value: t(entry[name] ? 'daily.yes' : 'daily.no') }))
  }
  if (!parts.length) parts.push(t('daily.factors.notesOnly'))
  return { title: formatDate(parseDay(entry.log_date), locale), parts }
}
