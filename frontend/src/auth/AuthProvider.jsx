import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiRequest, fetchCurrentUser, fetchSession, loginUser, logoutUser, registerUser } from '../api.js'
import { AuthContext } from './auth-context.js'

/**
 * The session lives in an HttpOnly cookie set by the API: JavaScript never sees
 * the token, and nothing is kept in localStorage or sessionStorage. On start-up
 * (including after a refresh or in a new tab) the app asks the API whether the
 * cookie still holds a valid session; until that answer arrives, status is
 * 'checking' and the route guards wait instead of redirecting.
 */
export default function AuthProvider({ children }) {
  // status: 'checking' | 'authenticated' | 'anonymous'
  const [state, setState] = useState({ status: 'checking', user: null, expiresAt: null })
  const [endReason, setEndReason] = useState(null)

  const endSession = useCallback((reason) => {
    setState({ status: 'anonymous', user: null, expiresAt: null })
    setEndReason(reason)
  }, [])

  const startSession = useCallback(({ user, expires_at: expiresAt }) => {
    setEndReason(null)
    setState({ status: 'authenticated', user, expiresAt: new Date(expiresAt).getTime() })
  }, [])

  // Restore the session from the cookie, once, when the app starts.
  useEffect(() => {
    const controller = new AbortController()
    fetchSession({ signal: controller.signal }).then(startSession, (error) => {
      if (error?.name === 'AbortError') return
      // 401 (no cookie, or an expired one) or the API is unreachable: not signed in.
      setState({ status: 'anonymous', user: null, expiresAt: null })
    })
    return () => controller.abort()
  }, [startSession])

  // The cookie expires with the token; end the session in the app at the same moment.
  const expiresAt = state.expiresAt
  useEffect(() => {
    if (!expiresAt) return undefined
    const timer = setTimeout(() => endSession('expired'), Math.max(0, expiresAt - Date.now()))
    return () => clearTimeout(timer)
  }, [expiresAt, endSession])

  const login = useCallback(async (email, password) => startSession(await loginUser(email, password)), [startSession])

  const register = useCallback((email, password) => registerUser(email, password), [])

  /** Ask the API to expire the cookies, then forget the session locally (even if offline). */
  const logout = useCallback(
    async (reason = 'signed-out') => {
      try {
        await logoutUser()
      } catch {
        // Unreachable API: the cookie still expires on its own.
      }
      endSession(reason)
    },
    [endSession],
  )

  /** Re-fetch /auth/me. A 401 means the session is no longer valid: end it. */
  const refreshUser = useCallback(async () => {
    try {
      const user = await fetchCurrentUser()
      setState((current) => (current.status === 'authenticated' ? { ...current, user } : current))
      return user
    } catch (error) {
      if (error.status === 401) endSession('expired')
      throw error
    }
  }, [endSession])

  /**
   * Call the API as the signed-in user (the browser sends the cookie). A 401 means
   * the session expired or the account is gone, so the session ends.
   */
  const authRequest = useCallback(
    async (path, options = {}) => {
      try {
        return await apiRequest(path, options)
      } catch (error) {
        if (error.status === 401) endSession('expired')
        throw error
      }
    },
    [endSession],
  )

  const value = useMemo(
    () => ({
      user: state.user,
      status: state.status,
      isChecking: state.status === 'checking',
      isAuthenticated: state.status === 'authenticated',
      expiresAt: state.expiresAt,
      endReason,
      login,
      register,
      logout,
      refreshUser,
      authRequest,
    }),
    [state, endReason, login, register, logout, refreshUser, authRequest],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
