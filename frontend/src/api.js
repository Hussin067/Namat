// All calls to the Namat API go through this file.
// VITE_ variables are bundled into public JavaScript: never put secrets in them.
export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
).replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

// Turn FastAPI error bodies into one short, user-friendly sentence.
function errorMessage(status, body) {
  if (status === 422) return 'Please check the email and password and try again.'
  if (typeof body?.detail === 'string') return body.detail
  if (status >= 500) return 'The server had a problem. Please try again later.'
  return 'Something went wrong. Please try again.'
}

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options)
  } catch {
    throw new ApiError('Cannot reach the server. Is the backend running?', 0)
  }
  const body = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(errorMessage(response.status, body), response.status)
  return body
}

export function registerUser(email, password) {
  return request('/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
}

// OAuth2 password flow: form-encoded, with the email in the "username" field.
export function loginUser(email, password) {
  return request('/auth/login', {
    method: 'POST',
    body: new URLSearchParams({ username: email, password }),
  })
}

export function fetchCurrentUser(token) {
  return request('/auth/me', {
    headers: { Authorization: `Bearer ${token}` },
  })
}
