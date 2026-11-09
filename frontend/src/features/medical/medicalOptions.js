// Choices for the medical-history forms. Limits and values mirror
// backend/app/schemas/medical_history.py and backend/app/models/medical_history.py.
//
// A predefined name is stored in English (the text in en.js under
// medical.names), so the same record reads correctly in either language: the
// app and the report translate a stored name back when it matches one of
// these, and anything the user typed is shown exactly as typed.

import en from '../../i18n/messages/en.js'

export const NAME_MAX = 120
export const REACTION_MAX = 200
export const ADDITIONAL_NOTES_MAX = 4000

export const STATUSES = ['active', 'monitoring', 'resolved']
export const CONFIRMATIONS = ['clinician_confirmed', 'self_reported', 'unsure']
export const ALLERGY_TYPES = ['medication', 'food', 'environmental', 'other']
export const SEVERITIES = ['mild', 'moderate', 'severe', 'unknown']

/** "Other": the user types their own name. */
export const CUSTOM = 'custom'

// Predefined names per category (keys of medical.names). Serious past
// illnesses such as meningitis are their own category and are never offered
// as headache-associated conditions.
export const OPTIONS = {
  chronic_disease: ['diabetes', 'asthma', 'heart_disease', 'kidney_disease', 'epilepsy', 'depression_anxiety'],
  serious_history: ['meningitis', 'encephalitis', 'head_injury', 'stroke', 'brain_bleed'],
  headache_disorder: [
    'migraine',
    'migraine_with_aura',
    'migraine_without_aura',
    'chronic_migraine',
    'tension_type',
    'cluster',
    'chronic_daily',
    'medication_overuse',
    'sinus_headache',
    'not_identified',
  ],
  associated_condition: ['sinusitis', 'hypertension', 'anemia', 'thyroid', 'sleep_disorder', 'vision', 'tmj'],
}

// Options that need a short explanation when chosen.
export const OPTION_HINTS = { sinus_headache: 'medical.hints.sinus_headache', not_identified: 'medical.hints.not_identified' }

/** The six cards on the page, in order. Conditions cards list their categories. */
export const CARDS = [
  { id: 'chronic', kind: 'conditions', categories: ['chronic_disease', 'serious_history'] },
  { id: 'headache', kind: 'conditions', categories: ['headache_disorder'] },
  { id: 'associated', kind: 'conditions', categories: ['associated_condition'] },
  { id: 'allergies', kind: 'allergies' },
  { id: 'procedures', kind: 'procedures' },
  { id: 'notes', kind: 'notes' },
]

const CODE_BY_STORED_NAME = new Map(Object.entries(en.medical.names).map(([code, name]) => [name, code]))

/** The English name stored for a predefined option. */
export const storedName = (code) => en.medical.names[code]

/** The predefined option a stored name came from, or null for a typed name. */
export const codeOf = (name) => CODE_BY_STORED_NAME.get(name) ?? null

/** A stored name in the interface language (typed names unchanged). */
export function displayName(name, t) {
  const code = codeOf(name)
  return code ? t(`medical.names.${code}`) : name
}
