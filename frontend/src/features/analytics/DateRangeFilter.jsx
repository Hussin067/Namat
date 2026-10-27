import { useState } from 'react'
import Button from '../../components/ui/Button.jsx'
import { FieldError, Input } from '../../components/ui/Field.jsx'
import { cx } from '../../components/ui/styles.js'
import { useI18n } from '../../i18n/i18n-context.js'
import { toLocalInputValue } from '../episodes/format.js'
import { PRESET_PERIODS, validateCustomRange } from './analyticsService.js'

const LABEL_KEYS = { '7d': 'd7', '30d': 'd30', '3m': 'm3', '6m': 'm6', '12m': 'y1', custom: 'custom' }
const today = () => toLocalInputValue(new Date()).slice(0, 10)

/**
 * Preset periods plus a custom range. Presets apply immediately; a custom
 * range applies on "Apply", after the same checks the backend makes.
 */
export default function DateRangeFilter({ value, onChange, disabled }) {
  const { t } = useI18n()
  const [customOpen, setCustomOpen] = useState(value.period === 'custom')
  const [start, setStart] = useState(value.start ?? '')
  const [end, setEnd] = useState(value.end ?? today())
  const [error, setError] = useState(null)
  const selected = customOpen ? 'custom' : value.period

  function choose(period) {
    if (period === 'custom') {
      setCustomOpen(true)
      return
    }
    setCustomOpen(false)
    setError(null)
    onChange({ period })
  }

  function apply(event) {
    event.preventDefault()
    const problem = validateCustomRange(start, end)
    setError(problem)
    if (!problem) onChange({ period: 'custom', start, end })
  }

  return (
    <div className="space-y-3">
      <div
        role="radiogroup"
        aria-label={t('dashboard.filters.label')}
        className="inline-flex max-w-full flex-wrap rounded-xl border border-line bg-sunken p-1"
      >
        {[...PRESET_PERIODS, 'custom'].map((period) => (
          <button
            key={period}
            type="button"
            role="radio"
            aria-checked={selected === period}
            onClick={() => choose(period)}
            className={cx(
              'min-h-9 rounded-lg px-3.5 text-sm font-medium transition-colors',
              selected === period ? 'bg-surface text-ink shadow-card' : 'text-ink-muted hover:text-ink',
            )}
          >
            {t(`dashboard.filters.${LABEL_KEYS[period]}`)}
          </button>
        ))}
      </div>

      {customOpen && (
        <form onSubmit={apply} noValidate className="flex flex-wrap items-end gap-3 animate-rise-in">
          <label className="block w-44 text-sm font-semibold text-ink">
            {t('dashboard.filters.from')}
            <Input
              id="range-start"
              type="date"
              className="mt-1.5"
              value={start}
              max={end || undefined}
              onChange={(e) => setStart(e.target.value)}
              invalid={Boolean(error)}
              aria-describedby={error ? 'range-error' : undefined}
            />
          </label>
          <label className="block w-44 text-sm font-semibold text-ink">
            {t('dashboard.filters.to')}
            <Input
              id="range-end"
              type="date"
              className="mt-1.5"
              value={end}
              min={start || undefined}
              onChange={(e) => setEnd(e.target.value)}
              invalid={Boolean(error)}
              aria-describedby={error ? 'range-error' : undefined}
            />
          </label>
          <Button type="submit" variant="secondary" disabled={disabled}>
            {t('dashboard.filters.apply')}
          </Button>
          <div className={cx('w-full', !error && 'hidden')}>
            <FieldError id="range" error={error && t(error)} />
          </div>
        </form>
      )}
    </div>
  )
}
