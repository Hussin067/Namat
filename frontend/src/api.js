// All calls to the Namat API go through this file.
// VITE_ variables are bundled into public JavaScript: never put secrets in them.
// In development the API defaults to http://localhost:8000. A production build
// never falls back to localhost: without VITE_API_BASE_URL it calls the API on
// the same origin (e.g. behind a reverse proxy).
export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '')
).replace(/\/$/, '')

/**
 * `key` names a translated message (see src/i18n/messages), so the UI shows
 * errors in the user's language instead of the server's English text.
 */
export class ApiError extends Error {
  constructor(key, status) {
    super(key)
    this.key = key
    this.status = status
  }
}

// Map an HTTP failure to one short, user-friendly message key.
function errorKey(status, path) {
  if (status === 401) return path === '/auth/login' ? 'errors.badLogin' : 'errors.sessionExpired'
  if (status === 404) return 'errors.notFound'
  if (status === 409) return path.startsWith('/auth') ? 'errors.emailTaken' : 'errors.duplicateDate'
  if (status === 422) return path.startsWith('/auth') ? 'errors.checkInput' : 'errors.invalidData'
  if (status === 429) return 'errors.tooManyAttempts'
  if (status >= 500) return 'errors.server'
  return 'errors.generic'
}

async function request(path, { responseType, ...options } = {}) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options)
  } catch (error) {
    if (error?.name === 'AbortError') throw error // cancelled on purpose: not a failure
    throw new ApiError('errors.network', 0)
  }
  if (response.ok && responseType === 'file') return readFile(response)
  const body = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(errorKey(response.status, path), response.status)
  return body
}

/** A downloaded file: its contents and the server's suggested (already safe) file name. */
async function readFile(response) {
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? null
  return { blob: await response.blob(), filename }
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

/**
 * A request on behalf of the signed-in user. Pages don't call this directly:
 * they use `authRequest` from useAuth(), which supplies the token without ever
 * exposing it. Resolves to the parsed JSON body (null for 204 No Content), or,
 * with responseType: 'file', to { blob, filename }.
 * Pass an AbortController `signal` to cancel a request that is no longer needed.
 */
export function apiRequest(path, { token, method = 'GET', body, signal, responseType } = {}) {
  const headers = { Authorization: `Bearer ${token}` }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  return request(path, {
    method,
    headers,
    signal,
    responseType,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}
