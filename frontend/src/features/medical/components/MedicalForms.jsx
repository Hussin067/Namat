import { useState } from 'react'
import { Save } from 'lucide-react'
import Alert from '../../../components/ui/Alert.jsx'
import Button from '../../../components/ui/Button.jsx'
import Field, { Input, Select, Textarea } from '../../../components/ui/Field.jsx'
import { useI18n } from '../../../i18n/i18n-context.js'
import ChoiceGroup from '../../daily/components/ChoiceGroup.jsx'
import { dayString } from '../../daily/dailyForms.js'
import { NOTES_MAX } from '../../episodes/constants.js'
import {
  toAllergyPayload,
  toConditionPayload,
  toProcedurePayload,
  validateAllergyForm,
  validateConditionForm,
  validateProcedureForm,
} from '../medicalForms.js'
import { ALLERGY_TYPES, CONFIRMATIONS, CUSTOM, NAME_MAX, OPTION_HINTS, OPTIONS, REACTION_MAX, SEVERITIES, STATUSES } from '../medicalOptions.js'

/**
 * Shared form behaviour: validate, submit, keep the entry on failure.
 * onSubmit(payload) resolves when the server confirmed the save, or throws.
 */
function useForm(initialForm, validate, toPayload, onSubmit) {
  const [form, setForm] = useState(initialForm)
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [failure, setFailure] = useState(null)
  const set = (field) => (value) => setForm((f) => ({ ...f, [field]: value }))

  async function submit(event) {
    event.preventDefault()
    const problems = validate(form)
    setErrors(problems)
    setFailure(null)
    if (Object.keys(problems).length) return
    setSubmitting(true)
    try {
      await onSubmit(toPayload(form))
    } catch (error) {
      setFailure(error?.key ?? 'errors.generic')
      setSubmitting(false)
    }
  }
  return { form, set, setForm, errors, submitting, failure, submit }
}

function FormShell({ failure, submitting, submitLabel, onCancel, onSubmit, children }) {
  const { t } = useI18n()
  return (
    <form onSubmit={onSubmit} noValidate className="space-y-5">
      {failure && (
        <Alert tone="danger" title={t('medical.saveFailed')}>
          {t(failure)}
        </Alert>
      )}
      {children}
      <div className="flex flex-wrap gap-3">
        <Button type="submit" icon={Save} loading={submitting} loadingText={t('medical.saving')}>
          {submitLabel}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          {t('common.cancel')}
        </Button>
      </div>
    </form>
  )
}

function NotesField({ id, value, onChange, error }) {
  const { t } = useI18n()
  return (
    <Field id={id} label={t('medical.fields.notes')} error={error} optional>
      <Textarea id={id} maxLength={NOTES_MAX} value={value} onChange={(e) => onChange(e.target.value)} error={error} />
    </Field>
  )
}

function DateField({ id, label, value, onChange, error }) {
  const { t } = useI18n()
  const [today] = useState(() => dayString(new Date()))
  return (
    <Field id={id} label={label} hint={t('medical.fields.dateHint')} error={error} optional>
      <Input
        id={id}
        type="date"
        max={today}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        hint={t('medical.fields.dateHint')}
        error={error}
        className="sm:w-56"
      />
    </Field>
  )
}

/** Add or edit a condition. `categories` are the ones this card offers (one, or chronic + serious). */
export function ConditionForm({ categories, initialForm, onSubmit, onCancel, submitLabel }) {
  const { t } = useI18n()
  const { form, set, setForm, errors, submitting, failure, submit } = useForm(
    initialForm,
    validateConditionForm,
    toConditionPayload,
    onSubmit,
  )
  const err = (field) => errors[field] && t(errors[field])
  const prefix = `condition-${form.category}`
  // The name error is shown once: on the typed name when "Other" is chosen.
  const choiceError = form.choice === CUSTOM ? undefined : err('name')

  function choose(choice) {
    // "Not formally identified" is, by definition, not clinician-confirmed.
    setForm((f) => ({ ...f, choice, confirmation: choice === 'not_identified' ? 'unsure' : f.confirmation }))
  }

  return (
    <FormShell failure={failure} submitting={submitting} submitLabel={submitLabel} onCancel={onCancel} onSubmit={submit}>
      {categories.length > 1 && (
        <ChoiceGroup
          name={`${prefix}-category`}
          legend={t('medical.fields.category')}
          hint={t(`medical.categoryHints.${form.category}`)}
          value={form.category}
          onChange={(category) => setForm((f) => ({ ...f, category, choice: f.choice === CUSTOM ? CUSTOM : '' }))}
          options={categories.map((c) => ({ value: c, label: t(`medical.categories.${c}`) }))}
        />
      )}

      <Field id={`${prefix}-name`} label={t('medical.fields.condition')} error={choiceError}>
        <Select
          id={`${prefix}-name`}
          value={form.choice}
          onChange={(e) => choose(e.target.value)}
          error={choiceError}
          className="sm:max-w-md"
        >
          <option value="">{t('medical.fields.choose')}</option>
          {OPTIONS[form.category].map((code) => (
            <option key={code} value={code}>
              {t(`medical.names.${code}`)}
            </option>
          ))}
          <option value={CUSTOM}>{t('medical.fields.other')}</option>
        </Select>
      </Field>
      {OPTION_HINTS[form.choice] && <Alert tone="info">{t(OPTION_HINTS[form.choice])}</Alert>}

      {form.choice === CUSTOM && (
        <Field id={`${prefix}-custom`} label={t('medical.fields.customName')} error={err('name')}>
          <Input
            id={`${prefix}-custom`}
            dir="auto"
            maxLength={NAME_MAX}
            value={form.customName}
            onChange={(e) => set('customName')(e.target.value)}
            error={err('name')}
            className="sm:max-w-md"
          />
        </Field>
      )}

      <ChoiceGroup
        name={`${prefix}-status`}
        legend={t('medical.fields.status')}
        value={form.status}
        onChange={set('status')}
        options={STATUSES.map((s) => ({ value: s, label: t(`medical.statuses.${s}`) }))}
      />

      <ChoiceGroup
        name={`${prefix}-confirmation`}
        legend={t('medical.fields.confirmation')}
        hint={t(`medical.confirmationHints.${form.confirmation}`)}
        value={form.confirmation}
        onChange={set('confirmation')}
        options={CONFIRMATIONS.map((c) => ({ value: c, label: t(`medical.confirmations.${c}`) }))}
      />

      <DateField id={`${prefix}-date`} label={t('medical.fields.conditionDate')} value={form.date} onChange={set('date')} error={err('date')} />
      <NotesField id={`${prefix}-notes`} value={form.notes} onChange={set('notes')} error={err('notes')} />
    </FormShell>
  )
}

export function AllergyForm({ initialForm, onSubmit, onCancel, submitLabel }) {
  const { t } = useI18n()
  const { form, set, errors, submitting, failure, submit } = useForm(initialForm, validateAllergyForm, toAllergyPayload, onSubmit)
  const err = (field) => errors[field] && t(errors[field])
  return (
    <FormShell failure={failure} submitting={submitting} submitLabel={submitLabel} onCancel={onCancel} onSubmit={submit}>
      <Field id="allergy-name" label={t('medical.fields.allergen')} hint={t('medical.fields.allergenHint')} error={err('name')}>
        <Input
          id="allergy-name"
          dir="auto"
          maxLength={NAME_MAX}
          value={form.name}
          onChange={(e) => set('name')(e.target.value)}
          hint={t('medical.fields.allergenHint')}
          error={err('name')}
          className="sm:max-w-md"
        />
      </Field>
      <ChoiceGroup
        name="allergy-type"
        legend={t('medical.fields.allergyType')}
        value={form.type}
        onChange={set('type')}
        options={ALLERGY_TYPES.map((v) => ({ value: v, label: t(`medical.allergyTypes.${v}`) }))}
      />
      <Field id="allergy-reaction" label={t('medical.fields.reaction')} error={err('reaction')} optional>
        <Input
          id="allergy-reaction"
          dir="auto"
          maxLength={REACTION_MAX}
          value={form.reaction}
          onChange={(e) => set('reaction')(e.target.value)}
          error={err('reaction')}
          className="sm:max-w-md"
        />
      </Field>
      <ChoiceGroup
        name="allergy-severity"
        legend={t('medical.fields.severity')}
        value={form.severity}
        onChange={set('severity')}
        options={SEVERITIES.map((v) => ({ value: v, label: t(`medical.severities.${v}`) }))}
      />
      <NotesField id="allergy-notes" value={form.notes} onChange={set('notes')} error={err('notes')} />
    </FormShell>
  )
}

export function ProcedureForm({ initialForm, onSubmit, onCancel, submitLabel }) {
  const { t } = useI18n()
  const { form, set, errors, submitting, failure, submit } = useForm(initialForm, validateProcedureForm, toProcedurePayload, onSubmit)
  const err = (field) => errors[field] && t(errors[field])
  return (
    <FormShell failure={failure} submitting={submitting} submitLabel={submitLabel} onCancel={onCancel} onSubmit={submit}>
      <Field id="procedure-name" label={t('medical.fields.procedure')} error={err('name')}>
        <Input
          id="procedure-name"
          dir="auto"
          maxLength={NAME_MAX}
          value={form.name}
          onChange={(e) => set('name')(e.target.value)}
          error={err('name')}
          className="sm:max-w-md"
        />
      </Field>
      <DateField id="procedure-date" label={t('medical.fields.procedureDate')} value={form.date} onChange={set('date')} error={err('date')} />
      <NotesField id="procedure-notes" value={form.notes} onChange={set('notes')} error={err('notes')} />
    </FormShell>
  )
}
