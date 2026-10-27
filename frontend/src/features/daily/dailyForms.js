// Form state, validation and API payloads for the sleep and daily-factor forms.
// Limits mirror backend/app/schemas/daily_log.py.
//
// "Not recorded" and zero are different: an empty number field is sent as
// null (not recorded), while 0 is a real value. Yes/no factors have three
// states: not recorded (null), yes (true) and no (false).

import { NOTES_MAX } from '../episodes/constants.js'

export const SLEEP_QUALITY = [1, 2, 3, 4, 5]
export const AWAKENINGS_MAX = 50

export const NUMERIC_FACTORS = [
  { name: 'caffeine_mg', max: 5000, step: 1 },
  { name: 'water_ml', max: 20000, step: 50 },
  { name: 'alcohol_units', max: 99, step: 0.5 },
  { name: 'exercise_minutes', max: 1440, step: 1 },
]
export const STRESS_LEVELS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
export const YES_NO_FACTORS = ['skipped_meal', 'menstruating']

const pad = (n) => String(n).padStart(2, '0')
export const dayString = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
const timeString = (date) => `${pad(date.getHours())}:${pad(date.getMinutes())}`

function addDays(day, n) {
  const [y, m, d] = day.split('-').map(Number)
  return dayString(new Date(y, m - 1, d + n))
}

const localDate = (day, time) => new Date(`${day}T${time}`)

/**
 * Bedtime and wake-up as local Dates. A night is named by the evening it
 * starts: a bedtime before noon is after midnight (the next day), and the
 * wake-up is the first time after bedtime.
 */
export function sleepTimes(form) {
  if (!form.night || !form.bedtime || !form.wakeTime) return null
  const bedDay = form.bedtime < '12:00' ? addDays(form.night, 1) : form.night
  const bed = localDate(bedDay, form.bedtime)
  let wake = localDate(bedDay, form.wakeTime)
  if (wake <= bed) wake = localDate(addDays(bedDay, 1), form.wakeTime)
  return { bed, wake, minutes: Math.round((wake - bed) / 60000) }
}

// --- Sleep ------------------------------------------------------------------

export function emptySleepForm(now = new Date()) {
  return {
    night: addDays(dayString(now), -1), // usually logged the morning after
    bedtime: '23:00',
    wakeTime: '07:00',
    quality: null,
    awakenings: '',
    notes: '',
  }
}

export function sleepFormFrom(log) {
  return {
    night: log.sleep_date,
    bedtime: timeString(new Date(log.bedtime)),
    wakeTime: timeString(new Date(log.wake_time)),
    quality: log.quality,
    awakenings: log.awakenings == null ? '' : String(log.awakenings),
    notes: log.notes ?? '',
  }
}

/** Returns { field: messageKey } for every problem; empty when valid. */
export function validateSleepForm(form, now = new Date()) {
  const errors = {}
  if (!form.night) errors.night = 'daily.errors.dateRequired'
  else if (form.night > dayString(now)) errors.night = 'daily.errors.dateFuture'
  if (!form.bedtime) errors.bedtime = 'daily.errors.timeRequired'
  if (!form.wakeTime) errors.wakeTime = 'daily.errors.timeRequired'
  const times = sleepTimes(form)
  if (times && times.wake > now) errors.wakeTime = 'daily.errors.wakeFuture'
  if (form.awakenings !== '') {
    const n = Number(form.awakenings)
    if (!Number.isInteger(n) || n < 0 || n > AWAKENINGS_MAX) errors.awakenings = 'daily.errors.awakenings'
  }
  if (form.notes.length > NOTES_MAX) errors.notes = 'daily.errors.notesTooLong'
  return errors
}

export function toSleepPayload(form) {
  const { bed, wake } = sleepTimes(form)
  return {
    sleep_date: form.night,
    bedtime: bed.toISOString(),
    wake_time: wake.toISOString(),
    quality: form.quality,
    awakenings: form.awakenings === '' ? null : Number(form.awakenings),
    notes: form.notes.trim() || null,
  }
}

// --- Daily factors ----------------------------------------------------------

export function emptyFactorForm(now = new Date()) {
  return {
    day: dayString(now),
    stress_level: '',
    caffeine_mg: '',
    water_ml: '',
    alcohol_units: '',
    exercise_minutes: '',
    skipped_meal: null,
    menstruating: null,
    notes: '',
  }
}

export function factorFormFrom(record) {
  const text = (v) => (v == null ? '' : String(Number(v)))
  return {
    day: record.log_date,
    stress_level: text(record.stress_level),
    caffeine_mg: text(record.caffeine_mg),
    water_ml: text(record.water_ml),
    alcohol_units: text(record.alcohol_units),
    exercise_minutes: text(record.exercise_minutes),
    skipped_meal: record.skipped_meal,
    menstruating: record.menstruating,
    notes: record.notes ?? '',
  }
}

export function validateFactorForm(form, now = new Date()) {
  const errors = {}
  if (!form.day) errors.day = 'daily.errors.dateRequired'
  else if (form.day > dayString(now)) errors.day = 'daily.errors.dateFuture'
  for (const { name, max, step } of NUMERIC_FACTORS) {
    if (form[name] === '') continue
    const n = Number(form[name])
    const wholeOrHalf = step < 1 ? Number.isInteger(n * 10) : Number.isInteger(n)
    if (!Number.isFinite(n) || n < 0 || n > max || !wholeOrHalf) errors[name] = 'daily.errors.number'
  }
  if (form.notes.length > NOTES_MAX) errors.notes = 'daily.errors.notesTooLong'
  const anything =
    form.stress_level !== '' ||
    NUMERIC_FACTORS.some(({ name }) => form[name] !== '') ||
    YES_NO_FACTORS.some((name) => form[name] != null) ||
    form.notes.trim() !== ''
  if (!anything && !errors.day) errors.form = 'daily.errors.nothingRecorded'
  return errors
}

export function toFactorPayload(form) {
  const number = (v) => (v === '' ? null : Number(v))
  return {
    log_date: form.day,
    stress_level: number(form.stress_level),
    caffeine_mg: number(form.caffeine_mg),
    water_ml: number(form.water_ml),
    alcohol_units: number(form.alcohol_units),
    exercise_minutes: number(form.exercise_minutes),
    skipped_meal: form.skipped_meal,
    menstruating: form.menstruating,
    notes: form.notes.trim() || null,
  }
}
