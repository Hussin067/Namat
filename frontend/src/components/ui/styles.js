// Shared class recipes, so links that look like buttons and real buttons stay identical.

export function cx(...classes) {
  return classes.filter(Boolean).join(' ')
}

const buttonBase =
  'inline-flex items-center justify-center gap-2 rounded-xl font-semibold ' +
  'transition-colors duration-150 select-none ' +
  'disabled:cursor-not-allowed disabled:opacity-60'

const buttonVariants = {
  primary: 'bg-brand text-on-brand hover:bg-brand-hover',
  secondary: 'border border-line-strong/60 bg-surface text-ink hover:bg-sunken',
  ghost: 'text-ink-muted hover:bg-sunken hover:text-ink',
  danger: 'border border-danger/40 bg-surface text-danger hover:bg-danger-soft',
}

const buttonSizes = {
  md: 'min-h-11 px-5 text-[0.9375rem]',
  sm: 'min-h-9 px-3.5 text-sm',
}

export function buttonClasses({ variant = 'primary', size = 'md', block = false } = {}) {
  return cx(buttonBase, buttonVariants[variant], buttonSizes[size], block && 'w-full')
}

export const controlClasses = (invalid) =>
  cx(
    'block w-full rounded-xl border bg-surface px-3.5 text-ink placeholder:text-ink-muted/70',
    'transition-colors duration-150 focus-visible:outline-offset-1',
    'disabled:cursor-not-allowed disabled:bg-sunken',
    invalid ? 'border-danger' : 'border-line-strong/70 hover:border-line-strong',
  )

/** aria-describedby value for a field's hint and error messages. */
export function describedBy(id, { hint, error } = {}) {
  return [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(' ') || undefined
}
