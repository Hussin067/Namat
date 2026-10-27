// Service boundary for episode data (backend: /episodes and /symptoms).
//
// Every function takes `request`, the authRequest helper from useAuth(). It
// adds the access token, so the token never passes through page code. The
// server decides ownership from that token; nothing here sends a user id.

/** Episodes come back from the API with symptom objects; the UI works with names. */
export function fromApiEpisode(episode) {
  return {
    ...episode,
    symptoms: episode.symptoms.map((s) => s.name),
    medications: episode.medications.map((m) => ({
      ...m,
      dose_amount: m.dose_amount == null ? null : Number(m.dose_amount),
    })),
  }
}

// The symptom catalog is the same for everyone, so one copy per page load is enough.
let catalogPromise = null
export function loadSymptomCatalog(request) {
  if (!catalogPromise) {
    catalogPromise = request('/symptoms').catch((error) => {
      catalogPromise = null // allow a retry
      throw error
    })
  }
  return catalogPromise
}

export async function listEpisodes(request, { limit = 100, offset = 0 } = {}) {
  const page = await request(`/episodes?limit=${limit}&offset=${offset}`)
  return { ...page, items: page.items.map(fromApiEpisode) }
}

export async function getEpisode(request, id) {
  return fromApiEpisode(await request(`/episodes/${encodeURIComponent(id)}`))
}

/** Resolves only after the server confirms the episode was stored. */
export async function createEpisode(request, payload) {
  return fromApiEpisode(await request('/episodes', { method: 'POST', body: payload }))
}

export async function updateEpisode(request, id, payload) {
  return fromApiEpisode(await request(`/episodes/${encodeURIComponent(id)}`, { method: 'PATCH', body: payload }))
}

export function deleteEpisode(request, id) {
  return request(`/episodes/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

/**
 * Form state → API body. The same full body is used to create and to edit
 * (PATCH replaces symptoms and medications with exactly what's sent).
 * `catalog` maps symptom names to the ids the API expects.
 */
export function toEpisodePayload(form, catalog = []) {
  const iso = (local) => (local ? new Date(local).toISOString() : null)
  const idByName = new Map(catalog.map((s) => [s.name, s.id]))
  const edited = form.medicationName.trim()
    ? [
        {
          medication_name: form.medicationName.trim(),
          dose_amount: form.doseAmount === '' ? null : Number(form.doseAmount),
          dose_unit: form.doseUnit.trim() || null,
          taken_at: iso(form.medicationTakenAt),
          relief_rating: form.medicationRelief,
        },
      ]
    : []
  return {
    started_at: iso(form.startedAt),
    ended_at: form.ongoing ? null : iso(form.endedAt),
    peak_intensity: form.intensity,
    pain_location: form.location || null,
    had_aura: form.hadAura,
    notes: form.notes.trim() || null,
    symptom_ids: form.symptoms.map((name) => idByName.get(name)).filter((id) => id != null),
    // The form edits one dose; any others already on the episode are kept as they are.
    medications: [...edited, ...form.otherMedications],
  }
}
