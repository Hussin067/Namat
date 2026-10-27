import { Link } from 'react-router'
import { LoaderCircle } from 'lucide-react'
import { buttonClasses, cx } from './styles.js'

export default function Button({
  variant,
  size,
  block,
  loading = false,
  loadingText,
  icon: Icon,
  className,
  children,
  disabled,
  type = 'button',
  ...props
}) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cx(buttonClasses({ variant, size, block }), className)}
      {...props}
    >
      {loading ? (
        <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
      ) : (
        Icon && <Icon aria-hidden="true" className="size-4" />
      )}
      {loading && loadingText ? loadingText : children}
    </button>
  )
}

export function ButtonLink({ variant, size, block, icon: Icon, className, children, ...props }) {
  return (
    <Link className={cx(buttonClasses({ variant, size, block }), className)} {...props}>
      {Icon && <Icon aria-hidden="true" className="size-4" />}
      {children}
    </Link>
  )
}
