import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '../../auth/auth-context.js'
import { getEpisode } from './episodeService.js'

/** One saved episode by id: { status: 'loading'|'ready'|'error', episode, error, reload }. */
export function useEpisode(id) {
  const { authRequest } = useAuth()
  const [state, setState] = useState({ status: 'loading', episode: null, error: null })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    getEpisode(authRequest, id).then(
      (episode) => !cancelled && setState({ status: 'ready', episode, error: null }),
      (error) => !cancelled && setState({ status: 'error', episode: null, error }),
    )
    return () => {
      cancelled = true
    }
  }, [authRequest, id, attempt])

  const reload = useCallback(() => {
    setState({ status: 'loading', episode: null, error: null })
    setAttempt((n) => n + 1)
  }, [])

  return { ...state, reload }
}
