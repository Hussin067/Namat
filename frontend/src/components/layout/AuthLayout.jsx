import { LockKeyhole } from 'lucide-react'
import { useI18n } from '../../i18n/i18n-context.js'
import LanguageSwitch from '../ui/LanguageSwitch.jsx'
import Logo from '../ui/Logo.jsx'
import ThemeToggle from '../ui/ThemeToggle.jsx'

/** Shared frame for the login and registration screens. */
export default function AuthLayout({ title, description, children, footer }) {
  const { t } = useI18n()
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="flex items-center justify-between gap-3 px-5 py-5 sm:px-8">
        <Logo />
        <div className="flex items-center gap-2">
          <LanguageSwitch />
          <ThemeToggle />
        </div>
      </header>

      <main id="main" className="flex flex-1 items-start justify-center px-5 pt-6 pb-16 sm:items-center sm:pt-0">
        <div className="w-full max-w-[26rem] animate-rise-in">
          <div className="mb-8">
            <h1 className="text-[2rem] font-semibold text-ink">{title}</h1>
            <p className="mt-2 text-ink-muted">{description}</p>
          </div>

          <div className="rounded-2xl border border-line bg-surface p-6 shadow-card sm:p-8">{children}</div>

          {footer && <div className="mt-6 text-center text-ink-muted">{footer}</div>}

          <p className="mt-10 flex items-start justify-center gap-2 text-center text-sm text-ink-muted">
            <LockKeyhole aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            {t('auth.privacy')}
          </p>
        </div>
      </main>
    </div>
  )
}
