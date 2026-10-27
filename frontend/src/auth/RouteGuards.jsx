import { Navigate, Outlet, useLocation } from 'react-router'
import { useAuth } from './auth-context.js'

/** Pages behind login. Unauthenticated visitors go to /login, then come back. */
export function RequireAuth() {
  const { isAuthenticated } = useAuth()
  const location = useLocation()
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <Outlet />
}

/**
 * Login and registration. Once signed in (including right after a successful
 * login), users continue to the page they originally asked for.
 */
export function GuestOnly() {
  const { isAuthenticated } = useAuth()
  const location = useLocation()
  if (isAuthenticated) return <Navigate to={location.state?.from ?? '/dashboard'} replace />
  return <Outlet />
}
