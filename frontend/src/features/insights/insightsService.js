// Personal insights from GET /insights. They are
// calculated by the backend from the signed-in user's own records, for the
// same date filters as the rest of the dashboard.

/** filters: as for analytics ({ period } or { period: 'custom', start, end }). */
export function getInsights(request, filters, { signal } = {}) {
  const params = new URLSearchParams()
  if (filters.period === 'custom') {
    params.set('start_date', filters.start)
    params.set('end_date', filters.end)
  } else {
    params.set('period', filters.period)
  }
  return request(`/insights?${params}`, { signal })
}
