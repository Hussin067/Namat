import { displayName } from './medicalOptions.js'

/** A 'YYYY-MM-DD' day as a local date (never shifted by the time zone). */
export function formatDay(day, locale) {
  const [y, m, d] = day.split('-').map(Number)
  return new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(y, m - 1, d))
}

/** Title and short detail parts for one medical-history item, in the interface language. */
export function describeItem(kind, item, t, locale) {
  if (kind === 'conditions') {
    const parts = [t(`medical.statuses.${item.status}`)]
    if (item.diagnosis_date) parts.push(t('medical.since', { date: formatDay(item.diagnosis_date, locale) }))
    return { title: displayName(item.condition_name, t), parts }
  }
  if (kind === 'allergies') {
    return {
      title: item.name,
      parts: [t(`medical.allergyTypes.${item.type}`), t('medical.severityValue', { severity: t(`medical.severities.${item.severity}`) })],
    }
  }
  return { title: item.name, parts: item.procedure_date ? [formatDay(item.procedure_date, locale)] : [] }
}

// Shown on the dashboard as context only: what the user reported, nothing
// inferred. Serious past illnesses and conditions no longer current aren't listed.
const CONTEXT_CATEGORIES = ['headache_disorder', 'associated_condition', 'chronic_disease']

/** Names for "You reported a history of …", headache disorders first. */
export function contextNames(conditions, t) {
  return conditions
    .filter((c) => CONTEXT_CATEGORIES.includes(c.category) && c.status !== 'resolved')
    .sort((a, b) => CONTEXT_CATEGORIES.indexOf(a.category) - CONTEXT_CATEGORIES.indexOf(b.category))
    .map((c) => displayName(c.condition_name, t))
}
