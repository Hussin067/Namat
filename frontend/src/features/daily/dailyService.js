// Service boundary for sleep logs and daily factors (backend: /sleep-logs and
// /daily-factors). Like the episode service, every function takes `request`,
// the authRequest helper from useAuth(); the server decides ownership from the
// token, so nothing here sends a user id.

const RESOURCES = { sleep: '/sleep-logs', factors: '/daily-factors' }

export function listEntries(request, kind, { limit = 60, offset = 0, signal } = {}) {
  return request(`${RESOURCES[kind]}?limit=${limit}&offset=${offset}`, { signal })
}

/** Resolves only after the server confirms the entry was stored. */
export function createEntry(request, kind, payload) {
  return request(RESOURCES[kind], { method: 'POST', body: payload })
}

export function updateEntry(request, kind, id, payload) {
  return request(`${RESOURCES[kind]}/${encodeURIComponent(id)}`, { method: 'PATCH', body: payload })
}

export function deleteEntry(request, kind, id) {
  return request(`${RESOURCES[kind]}/${encodeURIComponent(id)}`, { method: 'DELETE' })
}
