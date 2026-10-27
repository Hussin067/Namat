import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '../../auth/auth-context.js'

// One string per distinct request, so the effect re-runs exactly when the
// request would change (and not when a new but equal filters object arrives).
const filtersKey = (f) => (f.period === 'custom' ? `custom|${f.start}|${f.end}` : f.period)
const keyToFilters = (key) => {
  const [period, start, end] = key.split('|')
  return period === 'custom' ? { period, start, end } : { period }
}

/**
 * Loads `fetcher(authRequest, filters, { signal })` for the dashboard's date filters.
 * - status: 'loading' (nothing to show yet), 'ready' or 'error'
 * - refreshing: true while data for newer filters loads; the previous data
 *   stays on screen, so the layout doesn't jump.
 * A newer filter choice aborts the older request, so a stale response can
 * never overwrite it. Failures never fall back to demo or placeholder data.
 * `fetcher` must be a stable (module-level) function.
 */
export function useFilteredRequest(fetcher, filters) {
  const { authRequest } = useAuth()
  const key = filtersKey(filters)
  const [state, setState] = useState({ status: 'loading', data: null, error: null, refreshing: false })
  const [request, setRequest] = useState({ key, attempt: 0 })

  // New filters: show the previous data as "refreshing" until the new data arrives.
  if (request.key !== key) {
    setRequest({ key, attempt: 0 })
    setState((s) => ({ ...s, refreshing: s.data != null, status: s.data ? 'ready' : 'loading', error: null }))
  }

  useEffect(() => {
    const controller = new AbortController()
    fetcher(authRequest, keyToFilters(request.key), { signal: controller.signal }).then(
      (data) => setState({ status: 'ready', data, error: null, refreshing: false }),
      (error) => {
        if (controller.signal.aborted) return // superseded by a newer request
        setState((s) => ({ ...s, status: 'error', error, refreshing: false }))
      },
    )
    return () => controller.abort()
  }, [fetcher, authRequest, request])

  const retry = useCallback(() => {
    setState((s) => ({ ...s, status: s.data ? 'ready' : 'loading', refreshing: s.data != null, error: null }))
    setRequest((r) => ({ ...r, attempt: r.attempt + 1 }))
  }, [])

  return { ...state, retry }
}
