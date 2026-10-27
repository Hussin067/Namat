import { cx } from '../../../components/ui/styles.js'

/**
 * A row of radio options styled as a segmented control (like the episode
 * form's "has it ended?" choice). `value` may be null for "not recorded".
 */
export default function ChoiceGroup({ name, legend, hint, options, value, onChange }) {
  return (
    <fieldset aria-describedby={hint ? `${name}-hint` : undefined}>
      <legend className="text-sm font-semibold text-ink">{legend}</legend>
      <div className="mt-2 inline-flex max-w-full flex-wrap rounded-xl border border-line bg-sunken p-1">
        {options.map((o) => (
          <label
            key={String(o.value)}
            className={cx(
              'flex min-h-9 cursor-pointer items-center rounded-lg px-3.5 text-sm font-medium transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-brand',
              value === o.value ? 'bg-surface text-ink shadow-card' : 'text-ink-muted hover:text-ink',
            )}
          >
            <input
              type="radio"
              name={name}
              value={String(o.value)}
              className="sr-only"
              checked={value === o.value}
              onChange={() => onChange(o.value)}
            />
            {o.label}
          </label>
        ))}
      </div>
      {hint && (
        <p id={`${name}-hint`} className="mt-1.5 text-sm text-ink-muted">
          {hint}
        </p>
      )}
    </fieldset>
  )
}
