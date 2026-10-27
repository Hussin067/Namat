import { CircleAlert, CircleCheck, Info, TriangleAlert } from 'lucide-react'
import { cx } from './styles.js'

const tones = {
  info: { icon: Info, classes: 'bg-brand-soft text-brand-ink border-brand/25' },
  success: { icon: CircleCheck, classes: 'bg-success-soft text-success border-success/25' },
  warning: { icon: TriangleAlert, classes: 'bg-warning-soft text-warning border-warning/25' },
  danger: { icon: CircleAlert, classes: 'bg-danger-soft text-danger border-danger/25' },
}

/**
 * Inline message. Errors use role="alert" (announced immediately);
 * everything else uses role="status" (announced politely).
 */
export default function Alert({ tone = 'info', title, children, className, action }) {
  const { icon: Icon, classes } = tones[tone]
  return (
    <div
      role={tone === 'danger' ? 'alert' : 'status'}
      className={cx('flex gap-3 rounded-xl border px-4 py-3 text-sm animate-rise-in', classes, className)}
    >
      <Icon aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
      <div className="min-w-0 flex-1 space-y-0.5">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className="leading-relaxed">{children}</div>}
        {action && <div className="pt-1.5">{action}</div>}
      </div>
    </div>
  )
}
