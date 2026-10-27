import { CircleAlert } from 'lucide-react'
import { useI18n } from '../../i18n/i18n-context.js'
import { controlClasses, cx, describedBy } from './styles.js'

/**
 * Label + control + hint + error, wired together for screen readers.
 * Pass the control as children; give it id={id} and
 * aria-describedby={describedBy(id, { hint, error })}.
 */
export default function Field({ id, label, hint, error, optional = false, children, className }) {
  const { t } = useI18n()
  return (
    <div className={cx('space-y-1.5', className)}>
      <label htmlFor={id} className="flex items-baseline justify-between gap-3 text-sm font-semibold text-ink">
        {label}
        {optional && <span className="text-xs font-normal text-ink-muted">{t('common.optional')}</span>}
      </label>
      {children}
      {hint && (
        <p id={`${id}-hint`} className="text-sm text-ink-muted">
          {hint}
        </p>
      )}
      <FieldError id={id} error={error} />
    </div>
  )
}

export function FieldError({ id, error }) {
  if (!error) return null
  return (
    <p id={`${id}-error`} className="flex items-start gap-1.5 text-sm font-medium text-danger">
      <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      {error}
    </p>
  )
}

export function Input({ id, invalid, hint, error, className, ...props }) {
  return (
    <input
      id={id}
      aria-invalid={invalid || Boolean(error) || undefined}
      aria-describedby={describedBy(id, { hint, error })}
      className={cx(controlClasses(invalid || error), 'min-h-11', className)}
      {...props}
    />
  )
}

export function Select({ id, hint, error, className, children, ...props }) {
  return (
    <select
      id={id}
      aria-invalid={Boolean(error) || undefined}
      aria-describedby={describedBy(id, { hint, error })}
      className={cx(controlClasses(error), 'min-h-11 pe-9', className)}
      {...props}
    >
      {children}
    </select>
  )
}

export function Textarea({ id, hint, error, className, ...props }) {
  return (
    <textarea
      id={id}
      aria-invalid={Boolean(error) || undefined}
      aria-describedby={describedBy(id, { hint, error })}
      className={cx(controlClasses(error), 'min-h-28 py-2.5 leading-relaxed', className)}
      {...props}
    />
  )
}
