// Must match the backend rules in backend/app/schemas/auth.py.
// Validators return null, or { key, vars } naming a translated message.
export const PASSWORD_MIN = 12
export const PASSWORD_MAX = 128

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function validateEmail(email) {
  if (!email.trim()) return { key: 'auth.validation.emailRequired' }
  if (!EMAIL_PATTERN.test(email.trim())) return { key: 'auth.validation.emailInvalid' }
  return null
}

export function validateNewPassword(password) {
  if (!password) return { key: 'auth.validation.newPasswordRequired' }
  if (password.length < PASSWORD_MIN) {
    return { key: 'auth.validation.passwordTooShort', vars: { min: PASSWORD_MIN, count: password.length } }
  }
  if (password.length > PASSWORD_MAX) return { key: 'auth.validation.passwordTooLong', vars: { max: PASSWORD_MAX } }
  return null
}
