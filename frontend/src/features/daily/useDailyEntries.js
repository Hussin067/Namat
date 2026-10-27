import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '../../auth/auth-context.js'
import { listEntries } from './dailyService.js'

const PAGE_SIZE = 60

/**
 * The user's sleep logs or daily factors, most recent first, PAGE_SIZE at a
 * time. reload() starts again from the first page (after a save or delete).
 */
export function useDailyEntries(kind) {
  const { authRequest } = useAuth()
  const [state, setState] = useState({ status: 'loading', items: [], total: 0, error: null })
  const [pages, setPages] = useState({ kind, count: 1, attempt: 0 })

  if (pages.kind !== kind) {
    setPages({ kind, count: 1, attempt: 0 })
    setState({ status: 'loading', items: [], total: 0, error: null })
  }

  useEffect(() => {
    const controller = new AbortController()
    listEntries(authRequest, pages.kind, { limit: PAGE_SIZE * pages.count, signal: controller.signal }).then(
      (page) => setState({ status: 'ready', items: page.items, total: page.total, error: null }),
      (error) => {
        if (!controller.signal.aborted) setState((s) => ({ ...s, status: 'error', error }))
      },
    )
    return () => controller.abort()
  }, [authRequest, pages])

  const reload = useCallback(() => setPages((p) => ({ ...p, attempt: p.attempt + 1 })), [])
  const loadMore = useCallback(() => setPages((p) => ({ ...p, count: p.count + 1 })), [])

  return { ...state, hasMore: state.items.length < state.total, reload, loadMore }
}
