import { useState } from 'react'
import { Save } from 'lucide-react'
import Alert from '../../../components/ui/Alert.jsx'
import Button from '../../../components/ui/Button.jsx'
import Field, { FieldError, Input, Select, Textarea } from '../../../components/ui/Field.jsx'
import { useI18n } from '../../../i18n/i18n-context.js'
import { NOTES_MAX } from '../../episodes/constants.js'
import {
  NUMERIC_FACTORS,
  STRESS_LEVELS,
  YES_NO_FACTORS,
  toFactorPayload,
  validateFactorForm,
} from '../dailyForms.js'
import ChoiceGroup from './ChoiceGroup.jsx'

/**
 * Add or edit one day's factors. Every factor is optional; leaving one empty
 * means "not recorded", which is different from 0 or "no".
 */
export default function FactorForm({ initialForm, onSubmit, onCancel, submitLabel }) {
  const { t } = useI18n()
  const [form, setForm] = useState(initialForm)
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [failure, setFailure] = useState(null)
  const set = (field) => (value) => setForm((f) => ({ ...f, [field]: value }))
  const err = (field) => errors[field] && t(errors[field])

  async function submit(event) {
    event.preventDefault()
    const problems = validateFactorForm(form)
    setErrors(problems)
    setFailure(null)
    if (Object.keys(problems).length) return
    setSubmitting(true)
    try {
      await onSubmit(toFactorPayload(form))
    } catch (error) {
      setFailure(error?.key ?? 'errors.generic')
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      {failure && <Alert tone="danger" title={t('daily.saveFailed')}>{t(failure)}</Alert>}
      <p className="text-sm text-ink-muted">{t('daily.factors.intro')}</p>

      <Field id="factor-day" label={t('daily.factors.day')} error={err('day')}>
        <Input id="factor-day" type="date" value={form.day} onChange={(e) => set('day')(e.target.value)} error={err('day')} className="sm:w-56" />
      </Field>

      <Field id="factor-stress" label={t('daily.factors.names.stress_level')} hint={t('daily.factors.stressHint')} optional>
        <Select
          id="factor-stress"
          value={form.stress_level}
          onChange={(e) => set('stress_level')(e.target.value)}
          hint={t('daily.factors.stressHint')}
          className="sm:w-56"
        >
          <option value="">{t('daily.notRecorded')}</option>
          {STRESS_LEVELS.map((n) => (
            <option key={n} value={String(n)}>
              {t('daily.factors.stressOption', { value: n })}
            </option>
          ))}
        </Select>
      </Field>

      <div className="grid gap-5 sm:grid-cols-2">
        {NUMERIC_FACTORS.map(({ name, max, step }) => (
          <Field key={name} id={`factor-${name}`} label={t(`daily.factors.names.${name}`)} error={err(name)} optional>
            <div className="flex items-center gap-2">
              <Input
                id={`factor-${name}`}
                type="number"
                inputMode="decimal"
                min={0}
                max={max}
                step={step}
                value={form[name]}
                onChange={(e) => set(name)(e.target.value)}
                error={err(name)}
              />
              <span className="shrink-0 text-sm text-ink-muted">{t(`daily.factors.units.${name}`)}</span>
            </div>
          </Field>
        ))}
      </div>
      <p className="text-sm text-ink-muted">{t('daily.factors.zeroHint')}</p>

      {YES_NO_FACTORS.map((name) => (
        <ChoiceGroup
          key={name}
          name={`factor-${name}`}
          legend={t(`daily.factors.names.${name}`)}
          value={form[name]}
          onChange={set(name)}
          options={[
            { value: null, label: t('daily.notRecorded') },
            { value: true, label: t('daily.yes') },
            { value: false, label: t('daily.no') },
          ]}
        />
      ))}

      <Field id="factor-notes" label={t('daily.notes')} error={err('notes')} optional>
        <Textarea id="factor-notes" maxLength={NOTES_MAX} value={form.notes} onChange={(e) => set('notes')(e.target.value)} error={err('notes')} />
      </Field>

      <FieldError id="factor-form" error={err('form')} />
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
