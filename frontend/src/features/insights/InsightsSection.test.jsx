// Run from frontend/ with:  npm test
// The API is replaced by a fake authRequest; everything else (translations,
// components, the request hook) is the real code. All data is synthetic.

import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../api.js'
import { AuthContext } from '../../auth/auth-context.js'
import I18nProvider from '../../i18n/I18nProvider.jsx'
import InsightsSection from './InsightsSection.jsx'

afterEach(() => {
  cleanup()
  localStorage.clear()
})

const insight = (overrides) => ({
  date_range: { start: '2026-06-01', end: '2026-06-30' },
  comparison: null,
  title: 'English fallback title',
  description: 'English fallback description',
  ...overrides,
})

const SLEEP = insight({
  id: 'sleep_rate_higher',
  category: 'sleep',
  evidence: {
    median_hours: 6.5,
    shorter_nights: 5,
    other_nights: 6,
    shorter_headache_rate: 1,
    other_headache_rate: 0,
    shorter_avg_intensity: null,
    other_avg_intensity: null,
    comparison_type: 'rate',
    direction: 'higher',
  },
  sample_size: 11,
  evidence_level: 'observed',
})

const FREQUENCY = insight({
  id: 'frequency_increase',
  category: 'frequency',
  evidence: { current: 7, previous: 3, days: 30 },
  sample_size: 10,
  evidence_level: 'limited',
})

function response(overrides = {}) {
  return {
    period: { period: '30d', start: '2026-06-01', end: '2026-06-30', days: 30, timezone: 'UTC' },
    previous_period: { start: '2026-05-02', end: '2026-05-31' },
    data_status: 'sufficient',
    summary: {
      total_episodes: 7,
      headache_days: 7,
      episodes_per_week: 1.6,
      average_intensity: 6.1,
      highest_intensity: 8,
      rated_episodes: 7,
      intensity_distribution: { moderate: 4, severe: 3 },
      time_of_day: { morning: 1, afternoon: 0, evening: 6, night: 0 },
      average_sleep_hours: 6.5,
      sleep_nights: 11,
      factor_days: 0,
    },
    insights: [SLEEP, FREQUENCY],
    data_gaps: [],
    generated_at: '2026-06-30T12:00:00Z',
    ...overrides,
  }
}

function renderSection({ authRequest, filters = { period: '30d' }, lang = 'en' }) {
  localStorage.setItem('namat-lang', lang)
  const ui = (f) => (
    <I18nProvider>
      <AuthContext.Provider value={{ authRequest }}>
        <MemoryRouter>
          <InsightsSection filters={f} />
        </MemoryRouter>
      </AuthContext.Provider>
    </I18nProvider>
  )
  const utils = render(ui(filters))
  return { ...utils, rerenderWith: (f) => utils.rerender(ui(f)) }
}

describe('InsightsSection', () => {
  it('shows a loading state, then insights built from the API values', async () => {
    const authRequest = vi.fn().mockResolvedValue(response())
    renderSection({ authRequest })

    expect(screen.getByText('Looking for patterns…')).toBeTruthy()
    expect(await screen.findByText('A sleep pattern in your records')).toBeTruthy()
    expect(screen.getByText(/100% of days after shorter sleep \(under 6\.5 h\)/)).toBeTruthy()
    expect(screen.getByText('More episodes than the previous period')).toBeTruthy()
    expect(screen.getByText(/7 episodes in this period, and 3 episodes in the 30 days before/)).toBeTruthy()
    expect(screen.getByText('Based on 11 days')).toBeTruthy()
    expect(screen.getAllByText('Limited evidence').length).toBeGreaterThan(0)
    expect(authRequest).toHaveBeenCalledWith('/insights?period=30d', expect.objectContaining({ signal: expect.any(AbortSignal) }))
  })

  it('shows the insufficient-data state with the real counts', async () => {
    const authRequest = vi.fn().mockResolvedValue(
      response({
        data_status: 'insufficient',
        insights: [],
        data_gaps: [
          { code: 'episodes', needed: 3, have: 1 },
          { code: 'sleep', needed: 7, have: 0 },
        ],
      }),
    )
    renderSection({ authRequest })
    expect(await screen.findByText('Not enough records for patterns yet')).toBeTruthy()
    expect(screen.getByText(/at least 3 episodes in the selected period\. You have 1 so far/)).toBeTruthy()
    expect(screen.getByText(/Sleep comparisons need at least 7 nights/)).toBeTruthy()
  })

  it('shows an honest empty state when nothing stood out', async () => {
    const authRequest = vi.fn().mockResolvedValue(response({ insights: [] }))
    renderSection({ authRequest })
    expect(await screen.findByText('No clear patterns in this period')).toBeTruthy()
    expect(screen.queryByRole('article')).toBeNull()
  })

  it('shows an error with a working retry, never demo data', async () => {
    const authRequest = vi
      .fn()
      .mockRejectedValueOnce(new ApiError('errors.network', 0))
      .mockResolvedValueOnce(response())
    renderSection({ authRequest })
    expect(await screen.findByText('We couldn’t load your insights')).toBeTruthy()
    expect(screen.queryByRole('article')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('A sleep pattern in your records')).toBeTruthy()
    expect(authRequest).toHaveBeenCalledTimes(2)
  })

  it('reloads for a new date filter and cancels the outdated request', async () => {
    let firstSignal
    const authRequest = vi.fn((path, { signal }) => {
      if (path.endsWith('period=30d')) {
        firstSignal = signal
        return new Promise(() => {}) // still pending when the filter changes
      }
      return Promise.resolve(response({ period: { ...response().period, period: '6m', days: 180 } }))
    })
    const { rerenderWith } = renderSection({ authRequest })
    await act(async () => rerenderWith({ period: '6m' }))
    expect(await screen.findByText('A sleep pattern in your records')).toBeTruthy()
    expect(authRequest).toHaveBeenLastCalledWith('/insights?period=6m', expect.anything())
    expect(firstSignal.aborted).toBe(true)
  })

  it('sends custom ranges as start_date and end_date', async () => {
    const authRequest = vi.fn().mockResolvedValue(response())
    renderSection({ authRequest, filters: { period: 'custom', start: '2026-06-01', end: '2026-06-30' } })
    await screen.findByText('A sleep pattern in your records')
    expect(authRequest).toHaveBeenCalledWith('/insights?start_date=2026-06-01&end_date=2026-06-30', expect.anything())
  })

  it('renders in Arabic, right to left', async () => {
    const authRequest = vi.fn().mockResolvedValue(response())
    renderSection({ authRequest, lang: 'ar' })
    expect(await screen.findByText('نمط في نومك حسب سجلاتك')).toBeTruthy()
    expect(screen.getByText('ملاحظات من سجلاتك')).toBeTruthy()
    expect(screen.getByText('نوبات أكثر من الفترة السابقة')).toBeTruthy()
    expect(document.documentElement.dir).toBe('rtl')
    expect(document.documentElement.lang).toBe('ar')
  })

  it('treats user-entered text as text, never HTML', async () => {
    const authRequest = vi.fn().mockResolvedValue(
      response({
        insights: [
          insight({
            id: 'medication_summary',
            category: 'medication',
            evidence: {
              doses: 2,
              top_medication: '<img src=x onerror=alert(1)>',
              top_medication_doses: 2,
              episodes_with_medication: 2,
              total_episodes: 3,
            },
            sample_size: 2,
            evidence_level: 'limited',
          }),
        ],
      }),
    )
    const { container } = renderSection({ authRequest })
    expect(await screen.findByText(/<img src=x onerror=alert\(1\)>/)).toBeTruthy()
    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText(/doesn’t show whether a medication helped/)).toBeTruthy()
  })

  it('skips insight types this app version cannot describe', async () => {
    const authRequest = vi.fn().mockResolvedValue(
      response({ insights: [SLEEP, insight({ id: 'future_kind', category: 'unknown', evidence: {}, sample_size: 1, evidence_level: 'limited' })] }),
    )
    renderSection({ authRequest })
    await screen.findByText('A sleep pattern in your records')
    expect(screen.getAllByRole('article')).toHaveLength(1)
    expect(screen.queryByText('English fallback title')).toBeNull()
  })

  it('shows four insights first and the rest on request', async () => {
    const many = ['morning', 'afternoon', 'evening', 'night', 'morning'].map((part, i) =>
      insight({
        id: `time_of_day_${part}_${i}`,
        category: 'timing',
        evidence: { part_of_day: part, count: 5, total: 6, counts: { morning: 5, afternoon: 1, evening: 0, night: 0 } },
        sample_size: 6,
        evidence_level: 'limited',
      }),
    )
    const authRequest = vi.fn().mockResolvedValue(response({ insights: many }))
    renderSection({ authRequest })
    await screen.findAllByRole('article')
    expect(screen.getAllByRole('article')).toHaveLength(4)
    fireEvent.click(screen.getByRole('button', { name: 'Show all (5)' }))
    expect(screen.getAllByRole('article')).toHaveLength(5)
  })
})
