import { useI18n } from '../../i18n/i18n-context.js'
import { cx } from './styles.js'

/** Namat (نمط, "pattern"): two soft waves, one quieter than the other. */
export function LogoMark({ className }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className={cx('size-9 shrink-0', className)}>
      <rect width="32" height="32" rx="9" className="fill-brand" />
      <path d="M7 19c3-6 6-6 9 0s6 6 9 0" fill="none" strokeWidth="2.6" strokeLinecap="round" className="stroke-on-brand" />
      <path
        d="M7 13c3-6 6-6 9 0s6 6 9 0"
        fill="none"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeOpacity=".55"
        className="stroke-on-brand"
      />
    </svg>
  )
}

export default function Logo({ className }) {
  const { t } = useI18n()
  return (
    <span className={cx('inline-flex items-center gap-2.5', className)}>
      <LogoMark />
      <span className="font-display text-[1.4rem] font-semibold tracking-tight text-ink">{t('brand')}</span>
    </span>
  )
}
