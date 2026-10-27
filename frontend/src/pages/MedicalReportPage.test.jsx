// Run from frontend/ with:  npm test
// The API is replaced by a fake authRequest; translations, components and the
// page logic are the real code. All data is synthetic.

import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api.js'
import { AuthContext } from '../auth/auth-context.js'
import I18nProvider from '../i18n/I18nProvider.jsx'
import MedicalReportPage from './MedicalReportPage.jsx'

afterEach(() => {
  cleanup()
  localStorage.clear()
  vi.restoreAllMocks()
})

function report({ lang = 'en', episodes = 2 } = {}) {
  const ar = lang === 'ar'
  return {
    language: lang,
    direction: ar ? 'rtl' : 'ltr',
    title: ar ? 'التقرير الطبي للصداع' : 'Headache medical report',
    subtitle: ar ? 'أُعدّ من السجلات المحفوظة في نمط' : 'Prepared from the records kept in Namat',
    period_label: ar ? '1 يونيو 2026 – 30 يونيو 2026' : '1 Jun 2026 – 30 Jun 2026',
    generated_at: '2026-07-01T09:00:00Z',
    generated_label: '1 Jul 2026',
    data: {
      overview: { total_episodes: episodes },
      sleep: { nights: 0 },
      factors: { days: 0 },
      medication: { doses: 0 },
    },
    sections: [
      {
        id: 'overview',
        title: ar ? 'نظرة عامة على الصداع' : 'Headache overview',
        blocks: [{ type: 'facts', items: [{ label: 'Recorded episodes', value: String(episodes) }] }],
      },
      {
        id: 'history',
        title: 'Episode history',
        blocks: [
          {
            type: 'episode',
            number: 1,
            heading: 'Episode 1 · Tue 2 Jun 2026',
            fields: [{ label: 'Peak intensity', value: 'Not recorded' }],
            notes_label: 'Notes',
            notes: '<img src=x onerror=alert(1)> صداع بعد العمل',
          },
        ],
      },
      {
        id: 'symptoms',
        title: 'Associated symptoms',
        blocks: [{ type: 'table', title: null, columns: [{ label: 'Symptom', width: 4 }], rows: [['Nausea']] }],
      },
      {
        id: 'observations',
        title: 'Key observations',
        blocks: [
          {
            type: 'observation',
            id: 'time_of_day_morning',
            category: 'timing',
            level: 'observed',
            level_label: 'Observed pattern',
            title: 'Most episodes started in the morning',
            description: '9 of your 16 episodes started in the morning.',
            facts: [{ label: 'Based on', value: '16 episodes' }],
            limitation: 'An association in the recorded data only.',
          },
          { type: 'mystery', text: 'never shown' },
        ],
      },
      { id: 'disclaimer', title: 'Medical disclaimer', blocks: [{ type: 'callout', text: 'This report is generated…' }] },
    ],
  }
}

function renderPage({ authRequest, lang = 'en' }) {
  localStorage.setItem('namat-lang', lang)
  return render(
    <I18nProvider>
      <AuthContext.Provider value={{ authRequest }}>
        <MemoryRouter>
          <MedicalReportPage />
        </MemoryRouter>
      </AuthContext.Provider>
    </I18nProvider>,
  )
}

describe('MedicalReportPage', () => {
  it('waits for the user, then generates and previews the whole report', async () => {
    const authRequest = vi.fn().mockResolvedValue(report())
    renderPage({ authRequest })

    expect(screen.getByText('Choose a period and a language')).toBeTruthy()
    expect(authRequest).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: 'Download PDF' })).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Generate report' }))
    expect(await screen.findByRole('heading', { name: 'Headache medical report' })).toBeTruthy()
    expect(authRequest).toHaveBeenCalledWith('/reports/medical?lang=en&period=3m', expect.objectContaining({ signal: expect.any(AbortSignal) }))

    for (const title of ['Headache overview', 'Episode history', 'Associated symptoms', 'Key observations', 'Medical disclaimer']) {
      expect(screen.getByRole('heading', { name: title })).toBeTruthy()
    }
    expect(screen.getByText('Observed pattern')).toBeTruthy()
    expect(screen.getByText('Not recorded')).toBeTruthy()
    expect(screen.queryByText('never shown')).toBeNull() // unknown blocks are skipped
  })

  it('renders typed notes as plain text in their own direction', async () => {
    renderPage({ authRequest: vi.fn().mockResolvedValue(report()) })
    fireEvent.click(screen.getByRole('button', { name: 'Generate report' }))
    const note = await screen.findByText(/<img src=x onerror=alert\(1\)>/)
    expect(note.getAttribute('dir')).toBe('auto')
    expect(document.querySelector('img')).toBeNull()
  })

  it('sends the chosen period and language, and shows an Arabic report right to left', async () => {
    const authRequest = vi.fn().mockResolvedValue(report({ lang: 'ar' }))
    renderPage({ authRequest })

    fireEvent.click(screen.getByRole('radio', { name: '6 months' }))
    fireEvent.click(screen.getByRole('radio', { name: 'العربية' }))
    fireEvent.click(screen.getByRole('button', { name: 'Generate report' }))

    const heading = await screen.findByRole('heading', { name: 'التقرير الطبي للصداع' })
    expect(authRequest).toHaveBeenCalledWith('/reports/medical?lang=ar&period=6m', expect.anything())
    const article = heading.closest('article')
    expect(article.getAttribute('dir')).toBe('rtl')
    expect(article.getAttribute('lang')).toBe('ar')
    // The page around it stays in the interface language.
    expect(document.documentElement.dir).toBe('ltr')
  })

  it('shows the Arabic interface right to left', async () => {
    renderPage({ authRequest: vi.fn().mockResolvedValue(report({ lang: 'ar' })), lang: 'ar' })
    expect(document.documentElement.dir).toBe('rtl')
    expect(screen.getByRole('heading', { name: 'التقرير الطبي', level: 1 })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'إنشاء التقرير' }))
    expect(await screen.findByRole('heading', { name: 'التقرير الطبي للصداع' })).toBeTruthy()
  })

  it('shows an error with a working retry', async () => {
    const authRequest = vi.fn().mockRejectedValueOnce(new ApiError('errors.server', 500)).mockResolvedValueOnce(report())
    renderPage({ authRequest })
    fireEvent.click(screen.getByRole('button', { name: 'Generate report' }))
    expect(await screen.findByText('The report couldn’t be prepared')).toBeTruthy()
    expect(screen.getByText('The server had a problem. Please try again later.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('heading', { name: 'Headache medical report' })).toBeTruthy()
  })

  it('downloads the PDF of the report on screen from the backend', async () => {
    const pdf = { blob: new Blob(['%PDF-1.7'], { type: 'application/pdf' }), filename: 'namat-medical-report-2026-06-01-to-2026-06-30-en.pdf' }
    const authRequest = vi.fn((path) => Promise.resolve(path.startsWith('/reports/medical/pdf') ? pdf : report()))
    URL.createObjectURL = vi.fn(() => 'blob:report')
    URL.revokeObjectURL = vi.fn()
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    renderPage({ authRequest })

    fireEvent.click(screen.getByRole('button', { name: 'Generate report' }))
    await screen.findByRole('heading', { name: 'Headache medical report' })
    // Changing the options afterwards doesn't change what the PDF contains.
    fireEvent.click(screen.getByRole('radio', { name: '7 days' }))
    expect(screen.getByText(/You changed the period or language/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Download PDF' }))

    await vi.waitFor(() => expect(click).toHaveBeenCalled())
    expect(authRequest).toHaveBeenCalledWith('/reports/medical/pdf?lang=en&period=3m', { responseType: 'file' })
    expect(URL.createObjectURL).toHaveBeenCalledWith(pdf.blob)
    const link = click.mock.contexts[0]
    expect(link.download).toBe(pdf.filename)
  })

  it('explains a failed download', async () => {
    const authRequest = vi.fn((path) =>
      path.startsWith('/reports/medical/pdf') ? Promise.reject(new ApiError('errors.network', 0)) : Promise.resolve(report()),
    )
    renderPage({ authRequest })
    fireEvent.click(screen.getByRole('button', { name: 'Generate report' }))
    await screen.findByRole('heading', { name: 'Headache medical report' })
    fireEvent.click(screen.getByRole('button', { name: 'Download PDF' }))
    const alert = await screen.findByRole('alert')
    expect(within(alert).getByText('The PDF couldn’t be downloaded')).toBeTruthy()
  })

  it('warns when nothing was recorded in the period', async () => {
    renderPage({ authRequest: vi.fn().mockResolvedValue(report({ episodes: 0 })) })
    fireEvent.click(screen.getByRole('button', { name: 'Generate report' }))
    expect(await screen.findByText('Nothing was recorded in this period')).toBeTruthy()
  })

  it('keeps wide tables scrollable inside their own box on phones', async () => {
    renderPage({ authRequest: vi.fn().mockResolvedValue(report()) })
    fireEvent.click(screen.getByRole('button', { name: 'Generate report' }))
    const cell = await screen.findByRole('cell', { name: 'Nausea' })
    expect(cell.closest('div').className).toContain('overflow-x-auto')
  })
})
