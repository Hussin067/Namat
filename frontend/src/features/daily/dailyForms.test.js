// Run from frontend/ with:  npm test
import { describe, expect, it } from 'vitest'
import {
  emptyFactorForm,
  factorFormFrom,
  sleepTimes,
  toFactorPayload,
  toSleepPayload,
  validateFactorForm,
  validateSleepForm,
} from './dailyForms.js'

const NOW = new Date(2026, 5, 20, 12, 0) // 20 June 2026, noon (local time)

describe('sleep form', () => {
  it('puts a bedtime after midnight on the next day, and wakes after bedtime', () => {
    const late = sleepTimes({ night: '2026-06-01', bedtime: '01:30', wakeTime: '08:00' })
    expect(late.bed).toEqual(new Date(2026, 5, 2, 1, 30))
    expect(late.wake).toEqual(new Date(2026, 5, 2, 8, 0))
    expect(late.minutes).toBe(390)

    const usual = sleepTimes({ night: '2026-06-01', bedtime: '23:00', wakeTime: '07:00' })
    expect(usual.bed).toEqual(new Date(2026, 5, 1, 23, 0))
    expect(usual.wake).toEqual(new Date(2026, 5, 2, 7, 0))
  })

  it('sends the night date, ISO times, and null for what was not recorded', () => {
    const payload = toSleepPayload({ night: '2026-06-01', bedtime: '23:00', wakeTime: '07:00', quality: null, awakenings: '0', notes: '  ' })
    expect(payload.sleep_date).toBe('2026-06-01')
    expect(new Date(payload.wake_time) - new Date(payload.bedtime)).toBe(8 * 3600 * 1000)
    expect(payload.quality).toBeNull()
    expect(payload.awakenings).toBe(0) // zero is a recorded value
    expect(payload.notes).toBeNull()
  })

  it('rejects future nights and impossible counts', () => {
    const base = { night: '2026-06-19', bedtime: '23:00', wakeTime: '07:00', quality: null, awakenings: '', notes: '' }
    expect(validateSleepForm(base, NOW)).toEqual({})
    expect(validateSleepForm({ ...base, night: '2026-06-25' }, NOW).night).toBe('daily.errors.dateFuture')
    expect(validateSleepForm({ ...base, night: '2026-06-20' }, NOW).wakeTime).toBe('daily.errors.wakeFuture')
    expect(validateSleepForm({ ...base, awakenings: '1.5' }, NOW).awakenings).toBe('daily.errors.awakenings')
  })
})

describe('daily-factor form', () => {
  it('keeps empty (not recorded) apart from 0 and "no"', () => {
    const form = { ...emptyFactorForm(NOW), caffeine_mg: '0', skipped_meal: false, alcohol_units: '1.5' }
    const payload = toFactorPayload(form)
    expect(payload.caffeine_mg).toBe(0)
    expect(payload.skipped_meal).toBe(false)
    expect(payload.alcohol_units).toBe(1.5)
    expect(payload.stress_level).toBeNull()
    expect(payload.water_ml).toBeNull()
    expect(payload.menstruating).toBeNull()
  })

  it('needs at least one value, and checks ranges', () => {
    expect(validateFactorForm(emptyFactorForm(NOW), NOW).form).toBe('daily.errors.nothingRecorded')
    expect(validateFactorForm({ ...emptyFactorForm(NOW), water_ml: '-5' }, NOW).water_ml).toBe('daily.errors.number')
    expect(validateFactorForm({ ...emptyFactorForm(NOW), alcohol_units: '1.25' }, NOW).alcohol_units).toBe('daily.errors.number')
    expect(validateFactorForm({ ...emptyFactorForm(NOW), menstruating: false }, NOW)).toEqual({})
  })

  it('loads a saved record back into the form without losing zeros', () => {
    const form = factorFormFrom({ log_date: '2026-06-01', stress_level: 0, caffeine_mg: null, water_ml: 1500, alcohol_units: '0.0', exercise_minutes: null, skipped_meal: null, menstruating: true, notes: null })
    expect(form.stress_level).toBe('0')
    expect(form.alcohol_units).toBe('0')
    expect(form.caffeine_mg).toBe('')
    expect(form.menstruating).toBe(true)
    expect(form.skipped_meal).toBeNull()
  })
})
