// Run from frontend/ with:  npm test
import { afterEach, describe, expect, it, vi } from 'vitest'
import { API_BASE_URL, apiRequest, loginUser } from './api.js'

afterEach(() => vi.unstubAllGlobals())

const reply = (status, body = null, headers = {}) =>
  Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body), headers: new Headers(headers), blob: () => Promise.resolve(new Blob(['%PDF'])) })

describe('api', () => {
  it('uses the local API only in development', () => {
    expect(import.meta.env.DEV).toBe(true)
    expect(API_BASE_URL).toBe('http://localhost:8000')
  })

  it('turns a 429 into a friendly "too many attempts" message', async () => {
    vi.stubGlobal('fetch', vi.fn(() => reply(429, { detail: 'Too many attempts.' }, { 'Retry-After': '60' })))
    await expect(loginUser('a@example.com', 'synthetic-password')).rejects.toMatchObject({ key: 'errors.tooManyAttempts', status: 429 })
  })

  it('never shows the server’s own error text', async () => {
    vi.stubGlobal('fetch', vi.fn(() => reply(500, { detail: 'Internal server error.' })))
    await expect(apiRequest('/episodes', { token: 't' })).rejects.toMatchObject({ key: 'errors.server', status: 500 })
  })

  it('reads a downloaded file and its suggested name', async () => {
    vi.stubGlobal('fetch', vi.fn(() => reply(200, null, { 'Content-Disposition': 'attachment; filename="namat-medical-report-2026-06-01-to-2026-06-30-en.pdf"' })))
    const file = await apiRequest('/reports/medical/pdf', { token: 't', responseType: 'file' })
    expect(file.filename).toBe('namat-medical-report-2026-06-01-to-2026-06-30-en.pdf')
    expect(file.blob).toBeInstanceOf(Blob)
  })

  it('sends the token only in the Authorization header', async () => {
    const fetch = vi.fn(() => reply(200, {}))
    vi.stubGlobal('fetch', fetch)
    await apiRequest('/episodes?limit=10', { token: 'synthetic-token' })
    const [url, options] = fetch.mock.calls[0]
    expect(url).not.toContain('synthetic-token')
    expect(options.headers.Authorization).toBe('Bearer synthetic-token')
  })
})
