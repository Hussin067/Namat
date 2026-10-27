// Turns one insight from the API into translated text. The wording comes from
// the translation files, keyed by the insight's id; every number comes from
// the insight's own `evidence`, never from defaults or examples.

const SAMPLE_UNIT = {
  frequency: 'episodes',
  intensity: 'episodes',
  timing: 'episodes',
  symptoms: 'episodes',
  sleep: 'days',
  factors: 'days',
  medication: 'doses',
}

// Categories whose evidence is the user's episodes (they get a "See your episodes" link).
export const EPISODE_CATEGORIES = new Set(['frequency', 'intensity', 'timing', 'symptoms'])

/** Returns { title, description, facts: [{ label, value }], note?, sample }. */
export function describeInsight(insight, t, locale) {
  const e = insight.evidence
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 })
  const percent = (rate) => new Intl.NumberFormat(locale, { style: 'percent', maximumFractionDigits: 0 }).format(rate)
  const episodes = (count) => t('dashboard.charts.episodeCount', { count })
  const symptom = (name) => t(`symptoms.${name}`)
  const ratio = (hits, total, rate) => t('insights.facts.ratio', { hits, total, rate: percent(rate) })
  const sample = t(`insights.sample.${SAMPLE_UNIT[insight.category]}`, { count: insight.sample_size })
  const id = insight.id

  if (insight.category === 'frequency') {
    const kind = id.replace('frequency_', '') // increase | decrease | stable
    return {
      title: t(`insights.frequency.${kind}Title`),
      description: t('insights.frequency.body', { current: episodes(e.current), previous: episodes(e.previous), days: e.days }),
      facts: [
        { label: t('insights.facts.thisPeriod'), value: number.format(e.current) },
        { label: t('insights.facts.previousDays', { days: e.days }), value: number.format(e.previous) },
      ],
      sample,
    }
  }

  if (insight.category === 'intensity') {
    const kind = id.replace('intensity_', '') // higher | lower
    return {
      title: t(`insights.intensity.${kind}Title`),
      description: t('insights.intensity.body', { current: number.format(e.current), previous: number.format(e.previous), days: e.days }),
      facts: [
        { label: t('insights.facts.thisPeriod'), value: t('insights.facts.avgIntensity', { value: number.format(e.current) }) },
        { label: t('insights.facts.previousDays', { days: e.days }), value: t('insights.facts.avgIntensity', { value: number.format(e.previous) }) },
      ],
      sample,
    }
  }

  if (insight.category === 'timing') {
    const part = t(`insights.time.parts.${e.part_of_day}`)
    return {
      title: t('insights.time.title', { part }),
      description: t('insights.time.body', { count: e.count, total: e.total, part }),
      facts: ['morning', 'afternoon', 'evening', 'night'].map((p) => ({
        label: t(`insights.time.labels.${p}`),
        value: number.format(e.counts[p] ?? 0),
      })),
      sample,
    }
  }

  if (id === 'symptom_common') {
    return {
      title: t('insights.symptoms.commonTitle'),
      description: t('insights.symptoms.commonBody', { symptom: symptom(e.symptom), count: e.count, total: e.total }),
      facts: [
        { label: t('insights.facts.thisPeriod'), value: ratio(e.count, e.total, e.count / e.total) },
        { label: t('insights.symptoms.previous'), value: number.format(e.previous_count) },
      ],
      sample,
    }
  }

  if (id === 'symptom_pair') {
    const [a, b] = e.symptoms.map(symptom)
    return {
      title: t('insights.symptoms.pairTitle'),
      description: t('insights.symptoms.pairBody', { a, b, count: e.count, total: e.total }),
      facts: [{ label: t('insights.facts.thisPeriod'), value: ratio(e.count, e.total, e.count / e.total) }],
      sample,
    }
  }

  if (insight.category === 'sleep') {
    const hours = number.format(e.median_hours)
    const byRate = e.comparison_type === 'rate'
    const shorterHits = Math.round(e.shorter_headache_rate * e.shorter_nights)
    const otherHits = Math.round(e.other_headache_rate * e.other_nights)
    return {
      title: t('insights.sleep.title'),
      description: byRate
        ? t('insights.sleep.rateBody', { a: percent(e.shorter_headache_rate), b: percent(e.other_headache_rate), hours })
        : t('insights.sleep.intensityBody', {
            a: number.format(e.shorter_avg_intensity),
            b: number.format(e.other_avg_intensity),
            hours,
          }),
      facts: [
        { label: t('insights.facts.afterShorter'), value: ratio(shorterHits, e.shorter_nights, e.shorter_headache_rate) },
        { label: t('insights.facts.afterLonger'), value: ratio(otherHits, e.other_nights, e.other_headache_rate) },
      ],
      sample,
    }
  }

  if (insight.category === 'factors') {
    const a = t(`insights.factors.groups.${e.factor}.a`)
    const b = t(`insights.factors.groups.${e.factor}.b`)
    const byRate = e.comparison_type === 'rate'
    const aHits = Math.round(e.group_a_headache_rate * e.group_a_days)
    const bHits = Math.round(e.group_b_headache_rate * e.group_b_days)
    return {
      title: t('insights.factors.title'),
      description: byRate
        ? t('insights.factors.rateBody', { a, b, aRate: percent(e.group_a_headache_rate), bRate: percent(e.group_b_headache_rate) })
        : t('insights.factors.intensityBody', {
            a,
            b,
            aAvg: number.format(e.group_a_avg_intensity),
            bAvg: number.format(e.group_b_avg_intensity),
          }),
      facts: [
        { label: a, value: ratio(aHits, e.group_a_days, e.group_a_headache_rate) },
        { label: b, value: ratio(bHits, e.group_b_days, e.group_b_headache_rate) },
      ],
      sample,
    }
  }

  if (insight.category === 'medication') {
    return {
      title: t('insights.medication.title'),
      description: t('insights.medication.body', {
        doses: t('insights.medication.doseCount', { count: e.doses }),
        top: e.top_medication, // the user's own wording, shown as plain text
        topDoses: number.format(e.top_medication_doses),
        withMedication: number.format(e.episodes_with_medication),
        total: number.format(e.total_episodes),
      }),
      facts: [],
      note: t('insights.medication.note'),
      sample,
    }
  }

  return null // an insight type this version of the app doesn't know: skip it rather than guess
}
