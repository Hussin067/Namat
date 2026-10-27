import { createContext, useContext } from 'react'

export const AuthContext = createContext(null)

/**
 * { user, isAuthenticated, expiresAt, endReason, login, register, logout, refreshUser, authRequest }
 * authRequest(path, { method, body }) calls the API as the signed-in user.
 * endReason is 'expired' or 'signed-out' after a session ends, otherwise null.
 */
export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>')
  return value
}
