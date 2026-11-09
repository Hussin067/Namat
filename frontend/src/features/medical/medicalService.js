// Service boundary for the medical history (backend: /medical-history). Every
// function takes `request`, the authRequest helper from useAuth(); the server
// decides ownership from the session, so nothing here sends a user id.

const BASE = '/medical-history'

/** { conditions, allergies, procedures, notes: { notes, updated_at } } */
export function fetchMedicalHistory(request, { signal } = {}) {
  return request(BASE, { signal })
}

/** kind: 'conditions' | 'allergies' | 'procedures'. Resolves after the server stored it. */
export function createItem(request, kind, payload) {
  return request(`${BASE}/${kind}`, { method: 'POST', body: payload })
}

export function updateItem(request, kind, id, payload) {
  return request(`${BASE}/${kind}/${encodeURIComponent(id)}`, { method: 'PATCH', body: payload })
}

export function deleteItem(request, kind, id) {
  return request(`${BASE}/${kind}/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

/** Replaces the additional notes; null removes them. */
export function saveNotes(request, notes) {
  return request(`${BASE}/notes`, { method: 'PUT', body: { notes } })
}
