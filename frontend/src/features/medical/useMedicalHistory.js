import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '../../auth/auth-context.js'
import { fetchMedicalHistory } from './medicalService.js'

/**
 * The user's whole medical history in one request. reload() fetches it again
 * (after a save or delete) while the current data stays on screen.
 */
export function useMedicalHistory() {
  const { authRequest } = useAuth()
  const [state, setState] = useState({ status: 'loading', data: null, error: null })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    fetchMedicalHistory(authRequest, { signal: controller.signal }).then(
      (data) => setState({ status: 'ready', data, error: null }),
      (error) => {
        if (!controller.signal.aborted) setState((s) => ({ ...s, status: s.data ? 'ready' : 'error', error }))
      },
    )
    return () => controller.abort()
  }, [authRequest, attempt])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])
  const retry = useCallback(() => {
    setState({ status: 'loading', data: null, error: null })
    setAttempt((n) => n + 1)
  }, [])

  return { ...state, reload, retry }
}
