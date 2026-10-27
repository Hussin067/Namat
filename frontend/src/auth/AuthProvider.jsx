import { useCallback, useEffect, useMemo, useState } from 'react'
import { ApiError, apiRequest, fetchCurrentUser, loginUser, registerUser } from '../api.js'
import { AuthContext } from './auth-context.js'

export default function AuthProvider({ children }) {
  // The access token lives only in React memory: never in localStorage,
  // sessionStorage or cookies. Reloading the page or closing the tab logs out.
  const [session, setSession] = useState(null) // { token, user, expiresAt }
  const [endReason, setEndReason] = useState(null)

  const logout = useCallback((reason = 'signed-out') => {
    setSession(null)
    setEndReason(reason)
  }, [])

  // End the session when the token expires.
  useEffect(() => {
    if (!session) return undefined
    const timer = setTimeout(() => logout('expired'), session.expiresAt - Date.now())
    return () => clearTimeout(timer)
  }, [session, logout])

  const login = useCallback(async (email, password) => {
    const { access_token: token, expires_in: expiresIn } = await loginUser(email, password)
    const user = await fetchCurrentUser(token)
    setEndReason(null)
    setSession({ token, user, expiresAt: Date.now() + expiresIn * 1000 })
  }, [])

  const register = useCallback((email, password) => registerUser(email, password), [])

  /** Re-fetch /auth/me. A 401 means the token is no longer valid: end the session. */
  const refreshUser = useCallback(async () => {
    if (!session) return null
    try {
      const user = await fetchCurrentUser(session.token)
      setSession((current) => (current ? { ...current, user } : current))
      return user
    } catch (error) {
      if (error.status === 401) logout('expired')
      throw error
    }
  }, [session, logout])

  /**
   * Call the API as the signed-in user. The token is added here and never
   * handed to pages. A 401 means the token expired or the account is gone,
   * so the session ends. Its identity only changes on login/logout.
   */
  const token = session?.token ?? null
  const authRequest = useCallback(
    async (path, options = {}) => {
      if (!token) throw new ApiError('errors.sessionExpired', 401)
      try {
        return await apiRequest(path, { ...options, token })
      } catch (error) {
        if (error.status === 401) logout('expired')
        throw error
      }
    },
    [token, logout],
  )

  const value = useMemo(
    () => ({
      user: session?.user ?? null,
      isAuthenticated: Boolean(session),
      expiresAt: session?.expiresAt ?? null,
      endReason,
      login,
      register,
      logout,
      refreshUser,
      authRequest,
    }),
    [session, endReason, login, register, logout, refreshUser, authRequest],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
