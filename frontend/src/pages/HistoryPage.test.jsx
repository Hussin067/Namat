// Run from frontend/ with:  npm test
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/auth-context.js'
import { DemoModeProvider } from '../features/episodes/DemoModeProvider.jsx'
import I18nProvider from '../i18n/I18nProvider.jsx'
import HistoryPage from './HistoryPage.jsx'

afterEach(() => {
  cleanup()
  localStorage.clear()
})

const episode = (i) => ({
  id: `e${i}`,
  started_at: new Date(2026, 5, 30 - (i % 28), 8).toISOString(),
  ended_at: null,
  peak_intensity: 5,
  pain_location: null,
  had_aura: false,
  notes: i === 0 ? '<b>plain text</b>' : null,
  symptoms: [],
  medications: [],
})

function renderPage(authRequest) {
  return render(
    <I18nProvider>
      <AuthContext.Provider value={{ authRequest }}>
        <MemoryRouter>
          <DemoModeProvider>
            <HistoryPage />
          </DemoModeProvider>
        </MemoryRouter>
      </AuthContext.Provider>
    </I18nProvider>,
  )
}

describe('HistoryPage', () => {
  it('shows the real total and loads older episodes on request', async () => {
    const authRequest = vi.fn((path) => {
      const offset = Number(new URL(path, 'http://x').searchParams.get('offset'))
      const items = Array.from({ length: offset === 0 ? 100 : 20 }, (_, i) => episode(offset + i))
      return Promise.resolve({ items, total: 120, limit: 100, offset })
    })
    renderPage(authRequest)

    expect(await screen.findByText('120 episodes, newest first')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Show older episodes' }))
    await vi.waitFor(() => expect(screen.queryByRole('button', { name: 'Show older episodes' })).toBeNull())
    expect(authRequest).toHaveBeenLastCalledWith('/episodes?limit=100&offset=100')
  })
})
