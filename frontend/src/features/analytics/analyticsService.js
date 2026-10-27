// Dashboard analytics from GET /analytics/dashboard.
// All numbers are calculated by the backend for the signed-in user; the
// frontend only formats them, so every card and chart uses the same range.

export const PRESET_PERIODS = ['7d', '30d', '3m', '6m', '12m']
export const DEFAULT_PERIOD = '30d'
export const MAX_CUSTOM_DAYS = 366 // same limit as the backend

/**
 * filters: { period: '7d'|'30d'|'3m'|'6m'|'12m' } or { period: 'custom', start, end }
 * with start/end as 'YYYY-MM-DD' (inclusive). `request` is useAuth().authRequest.
 */
export function getDashboardAnalytics(request, filters, { signal } = {}) {
  const params = new URLSearchParams()
  if (filters.period === 'custom') {
    params.set('start_date', filters.start)
    params.set('end_date', filters.end)
  } else {
    params.set('period', filters.period)
  }
  return request(`/analytics/dashboard?${params}`, { signal })
}

/** Read the filters from the URL (?period=…&from=…&to=…), falling back to 30 days. */
export function filtersFromSearch(searchParams) {
  const period = searchParams.get('period')
  const start = searchParams.get('from')
  const end = searchParams.get('to')
  if (period === 'custom' && validateCustomRange(start, end) == null) return { period, start, end }
  return { period: PRESET_PERIODS.includes(period) ? period : DEFAULT_PERIOD }
}

export function filtersToSearch(filters) {
  return filters.period === 'custom'
    ? { period: 'custom', from: filters.start, to: filters.end }
    : { period: filters.period }
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

/** Mirrors the backend's rules; returns a message key, or null when valid. */
export function validateCustomRange(start, end) {
  if (!start || !end || !ISO_DATE.test(start) || !ISO_DATE.test(end)) return 'dashboard.filters.rangeRequired'
  if (start > end) return 'dashboard.filters.startAfterEnd'
  const days = (Date.parse(`${end}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) / 86400000 + 1
  if (days > MAX_CUSTOM_DAYS) return 'dashboard.filters.rangeTooLong'
  if (start < '2000-01-01') return 'dashboard.filters.rangeTooEarly'
  return null
}

/** 'YYYY-MM-DD' → local Date at midnight (avoids the UTC shift of new Date('YYYY-MM-DD')). */
export function parseDay(value) {
  const [y, m, d] = value.split('-').map(Number)
  return new Date(y, m - 1, d)
}
