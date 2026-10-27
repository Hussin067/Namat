import { Languages } from 'lucide-react'
import { useI18n } from '../../i18n/i18n-context.js'
import { cx } from './styles.js'

/** One button that switches to the other language. Its label is written in that language. */
export default function LanguageSwitch({ className }) {
  const { t, setLang } = useI18n()
  const target = t('language.otherCode')
  return (
    <button
      type="button"
      onClick={() => setLang(target)}
      aria-label={t('language.switchTo')}
      className={cx(
        'inline-flex min-h-9 items-center gap-2 rounded-xl border border-line bg-sunken px-3 text-sm font-semibold text-ink transition-colors hover:bg-surface',
        className,
      )}
    >
      <Languages aria-hidden="true" className="size-4 text-ink-muted" />
      <span lang={target}>{t('language.other')}</span>
    </button>
  )
}
