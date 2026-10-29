// All calls to the Namat API go through this file.
// VITE_ variables are bundled into public JavaScript: never put secrets in them.
//
// The API is reached at /api on the app's own site: the Vite dev server proxies
// it to http://localhost:8000 (vite.config.js) and Vercel rewrites it to the
// Render API (vercel.json). Same site means the session cookie is first-party.
// VITE_API_BASE_URL can point somewhere else (that needs the cross-site cookie
// settings described in backend/app/core/config.py).
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '')

// Sessions live in an HttpOnly cookie set by the API, which JavaScript can't read.
// The readable CSRF cookie holds a per-session value that requests changing data
// must echo in the X-CSRF-Token header. (__Host- names are used over HTTPS.)
const CSRF_COOKIES = ['__Host-namat_csrf', 'namat_csrf']
const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

function readCsrfToken() {
  const cookies = Object.fromEntries(
    document.cookie
      .split(';')
      .map((part) => part.trim().split('='))
      .filter(([name]) => name)
      .map(([name, ...rest]) => [name, decodeURIComponent(rest.join('='))]),
  )
  const name = CSRF_COOKIES.find((n) => cookies[n])
  return name ? cookies[name] : null
}

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

async function request(path, { responseType, method = 'GET', headers = {}, ...options } = {}) {
  const allHeaders = { ...headers }
  if (UNSAFE_METHODS.has(method)) {
    const csrf = readCsrfToken()
    if (csrf) allHeaders['X-CSRF-Token'] = csrf
  }
  let response
  try {
    // credentials: 'include' sends the session cookie (also when the API is on another origin).
    response = await fetch(`${API_BASE_URL}${path}`, { ...options, method, headers: allHeaders, credentials: 'include' })
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

/**
 * Form-encoded, with the email in the "username" field. The API answers with
 * { user, expires_at } and sets the session cookies; the token never reaches JavaScript.
 */
export function loginUser(email, password) {
  return request('/auth/login', {
    method: 'POST',
    body: new URLSearchParams({ username: email, password }),
  })
}

/** The current session ({ user, expires_at }) if the cookie is valid; throws 401 otherwise. */
export function fetchSession({ signal } = {}) {
  return request('/auth/session', { signal })
}

export function fetchCurrentUser() {
  return request('/auth/me')
}

/** Ends the session on the server (expires both cookies). */
export function logoutUser() {
  return request('/auth/logout', { method: 'POST' })
}

/**
 * A request on behalf of the signed-in user. Pages don't call this directly:
 * they use `authRequest` from useAuth(), which ends the session on a 401.
 * Resolves to the parsed JSON body (null for 204 No Content), or, with
 * responseType: 'file', to { blob, filename }.
 * Pass an AbortController `signal` to cancel a request that is no longer needed.
 */
export function apiRequest(path, { method = 'GET', body, signal, responseType } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  return request(path, {
    method,
    headers,
    signal,
    responseType,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}
