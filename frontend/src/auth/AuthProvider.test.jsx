// An expired or invalid token (401 from any API call) must end the session.
import { useEffect } from 'react'
import { act, cleanup, render } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import AuthProvider from './AuthProvider.jsx'
import { useAuth } from './auth-context.js'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const json = (status, body) => Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) })

it('ends the session when an API call answers 401', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn((url) => {
      if (url.endsWith('/auth/login')) return json(200, { access_token: 'synthetic-token', token_type: 'bearer', expires_in: 1200 })
      if (url.endsWith('/auth/me')) return json(200, { id: 'u1', email: 'test@example.com', display_name: null, timezone: 'UTC', created_at: '2026-01-01T00:00:00Z' })
      return json(401, { detail: 'Could not validate credentials' }) // e.g. /insights after the token expired
    }),
  )

  const latest = { current: null }
  function Probe() {
    const value = useAuth()
    useEffect(() => {
      latest.current = value
    })
    return null
  }
  const auth = new Proxy({}, { get: (_, key) => latest.current[key] })
  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  )

  await act(() => auth.login('test@example.com', 'synthetic-password-1'))
  expect(auth.isAuthenticated).toBe(true)

  await act(async () => {
    await expect(auth.authRequest('/insights?period=30d')).rejects.toMatchObject({ status: 401 })
  })
  expect(auth.isAuthenticated).toBe(false)
  expect(auth.endReason).toBe('expired')
  expect(localStorage.length).toBe(0) // the token was never written to storage
})
