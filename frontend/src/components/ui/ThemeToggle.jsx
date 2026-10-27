import { Moon, Sun } from 'lucide-react'
import { useI18n } from '../../i18n/i18n-context.js'
import { useTheme } from '../../theme/theme-context.js'
import { cx } from './styles.js'

const OPTIONS = [
  { value: 'light', icon: Sun },
  { value: 'dark', icon: Moon },
]

/** Two-way switch: light or dark. */
export default function ThemeToggle({ showLabels = false, className }) {
  const { theme, setTheme } = useTheme()
  const { t } = useI18n()
  return (
    <div
      role="radiogroup"
      aria-label={t('theme.label')}
      className={cx('inline-flex rounded-xl border border-line bg-sunken p-1', className)}
    >
      {OPTIONS.map(({ value, icon: Icon }) => {
        const checked = theme === value
        const name = t(`theme.${value}Theme`)
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={checked}
            aria-label={showLabels ? undefined : name}
            title={name}
            onClick={() => setTheme(value)}
            className={cx(
              'flex min-h-9 flex-1 items-center justify-center gap-1.5 rounded-lg px-2.5 text-sm font-medium transition-colors',
              checked ? 'bg-surface text-ink shadow-card' : 'text-ink-muted hover:text-ink',
            )}
          >
            <Icon aria-hidden="true" className="size-4" />
            {showLabels && t(`theme.${value}`)}
          </button>
        )
      })}
    </div>
  )
}
