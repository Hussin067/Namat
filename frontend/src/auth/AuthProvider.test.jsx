// Run from frontend/ with:  npm test
// The browser's fetch is replaced by a fake API; the provider, the route guards
// and the translations are the real code. All data is synthetic.

import { useEffect } from 'react'
import { act, cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import I18nProvider from '../i18n/I18nProvider.jsx'
import AuthProvider from './AuthProvider.jsx'
import { useAuth } from './auth-context.js'
import { GuestOnly, RequireAuth } from './RouteGuards.jsx'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.useRealTimers()
  localStorage.clear()
})

const USER = { id: 'u1', email: 'test@example.com', display_name: null, timezone: 'UTC', created_at: '2026-01-01T00:00:00Z' }
const inMinutes = (m) => new Date(Date.now() + m * 60000).toISOString()
const json = (status, body) => Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) })

/** A fake API: routes are matched by path suffix. */
function fakeApi(routes) {
  const fetch = vi.fn((url, options = {}) => {
    const path = Object.keys(routes).find((p) => url.endsWith(p))
    return path ? routes[path](options) : json(401, { detail: 'Could not validate credentials' })
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

function WhereAmI() {
  const location = useLocation()
  return <p data-testid="where">{`${location.pathname} from=${location.state?.from ?? ''}`}</p>
}

let latest = null
function Probe() {
  const auth = useAuth()
  useEffect(() => {
    latest = auth
  })
  return null
}

function renderApp(path) {
  return render(
    <I18nProvider>
      <AuthProvider>
        <Probe />
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route element={<GuestOnly />}>
              <Route path="/login" element={<h1>Login page</h1>} />
            </Route>
            <Route element={<RequireAuth />}>
              <Route path="/profile" element={<h1>Profile page</h1>} />
              <Route path="/episodes/:id" element={<h1>Episode page</h1>} />
            </Route>
          </Routes>
          <WhereAmI />
        </MemoryRouter>
      </AuthProvider>
    </I18nProvider>,
  )
}

describe('session restore on start-up (refresh, new tab)', () => {
  it('waits for the session check, then stays on the protected page', async () => {
    let answer
    fakeApi({ '/auth/session': () => new Promise((resolve) => (answer = resolve)) })
    renderApp('/profile')

    expect(screen.getByText('Checking your session…')).toBeTruthy()
    expect(screen.getByTestId('where').textContent).toBe('/profile from=') // no redirect yet

    await act(async () => answer({ ok: true, status: 200, json: () => Promise.resolve({ user: USER, expires_at: inMinutes(20) }) }))
    expect(screen.getByText('Profile page')).toBeTruthy()
    expect(latest.isAuthenticated).toBe(true)
    expect(latest.user.email).toBe('test@example.com')
  })

  it('works for nested routes too', async () => {
    fakeApi({ '/auth/session': () => json(200, { user: USER, expires_at: inMinutes(20) }) })
    renderApp('/episodes/123')
    expect(await screen.findByText('Episode page')).toBeTruthy()
  })

  it('goes to login with the intended destination when there is no valid cookie', async () => {
    fakeApi({}) // /auth/session answers 401
    renderApp('/episodes/123?tab=notes')
    expect(await screen.findByText('Login page')).toBeTruthy()
    expect(screen.getByTestId('where').textContent).toBe('/login from=/episodes/123?tab=notes')
  })

  it('keeps tokens out of browser storage', async () => {
    fakeApi({ '/auth/session': () => json(200, { user: USER, expires_at: inMinutes(20) }) })
    renderApp('/profile')
    await screen.findByText('Profile page')
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })
})

describe('session lifetime', () => {
  it('logs in, then returns to the page originally asked for', async () => {
    fakeApi({ '/auth/login': () => json(200, { user: USER, expires_at: inMinutes(20) }) })
    renderApp('/profile')
    await screen.findByText('Login page')
    await act(() => latest.login('test@example.com', 'synthetic-password-1'))
    expect(await screen.findByText('Profile page')).toBeTruthy()
  })

  it('ends the session when an API call answers 401 (expired cookie)', async () => {
    fakeApi({ '/auth/session': () => json(200, { user: USER, expires_at: inMinutes(20) }) })
    renderApp('/profile')
    await screen.findByText('Profile page')

    await act(async () => {
      await expect(latest.authRequest('/insights?period=30d')).rejects.toMatchObject({ status: 401 })
    })
    expect(await screen.findByText('Login page')).toBeTruthy()
    expect(latest.endReason).toBe('expired')
  })

  it('ends the session in the app when the cookie expires', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    fakeApi({ '/auth/session': () => json(200, { user: USER, expires_at: inMinutes(1) }) })
    renderApp('/profile')
    await screen.findByText('Profile page')
    await act(async () => vi.advanceTimersByTime(61_000))
    expect(await screen.findByText('Login page')).toBeTruthy()
    expect(latest.endReason).toBe('expired')
  })

  it('logs out on the server and forgets the session', async () => {
    const fetch = fakeApi({
      '/auth/session': () => json(200, { user: USER, expires_at: inMinutes(20) }),
      '/auth/logout': () => Promise.resolve({ ok: true, status: 204, json: () => Promise.reject(new Error('no body')) }),
    })
    renderApp('/profile')
    await screen.findByText('Profile page')
    await act(() => latest.logout())
    expect(fetch).toHaveBeenCalledWith('/api/auth/logout', expect.objectContaining({ method: 'POST', credentials: 'include' }))
    expect(await screen.findByText('Login page')).toBeTruthy()
    expect(latest.endReason).toBe('signed-out')
  })
})
