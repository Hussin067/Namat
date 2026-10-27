import { useState } from 'react'
import { Save } from 'lucide-react'
import Alert from '../../../components/ui/Alert.jsx'
import Button from '../../../components/ui/Button.jsx'
import Field, { Input, Textarea } from '../../../components/ui/Field.jsx'
import { useI18n } from '../../../i18n/i18n-context.js'
import { NOTES_MAX } from '../../episodes/constants.js'
import { formatDuration } from '../../episodes/format.js'
import { AWAKENINGS_MAX, SLEEP_QUALITY, sleepTimes, toSleepPayload, validateSleepForm } from '../dailyForms.js'
import ChoiceGroup from './ChoiceGroup.jsx'

/**
 * Add or edit one night of sleep. onSubmit(payload) resolves when the server
 * confirmed the save, or throws; on failure the entry stays in the form.
 */
export default function SleepForm({ initialForm, onSubmit, onCancel, submitLabel }) {
  const { t, locale } = useI18n()
  const [form, setForm] = useState(initialForm)
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [failure, setFailure] = useState(null)
  const set = (field) => (value) => setForm((f) => ({ ...f, [field]: value }))
  const times = sleepTimes(form)

  async function submit(event) {
    event.preventDefault()
    const problems = validateSleepForm(form)
    setErrors(problems)
    setFailure(null)
    if (Object.keys(problems).length) return
    setSubmitting(true)
    try {
      await onSubmit(toSleepPayload(form))
    } catch (error) {
      setFailure(error?.key ?? 'errors.generic')
      setSubmitting(false)
    }
  }

  const err = (field) => errors[field] && t(errors[field])

  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      {failure && <Alert tone="danger" title={t('daily.saveFailed')}>{t(failure)}</Alert>}

      <Field id="sleep-night" label={t('daily.sleep.night')} hint={t('daily.sleep.nightHint')} error={err('night')}>
        <Input
          id="sleep-night"
          type="date"
          value={form.night}
          onChange={(e) => set('night')(e.target.value)}
          hint={t('daily.sleep.nightHint')}
          error={err('night')}
          className="sm:w-56"
        />
      </Field>

      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="sleep-bed" label={t('daily.sleep.bedtime')} error={err('bedtime')}>
          <Input id="sleep-bed" type="time" value={form.bedtime} onChange={(e) => set('bedtime')(e.target.value)} error={err('bedtime')} />
        </Field>
        <Field id="sleep-wake" label={t('daily.sleep.wakeTime')} error={err('wakeTime')}>
          <Input id="sleep-wake" type="time" value={form.wakeTime} onChange={(e) => set('wakeTime')(e.target.value)} error={err('wakeTime')} />
        </Field>
      </div>
      {times && (
        <p className="text-sm text-ink-muted" aria-live="polite">
          {t('daily.sleep.duration', { duration: formatDuration(times.minutes, locale) })}
        </p>
      )}

      <ChoiceGroup
        name="sleep-quality"
        legend={t('daily.sleep.quality')}
        value={form.quality}
        onChange={set('quality')}
        options={[
          { value: null, label: t('daily.notRecorded') },
          ...SLEEP_QUALITY.map((q) => ({ value: q, label: t(`daily.sleep.qualities.${q}`) })),
        ]}
      />

      <Field id="sleep-awakenings" label={t('daily.sleep.awakenings')} hint={t('daily.emptyMeansNotRecorded')} error={err('awakenings')} optional>
        <Input
          id="sleep-awakenings"
          type="number"
          inputMode="numeric"
          min={0}
          max={AWAKENINGS_MAX}
          value={form.awakenings}
          onChange={(e) => set('awakenings')(e.target.value)}
          hint={t('daily.emptyMeansNotRecorded')}
          error={err('awakenings')}
          className="sm:w-40"
        />
      </Field>

      <Field id="sleep-notes" label={t('daily.notes')} error={err('notes')} optional>
        <Textarea id="sleep-notes" maxLength={NOTES_MAX} value={form.notes} onChange={(e) => set('notes')(e.target.value)} error={err('notes')} />
      </Field>

      <div className="flex flex-wrap gap-3">
        <Button type="submit" icon={Save} loading={submitting} loadingText={t('daily.saving')}>
          {submitLabel}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          {t('common.cancel')}
        </Button>
      </div>
    </form>
  )
}
