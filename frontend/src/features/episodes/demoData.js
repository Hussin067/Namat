// DEVELOPMENT-ONLY DEMO DATA.
// Invented records for previewing the dashboard and history layouts while the
// backend has no episode endpoints. They are never sent to the server, never
// shown unless "demo data" is switched on in development, and always labelled.

const HOUR = 60 * 60 * 1000
const DAY = 24 * HOUR

// [days ago, start hour, duration hours (null = ongoing), intensity, location, aura, symptoms, medication]
const SEEDS = [
  [0.3, 9, null, 5, 'left', false, ['Sensitivity to light', 'Throbbing pain'], null],
  [3, 14, 6, 7, 'left', true, ['Visual aura', 'Nausea', 'Sensitivity to light'], ['Sample pain reliever', 400, 'mg']],
  [6, 8, 3, 4, 'frontal', false, ['Neck pain or stiffness', 'Fatigue'], null],
  [11, 17, 9, 8, 'behind_eye', false, ['Nausea', 'Sensitivity to sound', 'Throbbing pain'], ['Sample pain reliever', 400, 'mg']],
  [15, 11, 2, 3, 'bilateral', false, ['Difficulty concentrating'], null],
  [19, 7, 14, 9, 'right', true, ['Visual aura', 'Vomiting', 'Sensitivity to light'], ['Sample triptan', 50, 'mg']],
  [26, 16, 4, 5, 'occipital', false, ['Neck pain or stiffness', 'Dizziness'], null],
  [33, 10, 5, 6, 'left', false, ['Sensitivity to light', 'Pain worse with activity'], ['Sample pain reliever', 400, 'mg']],
  [41, 13, 3, 4, 'frontal', false, ['Fatigue'], null],
  [48, 9, 11, 8, 'left', true, ['Visual aura', 'Nausea'], ['Sample triptan', 50, 'mg']],
  [57, 15, 2, 3, 'bilateral', false, ['Difficulty concentrating', 'Fatigue'], null],
  [66, 8, 7, 7, 'behind_eye', false, ['Sensitivity to light', 'Throbbing pain'], ['Sample pain reliever', 400, 'mg']],
]

export function createDemoEpisodes(now = new Date()) {
  return SEEDS.map(([daysAgo, hour, hours, intensity, location, aura, symptoms, med], index) => {
    const day = new Date(now.getTime() - Math.floor(daysAgo) * DAY)
    day.setHours(hour, 0, 0, 0)
    const start = daysAgo < 1 ? new Date(now.getTime() - daysAgo * DAY) : day
    return {
      id: `demo-${index + 1}`,
      started_at: start.toISOString(),
      ended_at: hours == null ? null : new Date(start.getTime() + hours * HOUR).toISOString(),
      peak_intensity: intensity,
      pain_location: location,
      had_aura: aura,
      notes: null,
      symptoms,
      medications: med
        ? [{ medication_name: med[0], dose_amount: med[1], dose_unit: med[2], taken_at: new Date(start.getTime() + HOUR).toISOString() }]
        : [],
      isDemo: true,
    }
  })
}
