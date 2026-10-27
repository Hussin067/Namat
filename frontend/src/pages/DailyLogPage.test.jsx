// Run from frontend/ with:  npm test
// The API is replaced by a fake authRequest; the page, forms and translations are real.

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api.js'
import { AuthContext } from '../auth/auth-context.js'
import I18nProvider from '../i18n/I18nProvider.jsx'
import DailyLogPage from './DailyLogPage.jsx'

afterEach(() => {
  cleanup()
  localStorage.clear()
})

const empty = { items: [], total: 0, limit: 60, offset: 0 }
const sleepLog = {
  id: 's1',
  sleep_date: '2026-06-01',
  bedtime: new Date(2026, 5, 1, 23, 0).toISOString(),
  wake_time: new Date(2026, 5, 2, 7, 0).toISOString(),
  duration_minutes: 480,
  quality: 4,
  awakenings: 1,
  notes: null,
}

function renderPage(authRequest, { lang = 'en', path = '/daily' } = {}) {
  localStorage.setItem('namat-lang', lang)
  return render(
    <I18nProvider>
      <AuthContext.Provider value={{ authRequest }}>
        <MemoryRouter initialEntries={[path]}>
          <DailyLogPage />
        </MemoryRouter>
      </AuthContext.Provider>
    </I18nProvider>,
  )
}

describe('DailyLogPage', () => {
  it('lists sleep records with what was recorded', async () => {
    renderPage(vi.fn().mockResolvedValue({ ...empty, items: [sleepLog], total: 1 }))
    expect(await screen.findByText('Night of Jun 1, 2026')).toBeTruthy()
    expect(screen.getByText(/8 hr · Slept: Well · woke 1 time/)).toBeTruthy()
  })

  it('adds a night of sleep and shows it was saved', async () => {
    const authRequest = vi.fn().mockResolvedValueOnce(empty).mockResolvedValueOnce(sleepLog).mockResolvedValue({ ...empty, items: [sleepLog], total: 1 })
    renderPage(authRequest)
    fireEvent.click(await screen.findByRole('button', { name: 'Add a night' }))
    fireEvent.change(screen.getByLabelText('Night of'), { target: { value: '2026-06-01' } })
    fireEvent.click(screen.getByRole('radio', { name: 'Well' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Saved.')).toBeTruthy()
    const [path, options] = authRequest.mock.calls[1]
    expect(path).toBe('/sleep-logs')
    expect(options.method).toBe('POST')
    expect(options.body).toMatchObject({ sleep_date: '2026-06-01', quality: 4, awakenings: null })
  })

  it('keeps the entry and explains a duplicate date', async () => {
    const authRequest = vi.fn().mockResolvedValueOnce(empty).mockRejectedValueOnce(new ApiError('errors.duplicateDate', 409))
    renderPage(authRequest)
    fireEvent.click(await screen.findByRole('button', { name: 'Add a night' }))
    fireEvent.change(screen.getByLabelText('Night of'), { target: { value: '2026-06-01' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText(/already an entry for this date/)).toBeTruthy()
    expect(screen.getByLabelText('Night of').value).toBe('2026-06-01')
  })

  it('switches to daily factors and validates an empty day', async () => {
    const authRequest = vi.fn().mockResolvedValue(empty)
    renderPage(authRequest)
    fireEvent.click(await screen.findByRole('tab', { name: 'Daily factors' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Add a day' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(screen.getByText('Record at least one factor or a note.')).toBeTruthy()
    expect(authRequest).toHaveBeenLastCalledWith('/daily-factors?limit=60&offset=0', expect.anything())
  })

  it('shows an error with a working retry', async () => {
    const authRequest = vi.fn().mockRejectedValueOnce(new ApiError('errors.network', 0)).mockResolvedValue(empty)
    renderPage(authRequest)
    fireEvent.click(await screen.findByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('No sleep records yet')).toBeTruthy()
  })

  it('works in Arabic, right to left', async () => {
    renderPage(vi.fn().mockResolvedValue(empty), { lang: 'ar' })
    expect(document.documentElement.dir).toBe('rtl')
    expect(await screen.findByText('لا توجد سجلات نوم بعد')).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'العوامل اليومية' })).toBeTruthy()
  })
})
