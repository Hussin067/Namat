import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import ar from '../../i18n/messages/ar.js'
import en from '../../i18n/messages/en.js'
import { conditionFormFrom, emptyConditionForm, toConditionPayload, validateConditionForm, validateNotes } from './medicalForms.js'
import { OPTIONS, codeOf, displayName } from './medicalOptions.js'

const NOW = new Date(2026, 5, 15)

describe('medical history forms', () => {
  it('stores a predefined name in English and a typed one as typed', () => {
    const form = { ...emptyConditionForm('associated_condition'), choice: 'hypertension' }
    expect(toConditionPayload(form).condition_name).toBe('High blood pressure')
    const typed = { ...form, choice: 'custom', customName: '  Something rare ' }
    expect(toConditionPayload(typed).condition_name).toBe('Something rare')
  })

  it('reopens a stored item on the right choice', () => {
    const base = { category: 'headache_disorder', status: 'active', confirmation: 'unsure', diagnosis_date: null, notes: null }
    expect(conditionFormFrom({ ...base, condition_name: 'Cluster headache' }).choice).toBe('cluster')
    const typed = conditionFormFrom({ ...base, condition_name: 'My own words' })
    expect(typed).toMatchObject({ choice: 'custom', customName: 'My own words' })
  })

  it('validates names, dates and lengths', () => {
    const form = emptyConditionForm('chronic_disease')
    expect(validateConditionForm(form, NOW)).toEqual({ name: 'medical.errors.chooseName' })
    expect(validateConditionForm({ ...form, choice: 'custom', customName: 'x'.repeat(121) }, NOW).name).toBe('medical.errors.nameTooLong')
    expect(validateConditionForm({ ...form, choice: 'asthma', date: '2026-06-20' }, NOW).date).toBe('medical.errors.dateFuture')
    expect(validateConditionForm({ ...form, choice: 'asthma', date: '1850-01-01' }, NOW).date).toBe('medical.errors.dateTooOld')
    expect(validateConditionForm({ ...form, choice: 'asthma', date: '2026-06-15' }, NOW)).toEqual({})
    expect(validateNotes('x'.repeat(4001))).toBe('medical.errors.additionalNotesTooLong')
  })

  it('keeps serious past illnesses out of the associated conditions', () => {
    expect(OPTIONS.serious_history).toContain('meningitis')
    expect(OPTIONS.associated_condition).not.toContain('meningitis')
    expect(OPTIONS.headache_disorder).not.toContain('meningitis')
  })

  it('has every predefined name in both languages', () => {
    for (const code of Object.values(OPTIONS).flat()) {
      expect(en.medical.names[code]).toBeTruthy()
      expect(ar.medical.names[code]).toBeTruthy()
      expect(codeOf(en.medical.names[code])).toBe(code)
    }
    expect(displayName('Anemia', (key) => (key === 'medical.names.anemia' ? 'فقر الدم' : key))).toBe('فقر الدم')
    expect(displayName('Typed by me', () => 'never')).toBe('Typed by me')
  })

  it('uses the same names and Arabic translations as the PDF report', () => {
    const text = fs.readFileSync(path.resolve(process.cwd(), '../backend/app/reports/text.py'), 'utf8')
    for (const code of Object.values(OPTIONS).flat()) {
      expect(text).toContain(`"${en.medical.names[code]}": "${ar.medical.names[code]}"`)
    }
  })
})
