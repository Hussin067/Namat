// Run from frontend/ with:  npm test
import { afterEach, describe, expect, it, vi } from 'vitest'
import { API_BASE_URL, apiRequest, loginUser, logoutUser } from './api.js'

afterEach(() => {
  vi.unstubAllGlobals()
  document.cookie = 'namat_csrf=; Max-Age=0; Path=/'
})

const reply = (status, body = null, headers = {}) =>
  Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body), headers: new Headers(headers), blob: () => Promise.resolve(new Blob(['%PDF'])) })

describe('api', () => {
  it('calls the API on the same origin, under /api', () => {
    expect(API_BASE_URL).toBe('/api')
  })

  it('sends cookies with every request and never a token', async () => {
    const fetch = vi.fn(() => reply(200, {}))
    vi.stubGlobal('fetch', fetch)
    await apiRequest('/episodes?limit=10')
    const [url, options] = fetch.mock.calls[0]
    expect(url).toBe('/api/episodes?limit=10')
    expect(options.credentials).toBe('include')
    expect(options.headers.Authorization).toBeUndefined()
  })

  it('echoes the CSRF cookie on requests that change data, not on reads', async () => {
    document.cookie = 'namat_csrf=synthetic-csrf-value; Path=/'
    const fetch = vi.fn(() => reply(200, {}))
    vi.stubGlobal('fetch', fetch)
    await apiRequest('/episodes', { method: 'POST', body: { peak_intensity: 3 } })
    await apiRequest('/episodes')
    expect(fetch.mock.calls[0][1].headers['X-CSRF-Token']).toBe('synthetic-csrf-value')
    expect(fetch.mock.calls[1][1].headers['X-CSRF-Token']).toBeUndefined()
  })

  it('logs out on the server', async () => {
    const fetch = vi.fn(() => reply(204))
    vi.stubGlobal('fetch', fetch)
    await logoutUser()
    expect(fetch).toHaveBeenCalledWith('/api/auth/logout', expect.objectContaining({ method: 'POST', credentials: 'include' }))
  })

  it('turns a 429 into a friendly "too many attempts" message', async () => {
    vi.stubGlobal('fetch', vi.fn(() => reply(429, { detail: 'Too many attempts.' }, { 'Retry-After': '60' })))
    await expect(loginUser('a@example.com', 'synthetic-password')).rejects.toMatchObject({ key: 'errors.tooManyAttempts', status: 429 })
  })

  it('never shows the server’s own error text', async () => {
    vi.stubGlobal('fetch', vi.fn(() => reply(500, { detail: 'Internal server error.' })))
    await expect(apiRequest('/episodes')).rejects.toMatchObject({ key: 'errors.server', status: 500 })
  })

  it('reads a downloaded file and its suggested name', async () => {
    vi.stubGlobal('fetch', vi.fn(() => reply(200, null, { 'Content-Disposition': 'attachment; filename="namat-medical-report-2026-06-01-to-2026-06-30-en.pdf"' })))
    const file = await apiRequest('/reports/medical/pdf', { responseType: 'file' })
    expect(file.filename).toBe('namat-medical-report-2026-06-01-to-2026-06-30-en.pdf')
    expect(file.blob).toBeInstanceOf(Blob)
  })
})
