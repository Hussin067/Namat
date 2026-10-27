import { useRef, useState } from 'react'
import { Link, useLocation } from 'react-router'
import { useAuth } from '../auth/auth-context.js'
import { PASSWORD_MAX, validateEmail } from '../auth/validation.js'
import AuthLayout from '../components/layout/AuthLayout.jsx'
import Alert from '../components/ui/Alert.jsx'
import Button from '../components/ui/Button.jsx'
import Field, { Input } from '../components/ui/Field.jsx'
import PasswordInput from '../components/ui/PasswordInput.jsx'
import { useI18n } from '../i18n/i18n-context.js'

function SessionNotice({ endReason, registered }) {
  const { t } = useI18n()
  if (registered) {
    return (
      <Alert tone="success" title={t('auth.login.registeredTitle')}>
        {t('auth.login.registeredBody')}
      </Alert>
    )
  }
  if (endReason === 'expired') {
    return (
      <Alert tone="warning" title={t('auth.login.expiredTitle')}>
        {t('auth.login.expiredBody')}
      </Alert>
    )
  }
  if (endReason === 'signed-out') return <Alert tone="info">{t('auth.login.loggedOut')}</Alert>
  return null
}

export default function LoginPage() {
  const { login, endReason } = useAuth()
  const { t } = useI18n()
  const location = useLocation()
  const registered = Boolean(location.state?.registered)

  const [email, setEmail] = useState(location.state?.email ?? '')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState({})
  // An error stays until the field is edited, so it never describes old input.
  const clearError = (key) => setErrors((current) => (current[key] ? { ...current, [key]: null } : current))
  const [formError, setFormError] = useState(null)
  const [loading, setLoading] = useState(false)
  const emailRef = useRef(null)
  const passwordRef = useRef(null)
  const message = (error) => error && t(error.key, error.vars)

  async function handleSubmit(event) {
    event.preventDefault()
    const next = {
      email: validateEmail(email),
      password: password ? null : { key: 'auth.validation.passwordRequired' },
    }
    setErrors(next)
    setFormError(null)
    if (next.email) return emailRef.current?.focus()
    if (next.password) return passwordRef.current?.focus()

    setLoading(true)
    try {
      await login(email.trim(), password)
      // <GuestOnly> now redirects to the dashboard (or the page originally requested).
    } catch (error) {
      setFormError(error)
      setPassword('')
      setLoading(false)
      passwordRef.current?.focus()
    }
  }

  return (
    <AuthLayout
      title={t('auth.login.title')}
      description={t('auth.login.description')}
      footer={
        <>
          {t('auth.login.newHere')}{' '}
          <Link to="/register" className="font-semibold text-brand underline-offset-4 hover:underline">
            {t('auth.login.createAccount')}
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        {!formError && <SessionNotice endReason={endReason} registered={registered} />}
        {formError && (
          <Alert tone="danger" title={t('auth.login.errorTitle')}>
            {t(formError.key ?? 'errors.generic')}
          </Alert>
        )}

        <Field id="login-email" label={t('auth.fields.email')} error={message(errors.email)}>
          <Input
            ref={emailRef}
            id="login-email"
            type="email"
            dir="ltr"
            autoComplete="email"
            inputMode="email"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value)
              clearError('email')
            }}
            error={message(errors.email)}
          />
        </Field>

        <Field id="login-password" label={t('auth.fields.password')} error={message(errors.password)}>
          <PasswordInput
            ref={passwordRef}
            id="login-password"
            autoComplete="current-password"
            maxLength={PASSWORD_MAX}
            value={password}
            onChange={(e) => {
              setPassword(e.target.value)
              clearError('password')
            }}
            error={message(errors.password)}
          />
        </Field>

        <Button type="submit" block loading={loading} loadingText={t('auth.login.submitting')}>
          {t('auth.login.submit')}
        </Button>
      </form>
    </AuthLayout>
  )
}
