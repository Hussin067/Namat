import { useEffect, useRef, useState } from 'react'
import { Check, Save } from 'lucide-react'
import { useAuth } from '../../../auth/auth-context.js'
import Alert from '../../../components/ui/Alert.jsx'
import Button from '../../../components/ui/Button.jsx'
import Card, { CardHeader } from '../../../components/ui/Card.jsx'
import Field, { Input, Select, Textarea } from '../../../components/ui/Field.jsx'
import { cx } from '../../../components/ui/styles.js'
import { useI18n } from '../../../i18n/i18n-context.js'
import { DOSE_UNITS, NOTES_MAX, PAIN_LOCATIONS, SYMPTOMS } from '../constants.js'
import { FIELD_ORDER, validateEpisodeForm } from '../episodeForm.js'
import { loadSymptomCatalog, toEpisodePayload } from '../episodeService.js'
import IntensityScale from './IntensityScale.jsx'

function Section({ title, description, children, optional }) {
  const { t } = useI18n()
  return (
    <Card>
      <CardHeader
        title={
          <>
            {title}
            {optional && <span className="ms-2 font-sans text-sm font-normal text-ink-muted">{t('common.optional')}</span>}
          </>
        }
        description={description}
      />
      <div className="space-y-5 px-5 pt-5 pb-6 sm:px-6">{children}</div>
    </Card>
  )
}

function EndChoice({ ongoing, onChange }) {
  const { t } = useI18n()
  const options = [
    { value: false, label: t('log.itHasEnded') },
    { value: true, label: t('log.stillGoing') },
  ]
  return (
    <fieldset>
      <legend className="text-sm font-semibold text-ink">{t('log.hasEnded')}</legend>
      <div className="mt-2 inline-flex rounded-xl border border-line bg-sunken p-1">
        {options.map((o) => (
          <label
            key={String(o.value)}
            className={cx(
              'flex min-h-9 cursor-pointer items-center rounded-lg px-3.5 text-sm font-medium transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-brand',
              ongoing === o.value ? 'bg-surface text-ink shadow-card' : 'text-ink-muted hover:text-ink',
            )}
          >
            <input
              type="radio"
              name="ongoing"
              value={o.value ? 'ongoing' : 'ended'}
              className="sr-only"
              checked={ongoing === o.value}
              onChange={() => onChange(o.value)}
            />
            {o.label}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

/**
 * The episode form, shared by "Log an episode" and "Edit episode".
 * It validates, builds the API payload and calls onSubmit(payload, form).
 * onSubmit resolves when the server confirmed the save, or throws; on failure
 * the entry stays in the form and an error is shown. Success handling (reset,
 * navigation, messages) belongs to the page.
 */
export default function EpisodeForm({ initialForm, onSubmit, submitLabel, submittingLabel, secondaryAction }) {
  const { t } = useI18n()
  const { authRequest } = useAuth()
  const [form, setForm] = useState(initialForm)
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [failure, setFailure] = useState(null) // message key
  const [catalog, setCatalog] = useState(null)
  const formRef = useRef(null)
  const message = (error) => error && t(error.key, error.vars)

  // Symptom ids come from the server; the checkboxes work by name meanwhile.
  useEffect(() => {
    let cancelled = false
    loadSymptomCatalog(authRequest).then(
      (items) => !cancelled && setCatalog(items),
      () => !cancelled && setCatalog(null),
    )
    return () => {
      cancelled = true
    }
  }, [authRequest])

  const set = (key) => (eventOrValue) => {
    const value = eventOrValue?.target ? eventOrValue.target.value : eventOrValue
    setForm((current) => ({ ...current, [key]: value }))
    if (errors[key]) setErrors((current) => ({ ...current, [key]: undefined }))
  }

  const toggleSymptom = (name) =>
    setForm((current) => ({
      ...current,
      symptoms: current.symptoms.includes(name)
        ? current.symptoms.filter((s) => s !== name)
        : [...current.symptoms, name],
    }))

  async function handleSubmit(event) {
    event.preventDefault()
    if (submitting) return // no double submits
    setFailure(null)

    const found = validateEpisodeForm(form)
    setErrors(found)
    const firstInvalid = FIELD_ORDER.find((key) => found[key])
    if (firstInvalid) {
      formRef.current?.querySelector(`#${firstInvalid === 'intensity' ? 'intensity' : `episode-${firstInvalid}`}`)?.focus()
      return
    }
    if (form.symptoms.length > 0 && !catalog) {
      setFailure('log.symptomsUnavailable')
      window.scrollTo({ top: 0, behavior: 'smooth' })
      return
    }

    setSubmitting(true)
    try {
      await onSubmit(toEpisodePayload(form, catalog ?? []), form)
    } catch (error) {
      setFailure(error.key ?? 'errors.generic')
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form ref={formRef} onSubmit={handleSubmit} noValidate className="space-y-6">
      {failure && (
        <Alert tone="danger" title={t('log.result.notSavedTitle')}>
          {t(failure)} {t('log.result.keptInForm')}
        </Alert>
      )}

      <Section title={t('log.when')} description={t('log.whenDescription')}>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field id="episode-startedAt" label={t('log.started')} error={message(errors.startedAt)}>
            <Input
              id="episode-startedAt"
              type="datetime-local"
              value={form.startedAt}
              onChange={set('startedAt')}
              error={message(errors.startedAt)}
              required
            />
          </Field>
        </div>
        <EndChoice ongoing={form.ongoing} onChange={set('ongoing')} />
        {!form.ongoing && (
          <div className="grid gap-5 sm:grid-cols-2">
            <Field id="episode-endedAt" label={t('log.ended')} error={message(errors.endedAt)}>
              <Input
                id="episode-endedAt"
                type="datetime-local"
                min={form.startedAt || undefined}
                value={form.endedAt}
                onChange={set('endedAt')}
                error={message(errors.endedAt)}
              />
            </Field>
          </div>
        )}
      </Section>

      <Section title={t('log.howItFelt')}>
        <IntensityScale value={form.intensity} onChange={set('intensity')} error={message(errors.intensity)} />

        <div className="grid gap-5 sm:grid-cols-2">
          <Field id="episode-location" label={t('log.where')} optional>
            <Select id="episode-location" value={form.location} onChange={set('location')}>
              <option value="">{t('log.notSure')}</option>
              {PAIN_LOCATIONS.map((value) => (
                <option key={value} value={value}>
                  {t(`locations.${value}`)}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <label className="flex cursor-pointer items-start gap-3">
          <input
            type="checkbox"
            checked={form.hadAura}
            onChange={(e) => set('hadAura')(e.target.checked)}
            className="mt-1 size-[1.125rem] shrink-0 accent-brand"
          />
          <span>
            <span className="font-semibold text-ink">{t('log.auraTitle')}</span>
            <span className="block text-sm text-ink-muted">{t('log.auraDescription')}</span>
          </span>
        </label>
      </Section>

      <Section title={t('log.symptomsTitle')} optional description={t('log.symptomsDescription')}>
        <fieldset>
          <legend className="sr-only">{t('log.symptomsTitle')}</legend>
          <div className="flex flex-wrap gap-2">
            {SYMPTOMS.map((name) => {
              const checked = form.symptoms.includes(name)
              return (
                <label
                  key={name}
                  className={cx(
                    'inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-full border px-3.5 text-sm font-medium transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-brand',
                    checked
                      ? 'border-brand bg-brand-soft text-brand-ink'
                      : 'border-line-strong/50 text-ink-muted hover:bg-sunken hover:text-ink',
                  )}
                >
                  <input type="checkbox" checked={checked} onChange={() => toggleSymptom(name)} className="sr-only" />
                  <span
                    aria-hidden="true"
                    className={cx(
                      'flex size-4 items-center justify-center rounded border',
                      checked ? 'border-brand bg-brand text-on-brand' : 'border-line-strong',
                    )}
                  >
                    {checked && <Check className="size-3" strokeWidth={3} />}
                  </span>
                  {t(`symptoms.${name}`)}
                </label>
              )
            })}
          </div>
        </fieldset>
      </Section>

      <Section title={t('log.medicationTitle')} optional description={t('log.medicationDescription')}>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field id="episode-medicationName" label={t('log.medicationName')} error={message(errors.medicationName)}>
            <Input
              id="episode-medicationName"
              autoComplete="off"
              value={form.medicationName}
              onChange={set('medicationName')}
              error={message(errors.medicationName)}
            />
          </Field>
          <Field id="episode-medicationTakenAt" label={t('log.timeTaken')} error={message(errors.medicationTakenAt)}>
            <Input
              id="episode-medicationTakenAt"
              type="datetime-local"
              value={form.medicationTakenAt}
              onChange={set('medicationTakenAt')}
              error={message(errors.medicationTakenAt)}
            />
          </Field>
          <Field id="episode-doseAmount" label={t('log.dose')} error={message(errors.doseAmount)}>
            <div className="flex gap-2">
              <div className="min-w-0 flex-1">
                <Input
                  id="episode-doseAmount"
                  type="number"
                  inputMode="decimal"
                  min="0"
                  step="any"
                  value={form.doseAmount}
                  onChange={set('doseAmount')}
                  error={message(errors.doseAmount)}
                />
              </div>
              <div className="w-32 shrink-0">
                <Select id="episode-doseUnit" aria-label={t('log.doseUnit')} value={form.doseUnit} onChange={set('doseUnit')}>
                  {DOSE_UNITS.map((unit) => (
                    <option key={unit} value={unit}>
                      {t(`units.${unit}`)}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
          </Field>
        </div>
      </Section>

      <Section title={t('log.notesTitle')} optional>
        <Field
          id="episode-notes"
          label={t('log.notesLabel')}
          hint={t('log.notesHint', { count: form.notes.length, max: NOTES_MAX })}
          error={message(errors.notes)}
        >
          <Textarea
            id="episode-notes"
            value={form.notes}
            onChange={set('notes')}
            hint
            error={message(errors.notes)}
            maxLength={NOTES_MAX + 200}
          />
        </Field>
      </Section>


      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-end">
        {secondaryAction}
        <Button type="submit" icon={Save} loading={submitting} loadingText={submittingLabel}>
          {submitLabel}
        </Button>
      </div>
    </form>
  )
}
