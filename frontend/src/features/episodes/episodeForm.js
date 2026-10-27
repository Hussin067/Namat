import { NOTES_MAX } from './constants.js'
import { toLocalInputValue } from './format.js'

const FUTURE_TOLERANCE_MS = 5 * 60 * 1000

export function emptyEpisodeForm(now = new Date()) {
  return {
    startedAt: toLocalInputValue(now),
    ongoing: false,
    endedAt: '',
    intensity: null,
    location: '',
    hadAura: false,
    symptoms: [],
    medicationName: '',
    doseAmount: '',
    doseUnit: 'mg',
    medicationTakenAt: '',
    medicationRelief: null, // not shown in the form, but kept when editing
    otherMedications: [], // doses beyond the first, kept unchanged when editing
    notes: '',
  }
}

/** A saved episode (as returned by episodeService) → form state for editing. */
export function episodeToForm(episode) {
  const local = (iso) => (iso ? toLocalInputValue(new Date(iso)) : '')
  const [first, ...others] = episode.medications ?? []
  return {
    ...emptyEpisodeForm(),
    startedAt: local(episode.started_at),
    ongoing: episode.ended_at == null,
    endedAt: local(episode.ended_at),
    intensity: episode.peak_intensity,
    location: episode.pain_location ?? '',
    hadAura: episode.had_aura,
    symptoms: [...episode.symptoms],
    medicationName: first?.medication_name ?? '',
    doseAmount: first?.dose_amount == null ? '' : String(first.dose_amount),
    doseUnit: first?.dose_unit ?? 'mg',
    medicationTakenAt: local(first?.taken_at),
    medicationRelief: first?.relief_rating ?? null,
    otherMedications: others.map(({ medication_name, dose_amount, dose_unit, taken_at, relief_rating }) => ({
      medication_name,
      dose_amount,
      dose_unit,
      taken_at,
      relief_rating,
    })),
    notes: episode.notes ?? '',
  }
}

/** Field order here is the order focus moves to when several fields are invalid. */
export const FIELD_ORDER = ['startedAt', 'endedAt', 'intensity', 'medicationName', 'doseAmount', 'medicationTakenAt', 'notes']

/** Returns { field: { key, vars } } for each invalid field, naming translated messages. */
export function validateEpisodeForm(form, now = new Date()) {
  const errors = {}
  const latestAllowed = now.getTime() + FUTURE_TOLERANCE_MS
  const start = form.startedAt ? new Date(form.startedAt) : null

  if (!start || Number.isNaN(start.getTime())) errors.startedAt = { key: 'log.validation.startRequired' }
  else if (start.getTime() > latestAllowed) errors.startedAt = { key: 'log.validation.startFuture' }

  if (!form.ongoing) {
    const end = form.endedAt ? new Date(form.endedAt) : null
    if (!end || Number.isNaN(end.getTime())) errors.endedAt = { key: 'log.validation.endRequired' }
    else if (start && end < start) errors.endedAt = { key: 'log.validation.endBeforeStart' }
    else if (end.getTime() > latestAllowed) errors.endedAt = { key: 'log.validation.endFuture' }
  }

  if (form.intensity == null) errors.intensity = { key: 'log.validation.intensityRequired' }

  const hasMedication = form.medicationName.trim() !== ''
  if (!hasMedication && (form.doseAmount !== '' || form.medicationTakenAt)) {
    errors.medicationName = { key: 'log.validation.medicationNameRequired' }
  }
  if (form.doseAmount !== '' && !(Number(form.doseAmount) > 0)) {
    errors.doseAmount = { key: 'log.validation.doseInvalid' }
  }
  if (form.medicationTakenAt && new Date(form.medicationTakenAt).getTime() > latestAllowed) {
    errors.medicationTakenAt = { key: 'log.validation.takenFuture' }
  }

  if (form.notes.length > NOTES_MAX) errors.notes = { key: 'log.validation.notesTooLong', vars: { max: NOTES_MAX } }
  return errors
}
