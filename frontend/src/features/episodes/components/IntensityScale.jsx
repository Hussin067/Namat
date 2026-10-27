import { FieldError } from '../../../components/ui/Field.jsx'
import { cx } from '../../../components/ui/styles.js'
import { useI18n } from '../../../i18n/i18n-context.js'
import { intensityInfo } from '../constants.js'

const VALUES = Array.from({ length: 11 }, (_, i) => i)

/**
 * 0–10 scale built from native radio buttons: arrow keys move between values,
 * and the selected value is always spelled out in words next to the number.
 */
export default function IntensityScale({ value, onChange, error, id = 'intensity' }) {
  const { t } = useI18n()
  const label = (n) => t(intensityInfo(n).key)
  return (
    <fieldset aria-describedby={cx(`${id}-anchors`, error && `${id}-error`)} aria-invalid={Boolean(error) || undefined}>
      <legend className="text-sm font-semibold text-ink">{t('intensity.legend')}</legend>
      <p className="mt-0.5 text-sm text-ink-muted">{t('intensity.question')}</p>

      <div className="mt-3 grid grid-cols-6 gap-2 sm:grid-cols-11">
        {VALUES.map((n) => (
          <label key={n} className="relative">
            <input
              type="radio"
              name={id}
              value={n}
              checked={value === n}
              onChange={() => onChange(n)}
              className="peer sr-only"
              aria-label={t('intensity.option', { value: n, label: label(n) })}
              {...(n === 0 ? { id } : {})}
            />
            <span
              aria-hidden="true"
              className={cx(
                'flex h-11 cursor-pointer items-center justify-center rounded-xl border text-[0.9375rem] font-semibold tabular-nums transition-colors',
                'peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-brand',
                value === n
                  ? 'border-brand bg-brand text-on-brand'
                  : cx('bg-surface text-ink hover:bg-sunken', error ? 'border-danger' : 'border-line-strong/50'),
              )}
            >
              {n}
            </span>
          </label>
        ))}
      </div>

      <div id={`${id}-anchors`} className="mt-2 flex justify-between gap-4 text-xs text-ink-muted">
        <span>{t('intensity.anchorLow')}</span>
        <span className="text-end">{t('intensity.anchorHigh')}</span>
      </div>

      <p aria-live="polite" className="mt-3 min-h-6 text-sm font-semibold text-ink">
        {value != null && t('intensity.selected', { value, label: label(value) })}
      </p>
      <FieldError id={id} error={error} />
    </fieldset>
  )
}
