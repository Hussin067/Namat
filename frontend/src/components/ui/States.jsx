import { CircleAlert, LoaderCircle } from 'lucide-react'
import { useI18n } from '../../i18n/i18n-context.js'
import Button from './Button.jsx'
import { cx } from './styles.js'

export function LoadingState({ label, className }) {
  const { t } = useI18n()
  return (
    <div role="status" className={cx('flex items-center justify-center gap-3 py-12 text-ink-muted', className)}>
      <LoaderCircle aria-hidden="true" className="size-5 animate-spin" />
      <span>{label ?? t('common.loading')}</span>
    </div>
  )
}

export function ErrorState({ title, message, onRetry, className }) {
  const { t } = useI18n()
  return (
    <div role="alert" className={cx('flex flex-col items-center px-6 py-12 text-center', className)}>
      <span className="mb-4 flex size-12 items-center justify-center rounded-full bg-danger-soft text-danger">
        <CircleAlert aria-hidden="true" className="size-6" />
      </span>
      <h2 className="text-lg font-semibold text-ink">{title ?? t('common.somethingWrong')}</h2>
      {message && <p className="mt-1 max-w-sm text-ink-muted">{message}</p>}
      {onRetry && (
        <Button variant="secondary" size="sm" className="mt-5" onClick={onRetry}>
          {t('common.tryAgain')}
        </Button>
      )}
    </div>
  )
}

export function EmptyState({ icon: Icon, title, children, action, className }) {
  return (
    <div className={cx('flex flex-col items-center px-6 py-12 text-center', className)}>
      {Icon && (
        <span className="mb-4 flex size-12 items-center justify-center rounded-full bg-brand-soft text-brand-ink">
          <Icon aria-hidden="true" className="size-6" />
        </span>
      )}
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      {children && <div className="mt-1.5 max-w-md text-ink-muted">{children}</div>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}
