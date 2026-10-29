import { Navigate, Outlet, useLocation } from 'react-router'
import { LoadingState } from '../components/ui/States.jsx'
import { useI18n } from '../i18n/i18n-context.js'
import { useAuth } from './auth-context.js'

/** Shown while the app asks the API whether the session cookie is still valid. */
function CheckingSession() {
  const { t } = useI18n()
  return (
    <div className="flex min-h-dvh items-center justify-center">
      <LoadingState label={t('auth.checkingSession')} />
    </div>
  )
}

/**
 * Pages behind login. Nothing is decided until the session check finishes, so a
 * refresh on any page stays there when the session is still valid. Signed-out
 * visitors go to /login and come back to the exact address they asked for.
 */
export function RequireAuth() {
  const { isAuthenticated, isChecking } = useAuth()
  const location = useLocation()
  if (isChecking) return <CheckingSession />
  if (!isAuthenticated) {
    const from = `${location.pathname}${location.search}${location.hash}`
    return <Navigate to="/login" replace state={{ from }} />
  }
  return <Outlet />
}

/**
 * Login and registration. Once signed in (including right after a successful
 * login, or a refresh with a valid session), users continue to the page they
 * originally asked for.
 */
export function GuestOnly() {
  const { isAuthenticated, isChecking } = useAuth()
  const location = useLocation()
  if (isChecking) return <CheckingSession />
  if (isAuthenticated) return <Navigate to={location.state?.from ?? '/dashboard'} replace />
  return <Outlet />
}
