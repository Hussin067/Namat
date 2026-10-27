// Values mirror the backend schema (backend/app/models/episode.py and the
// symptoms seeded by the initial Alembic migration), so the form can be wired
// to a real endpoint later without remapping. What users see comes from the
// translation files: locations.<value>, symptoms.<name>, units.<unit>.

export const PAIN_LOCATIONS = ['left', 'right', 'bilateral', 'frontal', 'occipital', 'behind_eye', 'other']

export const SYMPTOMS = [
  'Nausea',
  'Vomiting',
  'Sensitivity to light',
  'Sensitivity to sound',
  'Sensitivity to smell',
  'Visual aura',
  'Tingling or numbness',
  'Dizziness',
  'Difficulty concentrating',
  'Neck pain or stiffness',
  'Fatigue',
  'Throbbing pain',
  'Pain worse with activity',
]

export const DOSE_UNITS = ['mg', 'ml', 'tablet', 'capsule', 'puff', 'drop']

export const NOTES_MAX = 2000

/**
 * Severity word for the 0–10 scale, as a translation key. Severity is always
 * shown as text (and a number), never by colour alone.
 */
export function intensityInfo(value) {
  if (value == null) return { key: 'intensity.notRecorded', tone: 'neutral' }
  if (value === 0) return { key: 'intensity.none', tone: 'neutral' }
  if (value <= 3) return { key: 'intensity.mild', tone: 'brand' }
  if (value <= 6) return { key: 'intensity.moderate', tone: 'warning' }
  if (value <= 8) return { key: 'intensity.severe', tone: 'danger' }
  return { key: 'intensity.verySevere', tone: 'danger' }
}
