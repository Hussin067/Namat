import { Compass } from 'lucide-react'
import { useAuth } from '../auth/auth-context.js'
import { ButtonLink } from '../components/ui/Button.jsx'
import Logo from '../components/ui/Logo.jsx'
import { EmptyState } from '../components/ui/States.jsx'
import { useI18n } from '../i18n/i18n-context.js'

export default function NotFoundPage() {
  const { isAuthenticated } = useAuth()
  const { t } = useI18n()
  return (
    <main id="main" className="flex min-h-dvh flex-col items-center justify-center px-5">
      <Logo className="mb-10" />
      <EmptyState
        icon={Compass}
        title={t('notFound.title')}
        action={
          <ButtonLink to={isAuthenticated ? '/dashboard' : '/login'}>
            {isAuthenticated ? t('notFound.toDashboard') : t('notFound.toLogin')}
          </ButtonLink>
        }
      >
        {t('notFound.body')}
      </EmptyState>
    </main>
  )
}
