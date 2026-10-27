import { useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { useAuth } from '../auth/auth-context.js'
import { PASSWORD_MAX, PASSWORD_MIN, validateEmail, validateNewPassword } from '../auth/validation.js'
import AuthLayout from '../components/layout/AuthLayout.jsx'
import Alert from '../components/ui/Alert.jsx'
import Button from '../components/ui/Button.jsx'
import Field, { Input } from '../components/ui/Field.jsx'
import PasswordInput from '../components/ui/PasswordInput.jsx'
import { useI18n } from '../i18n/i18n-context.js'

export default function RegisterPage() {
  const { register } = useAuth()
  const { t } = useI18n()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [errors, setErrors] = useState({})
  // An error stays until the field is edited, so it never describes old input.
  const clearError = (key) => setErrors((current) => (current[key] ? { ...current, [key]: null } : current))
  const [formError, setFormError] = useState(null)
  const [loading, setLoading] = useState(false)
  const emailRef = useRef(null)
  const passwordRef = useRef(null)
  const confirmRef = useRef(null)
  const message = (error) => error && t(error.key, error.vars)

  async function handleSubmit(event) {
    event.preventDefault()
    const next = {
      email: validateEmail(email),
      password: validateNewPassword(password),
      confirm: !confirm
        ? { key: 'auth.validation.confirmRequired' }
        : confirm !== password
          ? { key: 'auth.validation.mismatch' }
          : null,
    }
    setErrors(next)
    setFormError(null)
    const firstInvalid = [
      [next.email, emailRef],
      [next.password, passwordRef],
      [next.confirm, confirmRef],
    ].find(([error]) => error)
    if (firstInvalid) return firstInvalid[1].current?.focus()

    setLoading(true)
    try {
      await register(email.trim(), password)
      navigate('/login', { replace: true, state: { registered: true, email: email.trim() } })
    } catch (error) {
      setFormError(error)
      setPassword('')
      setConfirm('')
      setLoading(false)
    }
  }

  return (
    <AuthLayout
      title={t('auth.register.title')}
      description={t('auth.register.description')}
      footer={
        <>
          {t('auth.register.haveAccount')}{' '}
          <Link to="/login" className="font-semibold text-brand underline-offset-4 hover:underline">
            {t('auth.register.logIn')}
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        {formError && (
          <Alert
            tone="danger"
            title={t('auth.register.errorTitle')}
            action={
              formError.status === 409 && (
                <Link to="/login" state={{ email: email.trim() }} className="font-semibold underline underline-offset-4">
                  {t('auth.register.logInInstead')}
                </Link>
              )
            }
          >
            {t(formError.key ?? 'errors.generic')}
          </Alert>
        )}

        <Field id="register-email" label={t('auth.fields.email')} error={message(errors.email)}>
          <Input
            ref={emailRef}
            id="register-email"
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

        <Field
          id="register-password"
          label={t('auth.fields.password')}
          hint={t('auth.register.passwordHint', { min: PASSWORD_MIN })}
          error={message(errors.password)}
        >
          <PasswordInput
            ref={passwordRef}
            id="register-password"
            autoComplete="new-password"
            maxLength={PASSWORD_MAX}
            value={password}
            onChange={(e) => {
              setPassword(e.target.value)
              clearError('password')
            }}
            hint
            error={message(errors.password)}
          />
        </Field>

        <Field id="register-confirm" label={t('auth.fields.confirm')} error={message(errors.confirm)}>
          <PasswordInput
            ref={confirmRef}
            id="register-confirm"
            autoComplete="new-password"
            maxLength={PASSWORD_MAX}
            value={confirm}
            onChange={(e) => {
              setConfirm(e.target.value)
              clearError('confirm')
            }}
            error={message(errors.confirm)}
          />
        </Field>

        <Button type="submit" block loading={loading} loadingText={t('auth.register.submitting')}>
          {t('auth.register.submit')}
        </Button>
      </form>
    </AuthLayout>
  )
}
