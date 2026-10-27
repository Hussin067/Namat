import { useState } from 'react'

const PASSWORD_MIN = 12
const PASSWORD_MAX = 128
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function validate(mode, email, password, confirm) {
  if (!EMAIL_PATTERN.test(email.trim())) return 'Enter a valid email address.'
  if (mode === 'login') return password ? null : 'Enter your password.'
  if (password.length < PASSWORD_MIN) return `Password must be at least ${PASSWORD_MIN} characters.`
  if (password.length > PASSWORD_MAX) return `Password must be at most ${PASSWORD_MAX} characters.`
  if (password !== confirm) return 'Passwords do not match.'
  return null
}

const inputClass =
  'mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 ' +
  'focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200'

export default function AuthForm({ mode, onModeChange, onSubmit, notice }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const isRegister = mode === 'register'

  function switchMode(next) {
    setError(null)
    setPassword('')
    setConfirm('')
    onModeChange(next)
  }

  async function handleSubmit(event) {
    event.preventDefault()
    const problem = validate(mode, email, password, confirm)
    if (problem) {
      setError(problem)
      return
    }
    setError(null)
    setLoading(true)
    try {
      await onSubmit(email.trim(), password)
    } catch (err) {
      setError(err.message)
    } finally {
      // Don't keep the password in memory longer than needed.
      setPassword('')
      setConfirm('')
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <div className="flex rounded-lg bg-slate-100 p-1 text-sm font-medium">
        {['login', 'register'].map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => switchMode(tab)}
            className={`flex-1 rounded-md py-2 transition ${
              mode === tab ? 'bg-white text-indigo-600 shadow' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {tab === 'login' ? 'Log in' : 'Create account'}
          </button>
        ))}
      </div>

      {notice && (
        <p role="status" className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          {notice}
        </p>
      )}

      <label className="block text-sm font-medium text-slate-700">
        Email
        <input
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className={inputClass}
        />
      </label>

      <label className="block text-sm font-medium text-slate-700">
        Password
        <input
          type="password"
          autoComplete={isRegister ? 'new-password' : 'current-password'}
          maxLength={PASSWORD_MAX}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className={inputClass}
        />
        {isRegister && (
          <span className="mt-1 block text-xs font-normal text-slate-500">
            At least {PASSWORD_MIN} characters. A few random words make a strong passphrase.
          </span>
        )}
      </label>

      {isRegister && (
        <label className="block text-sm font-medium text-slate-700">
          Confirm password
          <input
            type="password"
            autoComplete="new-password"
            maxLength={PASSWORD_MAX}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className={inputClass}
          />
        </label>
      )}

      {error && (
        <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-lg bg-indigo-600 py-2.5 font-semibold text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? 'Please wait…' : isRegister ? 'Create account' : 'Log in'}
      </button>
    </form>
  )
}
