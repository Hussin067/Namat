import { cx } from './styles.js'

export default function Card({ as: Tag = 'section', className, children, ...props }) {
  return (
    <Tag className={cx('rounded-2xl border border-line bg-surface shadow-card', className)} {...props}>
      {children}
    </Tag>
  )
}

export function CardHeader({ title, description, action, id }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 px-5 pt-5 sm:px-6 sm:pt-6">
      <div>
        <h2 id={id} className="text-lg font-semibold text-ink">
          {title}
        </h2>
        {description && <p className="mt-0.5 text-sm text-ink-muted">{description}</p>}
      </div>
      {action}
    </div>
  )
}
