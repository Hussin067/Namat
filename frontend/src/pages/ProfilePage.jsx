import { useCallback, useEffect, useRef, useState } from 'react'
import { LogOut } from 'lucide-react'
import { useAuth } from '../auth/auth-context.js'
import Button from '../components/ui/Button.jsx'
import Card, { CardHeader } from '../components/ui/Card.jsx'
import PageHeader from '../components/ui/PageHeader.jsx'
import { ErrorState, LoadingState } from '../components/ui/States.jsx'
import { cx } from '../components/ui/styles.js'
import ThemeToggle from '../components/ui/ThemeToggle.jsx'
import { formatDate, formatTime } from '../features/episodes/format.js'
import { useI18n } from '../i18n/i18n-context.js'

// Each language is named in itself, so either reader can find their own.
const LANGUAGE_OPTIONS = [
  { value: 'en', label: 'English' },
  { value: 'ar', label: 'العربية' },
]

function DetailRow({ label, children }) {
  return (
    <div className="grid gap-1 px-5 py-4 sm:grid-cols-[12rem_1fr] sm:gap-6 sm:px-6">
      <dt className="text-sm font-medium text-ink-muted">{label}</dt>
      <dd className="min-w-0 break-words text-ink">{children}</dd>
    </div>
  )
}

function LanguageChoice() {
  const { t, lang, setLang } = useI18n()
  return (
    <div
      role="radiogroup"
      aria-label={t('language.label')}
      className="inline-flex w-full max-w-sm rounded-xl border border-line bg-sunken p-1"
    >
      {LANGUAGE_OPTIONS.map(({ value, label }) => (
        <button
          key={value}
          type="button"
          role="radio"
          lang={value}
          aria-checked={lang === value}
          onClick={() => setLang(value)}
          className={cx(
            'flex min-h-9 flex-1 items-center justify-center rounded-lg px-3 text-sm font-medium transition-colors',
            lang === value ? 'bg-surface text-ink shadow-card' : 'text-ink-muted hover:text-ink',
          )}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

export default function ProfilePage() {
  const { user, expiresAt, refreshUser, logout } = useAuth()
  const { t, locale } = useI18n()
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)
  const [attempt, setAttempt] = useState(0)

  // refreshUser gets a new identity whenever the user object updates, so keep
  // the latest one in a ref; depending on it directly would re-fetch in a loop.
  const refreshRef = useRef(refreshUser)
  useEffect(() => {
    refreshRef.current = refreshUser
  }, [refreshUser])

  // Always show fresh account details from /auth/me. A 401 ends the session
  // (handled in AuthProvider), which sends the user back to the login page.
  useEffect(() => {
    let cancelled = false
    refreshRef.current().then(
      () => !cancelled && setStatus('ready'),
      (err) => {
        if (cancelled) return
        setError(err)
        setStatus('error')
      },
    )
    return () => {
      cancelled = true
    }
  }, [attempt])

  const retry = useCallback(() => {
    setStatus('loading')
    setAttempt((n) => n + 1)
  }, [])

  return (
    <>
      <PageHeader title={t('profile.title')} description={t('profile.description')} />

      <div className="space-y-6">
        <Card aria-labelledby="account-heading">
          <CardHeader id="account-heading" title={t('profile.account')} description={t('profile.accountDescription')} />
          {status === 'loading' && <LoadingState label={t('profile.loading')} />}
          {status === 'error' && (
            <ErrorState title={t('profile.loadError')} message={t(error?.key ?? 'errors.generic')} onRetry={retry} />
          )}
          {status === 'ready' && user && (
            <dl className="mt-4 divide-y divide-line border-t border-line">
              <DetailRow label={t('profile.email')}>
                <span dir="ltr">{user.email}</span>
              </DetailRow>
              <DetailRow label={t('profile.displayName')}>
                {user.display_name ?? <span className="text-ink-muted">{t('profile.notSet')}</span>}
              </DetailRow>
              <DetailRow label={t('profile.timezone')}>
                <span dir="ltr">{user.timezone}</span>
              </DetailRow>
              <DetailRow label={t('profile.memberSince')}>{formatDate(user.created_at, locale)}</DetailRow>
            </dl>
          )}
        </Card>

        <Card aria-labelledby="language-heading">
          <CardHeader id="language-heading" title={t('profile.language')} description={t('profile.languageDescription')} />
          <div className="px-5 pt-4 pb-6 sm:px-6">
            <LanguageChoice />
          </div>
        </Card>

        <Card aria-labelledby="appearance-heading">
          <CardHeader
            id="appearance-heading"
            title={t('profile.appearance')}
            description={t('profile.appearanceDescription')}
          />
          <div className="px-5 pt-4 pb-6 sm:px-6">
            <ThemeToggle showLabels className="w-full max-w-sm" />
          </div>
        </Card>

        <Card aria-labelledby="session-heading">
          <CardHeader
            id="session-heading"
            title={t('profile.session')}
            description={
              expiresAt ? t('profile.sessionDescription', { time: formatTime(new Date(expiresAt), locale) }) : undefined
            }
          />
          <div className="px-5 pt-4 pb-6 sm:px-6">
            <Button variant="danger" icon={LogOut} onClick={() => logout()}>
              {t('common.logOut')}
            </Button>
          </div>
        </Card>
      </div>
    </>
  )
}
