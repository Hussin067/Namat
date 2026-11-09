// Run from frontend/ with:  npm test
// The API is replaced by a fake authRequest; the page, forms and translations are real.

import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api.js'
import { AuthContext } from '../auth/auth-context.js'
import MedicalHistoryContext from '../features/medical/MedicalHistoryContext.jsx'
import ReportPreview from '../features/reports/ReportPreview.jsx'
import I18nProvider from '../i18n/I18nProvider.jsx'
import MedicalHistoryPage from './MedicalHistoryPage.jsx'

// jsdom has no modal dialogs; enough of one for ConfirmDialog.
beforeAll(() => {
  HTMLDialogElement.prototype.showModal ??= function showModal() {
    this.open = true
  }
  HTMLDialogElement.prototype.close ??= function close() {
    this.open = false
  }
})

afterEach(() => {
  cleanup()
  localStorage.clear()
})

const empty = { conditions: [], allergies: [], procedures: [], notes: { notes: null, updated_at: null } }
const stamp = { created_at: '2026-06-01T08:00:00Z', updated_at: '2026-06-01T08:00:00Z' }
const migraine = {
  id: 'c1',
  condition_name: 'Migraine with aura',
  category: 'headache_disorder',
  status: 'active',
  confirmation: 'clinician_confirmed',
  diagnosis_date: '2019-05-10',
  notes: null,
  ...stamp,
}
const sinusitis = {
  id: 'c2',
  condition_name: 'Sinusitis',
  category: 'associated_condition',
  status: 'monitoring',
  confirmation: 'self_reported',
  diagnosis_date: null,
  notes: null,
  ...stamp,
}
const meningitis = {
  id: 'c3',
  condition_name: 'Meningitis',
  category: 'serious_history',
  status: 'resolved',
  confirmation: 'unsure',
  diagnosis_date: null,
  notes: null,
  ...stamp,
}
const allergy = { id: 'a1', name: 'Penicillin', type: 'medication', reaction: 'Rash', severity: 'moderate', notes: null, ...stamp }
const full = { ...empty, conditions: [migraine, sinusitis, meningitis], allergies: [allergy] }

function renderWith(ui, authRequest, lang = 'en') {
  localStorage.setItem('namat-lang', lang)
  return render(
    <I18nProvider>
      <AuthContext.Provider value={{ authRequest }}>
        <MemoryRouter>{ui}</MemoryRouter>
      </AuthContext.Provider>
    </I18nProvider>,
  )
}

const renderPage = (authRequest, lang) => renderWith(<MedicalHistoryPage />, authRequest, lang)
const card = (name) => screen.getByRole('region', { name })

describe('MedicalHistoryPage', () => {
  it('shows a loading state, then six cards with empty states', async () => {
    renderPage(vi.fn().mockResolvedValue(empty))
    expect(screen.getByText('Loading your medical history…')).toBeTruthy()
    expect(await screen.findByText('No conditions added')).toBeTruthy()
    for (const title of [
      'Chronic diseases and serious past illnesses',
      'Diagnosed headache disorders',
      'Associated conditions',
      'Allergies',
      'Surgeries and procedures',
      'Additional notes',
    ])
      expect(screen.getByRole('heading', { name: title })).toBeTruthy()
    expect(screen.getByText('No allergies added')).toBeTruthy()
    expect(screen.getByText('No surgeries or procedures added')).toBeTruthy()
  })

  it('lists items in their own cards with clear confirmation labels', async () => {
    renderPage(vi.fn().mockResolvedValue(full))
    const headache = await screen.findByRole('region', { name: 'Diagnosed headache disorders' })
    expect(within(headache).getByText('Migraine with aura')).toBeTruthy()
    expect(within(headache).getByText('Clinician-confirmed')).toBeTruthy()
    expect(within(headache).getByText('Active · Since May 10, 2019')).toBeTruthy()
    const associated = card('Associated conditions')
    expect(within(associated).getByText('Sinusitis')).toBeTruthy()
    expect(within(associated).getByText('Self-reported')).toBeTruthy()
    // Meningitis is a serious past illness, never an associated condition.
    const chronic = card('Chronic diseases and serious past illnesses')
    expect(within(chronic).getByText('Meningitis')).toBeTruthy()
    expect(within(chronic).getByText('Serious past illness')).toBeTruthy()
    expect(within(associated).queryByText('Meningitis')).toBeNull()
    expect(within(card('Allergies')).getByText('Reaction:')).toBeTruthy()
  })

  it('never offers meningitis as an associated condition', async () => {
    renderPage(vi.fn().mockResolvedValue(empty))
    const associated = await screen.findByRole('region', { name: 'Associated conditions' })
    fireEvent.click(within(associated).getByRole('button', { name: 'Add a condition' }))
    const options = within(associated).getAllByRole('option').map((o) => o.textContent)
    expect(options).toContain('High blood pressure')
    expect(options).toContain('Other (type your own)')
    expect(options).not.toContain('Meningitis')
  })

  it('adds a headache disorder from the predefined list', async () => {
    const authRequest = vi.fn().mockResolvedValueOnce(empty).mockResolvedValueOnce(migraine).mockResolvedValue({ ...empty, conditions: [migraine] })
    renderPage(authRequest)
    const headache = await screen.findByRole('region', { name: 'Diagnosed headache disorders' })
    fireEvent.click(within(headache).getByRole('button', { name: 'Add a headache disorder' }))
    fireEvent.change(within(headache).getByLabelText('Condition'), { target: { value: 'migraine_with_aura' } })
    fireEvent.click(within(headache).getByRole('radio', { name: 'Confirmed by a clinician' }))
    fireEvent.change(within(headache).getByLabelText(/When it was diagnosed/), { target: { value: '2019-05-10' } })
    fireEvent.click(within(headache).getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Saved.')).toBeTruthy()
    const [path, options] = authRequest.mock.calls[1]
    expect(path).toBe('/medical-history/conditions')
    expect(options.method).toBe('POST')
    expect(options.body).toEqual({
      condition_name: 'Migraine with aura',
      category: 'headache_disorder',
      status: 'active',
      confirmation: 'clinician_confirmed',
      diagnosis_date: '2019-05-10',
      notes: null,
    })
    expect(await within(headache).findByText('Migraine with aura')).toBeTruthy()
  })

  it('adds a serious past illness with a custom name', async () => {
    const authRequest = vi.fn().mockResolvedValueOnce(empty).mockResolvedValueOnce({}).mockResolvedValue(empty)
    renderPage(authRequest)
    const chronic = await screen.findByRole('region', { name: 'Chronic diseases and serious past illnesses' })
    fireEvent.click(within(chronic).getByRole('button', { name: 'Add a condition' }))
    fireEvent.click(within(chronic).getByRole('radio', { name: 'Serious past illness' }))
    fireEvent.change(within(chronic).getByLabelText('Condition'), { target: { value: 'custom' } })
    fireEvent.change(within(chronic).getByLabelText('Name of the condition'), { target: { value: '  Rare illness ' } })
    fireEvent.click(within(chronic).getByRole('radio', { name: 'Resolved' }))
    fireEvent.click(within(chronic).getByRole('button', { name: 'Save' }))
    await screen.findByText('Saved.')
    expect(authRequest.mock.calls[1][1].body).toMatchObject({
      condition_name: 'Rare illness',
      category: 'serious_history',
      status: 'resolved',
      confirmation: 'self_reported',
      diagnosis_date: null,
    })
  })

  it('validates before sending anything', async () => {
    const authRequest = vi.fn().mockResolvedValue(empty)
    renderPage(authRequest)
    const headache = await screen.findByRole('region', { name: 'Diagnosed headache disorders' })
    fireEvent.click(within(headache).getByRole('button', { name: 'Add a headache disorder' }))
    fireEvent.click(within(headache).getByRole('button', { name: 'Save' }))
    expect(within(headache).getByText('Choose a condition, or “Other” to type your own.')).toBeTruthy()

    fireEvent.change(within(headache).getByLabelText('Condition'), { target: { value: 'custom' } })
    fireEvent.click(within(headache).getByRole('button', { name: 'Save' }))
    expect(within(headache).getByText('Enter a name.')).toBeTruthy()

    fireEvent.change(within(headache).getByLabelText('Name of the condition'), { target: { value: 'x' } })
    fireEvent.change(within(headache).getByLabelText(/When it was diagnosed/), { target: { value: '2999-01-01' } })
    fireEvent.click(within(headache).getByRole('button', { name: 'Save' }))
    expect(within(headache).getByText('The date can’t be in the future.')).toBeTruthy()
    expect(authRequest).toHaveBeenCalledTimes(1) // only the initial load
  })

  it('explains when a sinus headache should be chosen', async () => {
    renderPage(vi.fn().mockResolvedValue(empty))
    const headache = await screen.findByRole('region', { name: 'Diagnosed headache disorders' })
    fireEvent.click(within(headache).getByRole('button', { name: 'Add a headache disorder' }))
    fireEvent.change(within(headache).getByLabelText('Condition'), { target: { value: 'sinus_headache' } })
    expect(within(headache).getByText(/only if a clinician identified it/)).toBeTruthy()
  })

  it('edits an item and keeps it on failure', async () => {
    const authRequest = vi.fn().mockResolvedValueOnce(full).mockRejectedValueOnce(new ApiError('errors.network', 0)).mockResolvedValueOnce(allergy).mockResolvedValue(full)
    renderPage(authRequest)
    const allergies = await screen.findByRole('region', { name: 'Allergies' })
    fireEvent.click(within(allergies).getByRole('button', { name: 'Edit Penicillin' }))
    expect(within(allergies).getByLabelText('Allergic to').value).toBe('Penicillin')
    fireEvent.click(within(allergies).getByRole('radio', { name: 'Severe' }))
    fireEvent.click(within(allergies).getByRole('button', { name: 'Save changes' }))
    expect(await within(allergies).findByText('This wasn’t saved')).toBeTruthy()
    expect(within(allergies).getByRole('radio', { name: 'Severe' }).checked).toBe(true)

    fireEvent.click(within(allergies).getByRole('button', { name: 'Save changes' }))
    expect(await screen.findByText('Changes saved.')).toBeTruthy()
    const [path, options] = authRequest.mock.calls[2]
    expect(path).toBe('/medical-history/allergies/a1')
    expect(options).toMatchObject({ method: 'PATCH', body: { name: 'Penicillin', severity: 'severe', reaction: 'Rash' } })
  })

  it('asks before deleting, then deletes', async () => {
    const authRequest = vi.fn().mockResolvedValueOnce(full).mockResolvedValueOnce(undefined).mockResolvedValue(empty)
    renderPage(authRequest)
    fireEvent.click(await screen.findByRole('button', { name: 'Delete Migraine with aura' }))
    expect(screen.getByText(/“Migraine with aura” will be removed/)).toBeTruthy()
    expect(authRequest).toHaveBeenCalledTimes(1)
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete' }))
    expect(await screen.findByText('Deleted.')).toBeTruthy()
    expect(authRequest.mock.calls[1]).toEqual(['/medical-history/conditions/c1', { method: 'DELETE' }])
  })

  it('saves additional notes with PUT', async () => {
    const authRequest = vi.fn().mockResolvedValueOnce(empty).mockResolvedValueOnce({ notes: 'Family history.', updated_at: stamp.updated_at })
    renderPage(authRequest)
    fireEvent.change(await screen.findByLabelText(/Notes for your doctor/), { target: { value: 'Family history. ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save notes' }))
    expect(await screen.findByText('Notes saved.')).toBeTruthy()
    expect(authRequest.mock.calls[1]).toEqual(['/medical-history/notes', { method: 'PUT', body: { notes: 'Family history.' } }])
  })

  it('shows an error with a working retry', async () => {
    const authRequest = vi.fn().mockRejectedValueOnce(new ApiError('errors.network', 0)).mockResolvedValue(empty)
    renderPage(authRequest)
    expect(await screen.findByText('We couldn’t load your medical history')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('No conditions added')).toBeTruthy()
  })

  it('works in Arabic, right to left, with translated names and labels', async () => {
    renderPage(vi.fn().mockResolvedValue(full), 'ar')
    expect(document.documentElement.dir).toBe('rtl')
    expect(await screen.findByText('الصداع النصفي مع هالة')).toBeTruthy()
    expect(screen.getByText('مؤكَّدة من طبيب')).toBeTruthy()
    expect(screen.getAllByText('إبلاغ ذاتي').length).toBeGreaterThan(0)
    expect(screen.getByText('Penicillin')).toBeTruthy() // typed text stays as typed
    expect(screen.getByRole('heading', { name: 'التاريخ المرضي' })).toBeTruthy()
  })
})

describe('MedicalHistoryContext (dashboard)', () => {
  it('describes only what was reported, without conclusions', async () => {
    renderWith(<MedicalHistoryContext />, vi.fn().mockResolvedValue(full))
    expect(await screen.findByText('You reported a history of Migraine with aura and Sinusitis.')).toBeTruthy()
    expect(screen.getByText(/Discuss this information with your healthcare professional/)).toBeTruthy()
    expect(screen.queryByText(/Meningitis/)).toBeNull() // resolved serious illness isn't listed
  })

  it('shows nothing when there is nothing current to mention', async () => {
    const authRequest = vi.fn().mockResolvedValue({ ...empty, conditions: [meningitis] })
    const { container } = renderWith(<MedicalHistoryContext />, authRequest)
    await vi.waitFor(() => expect(authRequest).toHaveBeenCalled())
    await Promise.resolve()
    expect(container.textContent).toBe('')
  })
})

describe('ReportPreview medical history', () => {
  it('renders reported items with their status and confirmation', () => {
    const report = {
      language: 'en',
      direction: 'ltr',
      title: 'Headache medical report',
      subtitle: '',
      period_label: '',
      sections: [
        {
          id: 'medical_history',
          title: 'Medical history (reported by you)',
          blocks: [
            {
              type: 'history_item',
              name: 'Migraine with aura',
              fields: [{ label: 'Confirmation', value: 'Confirmed by a clinician (as you reported)' }],
              details: [{ label: 'Notes', text: 'Visual aura.' }],
            },
          ],
        },
      ],
    }
    renderWith(<ReportPreview report={report} />, vi.fn())
    expect(screen.getByRole('heading', { name: 'Medical history (reported by you)' })).toBeTruthy()
    expect(screen.getByText('Confirmed by a clinician (as you reported)')).toBeTruthy()
    expect(screen.getByText('Visual aura.').getAttribute('dir')).toBe('auto')
  })
})
