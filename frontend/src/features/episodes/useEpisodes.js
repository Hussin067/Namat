import { useCallback, useEffect, useMemo, useState } from 'react'
import { useAuth } from '../../auth/auth-context.js'
import { useDemoMode } from './demo-context.js'
import { listEpisodes } from './episodeService.js'

const newestFirst = (list) => [...list].sort((a, b) => new Date(b.started_at) - new Date(a.started_at))

/**
 * Episodes for the current page, newest first.
 * source: 'api' (the user's saved records) or 'demo' (dev-only fixtures,
 * never mixed with real data). includeDemo: false always returns real records
 * (the dashboard uses this, so its list matches the real analytics).
 */
export function useEpisodes({ limit = 100, includeDemo = true } = {}) {
  const { authRequest } = useAuth()
  const demo = useDemoMode()
  const [state, setState] = useState({ status: 'loading', episodes: [], total: 0, error: null })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    listEpisodes(authRequest, { limit }).then(
      (page) => !cancelled && setState({ status: 'ready', episodes: page.items, total: page.total, error: null }),
      (error) => !cancelled && setState({ status: 'error', episodes: [], total: 0, error }),
    )
    return () => {
      cancelled = true
    }
  }, [authRequest, limit, attempt])

  const reload = useCallback(() => {
    setState((current) => ({ ...current, status: 'loading', error: null }))
    setAttempt((n) => n + 1)
  }, [])

  // The next, older page (the API returns at most 100 at a time).
  const [more, setMore] = useState({ loading: false, error: null })
  const loaded = state.episodes.length
  const loadMore = useCallback(() => {
    setMore({ loading: true, error: null })
    listEpisodes(authRequest, { limit, offset: loaded }).then(
      (page) => {
        setState((s) => ({ ...s, episodes: [...s.episodes, ...page.items], total: page.total }))
        setMore({ loading: false, error: null })
      },
      (error) => setMore({ loading: false, error }),
    )
  }, [authRequest, limit, loaded])

  return useMemo(() => {
    if (includeDemo && demo.enabled) {
      const episodes = newestFirst(demo.episodes)
      return { status: 'ready', episodes, total: episodes.length, error: null, source: 'demo', reload, hasMore: false }
    }
    return { ...state, source: 'api', reload, loadMore, hasMore: state.episodes.length < state.total, more }
  }, [includeDemo, demo.enabled, demo.episodes, state, reload, loadMore, more])
}
