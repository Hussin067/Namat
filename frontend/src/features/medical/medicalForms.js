// Form state, validation and API payloads for the medical-history forms.
// Errors are message keys; an empty object means the form is valid.

import { NOTES_MAX } from '../episodes/constants.js'
import { dayString } from '../daily/dailyForms.js'
import { ADDITIONAL_NOTES_MAX, CUSTOM, NAME_MAX, OPTIONS, REACTION_MAX, codeOf, storedName } from './medicalOptions.js'

const EARLIEST = '1900-01-01'

function checkDate(value, now) {
  if (!value) return null
  if (value > dayString(now)) return 'medical.errors.dateFuture'
  if (value < EARLIEST) return 'medical.errors.dateTooOld'
  return null
}

function checkName(name) {
  const value = name.trim()
  if (!value) return 'medical.errors.nameRequired'
  if (value.length > NAME_MAX) return 'medical.errors.nameTooLong'
  return null
}

const orNull = (text) => text.trim() || null

// --- Conditions -------------------------------------------------------------

export function emptyConditionForm(category) {
  return { category, choice: '', customName: '', status: 'active', confirmation: 'self_reported', date: '', notes: '' }
}

export function conditionFormFrom(item) {
  const code = codeOf(item.condition_name)
  const predefined = code && OPTIONS[item.category]?.includes(code)
  return {
    category: item.category,
    choice: predefined ? code : CUSTOM,
    customName: predefined ? '' : item.condition_name,
    status: item.status,
    confirmation: item.confirmation,
    date: item.diagnosis_date ?? '',
    notes: item.notes ?? '',
  }
}

export function validateConditionForm(form, now = new Date()) {
  const errors = {}
  if (!form.choice) errors.name = 'medical.errors.chooseName'
  else if (form.choice === CUSTOM) {
    const problem = checkName(form.customName)
    if (problem) errors.name = problem
  }
  const date = checkDate(form.date, now)
  if (date) errors.date = date
  if (form.notes.length > NOTES_MAX) errors.notes = 'medical.errors.notesTooLong'
  return errors
}

export function toConditionPayload(form) {
  return {
    condition_name: form.choice === CUSTOM ? form.customName.trim() : storedName(form.choice),
    category: form.category,
    status: form.status,
    confirmation: form.confirmation,
    diagnosis_date: form.date || null,
    notes: orNull(form.notes),
  }
}

// --- Allergies --------------------------------------------------------------

export function emptyAllergyForm() {
  return { name: '', type: 'medication', severity: 'unknown', reaction: '', notes: '' }
}

export function allergyFormFrom(item) {
  return { name: item.name, type: item.type, severity: item.severity, reaction: item.reaction ?? '', notes: item.notes ?? '' }
}

export function validateAllergyForm(form) {
  const errors = {}
  const name = checkName(form.name)
  if (name) errors.name = name
  if (form.reaction.trim().length > REACTION_MAX) errors.reaction = 'medical.errors.reactionTooLong'
  if (form.notes.length > NOTES_MAX) errors.notes = 'medical.errors.notesTooLong'
  return errors
}

export function toAllergyPayload(form) {
  return { name: form.name.trim(), type: form.type, severity: form.severity, reaction: orNull(form.reaction), notes: orNull(form.notes) }
}

// --- Procedures -------------------------------------------------------------

export function emptyProcedureForm() {
  return { name: '', date: '', notes: '' }
}

export function procedureFormFrom(item) {
  return { name: item.name, date: item.procedure_date ?? '', notes: item.notes ?? '' }
}

export function validateProcedureForm(form, now = new Date()) {
  const errors = {}
  const name = checkName(form.name)
  if (name) errors.name = name
  const date = checkDate(form.date, now)
  if (date) errors.date = date
  if (form.notes.length > NOTES_MAX) errors.notes = 'medical.errors.notesTooLong'
  return errors
}

export function toProcedurePayload(form) {
  return { name: form.name.trim(), procedure_date: form.date || null, notes: orNull(form.notes) }
}

// --- Additional notes -------------------------------------------------------

export function validateNotes(text) {
  return text.length > ADDITIONAL_NOTES_MAX ? 'medical.errors.additionalNotesTooLong' : null
}
