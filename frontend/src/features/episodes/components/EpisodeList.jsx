import { Link } from 'react-router'
import { ChevronRight, Clock, MapPin, Pill, Sparkles } from 'lucide-react'
import { useI18n } from '../../../i18n/i18n-context.js'
import { durationMinutes, formatDateTime, formatDuration } from '../format.js'
import IntensityBadge from './IntensityBadge.jsx'

function Meta({ icon: Icon, children }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <Icon aria-hidden="true" className="size-4 shrink-0" />
      {children}
    </span>
  )
}

/** Episodes as a readable list. Works from narrow phones up to desktop. */
export default function EpisodeList({ episodes, showDetails = true }) {
  const { t, locale } = useI18n()
  return (
    <ul className="divide-y divide-line">
      {episodes.map((episode) => {
        const duration = formatDuration(durationMinutes(episode), locale) ?? t('episode.ongoing')
        const meds = episode.medications ?? []
        return (
          <li key={episode.id} className="px-5 py-4 sm:px-6">
            <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
              <div className="min-w-0">
                <p className="font-semibold text-ink">
                  {episode.isDemo ? (
                    <time dateTime={episode.started_at}>{formatDateTime(episode.started_at, locale)}</time>
                  ) : (
                    <Link
                      to={`/episodes/${episode.id}`}
                      className="inline-flex items-center gap-1 underline-offset-4 hover:text-brand hover:underline"
                    >
                      <time dateTime={episode.started_at}>{formatDateTime(episode.started_at, locale)}</time>
                      <ChevronRight aria-hidden="true" className="size-4 text-ink-muted rtl:-scale-x-100" />
                    </Link>
                  )}
                </p>
                <p className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-muted">
                  <Meta icon={Clock}>
                    <span className="sr-only">{t('episode.duration')} </span>
                    {duration}
                  </Meta>
                  {episode.pain_location && (
                    <Meta icon={MapPin}>
                      <span className="sr-only">{t('episode.location')} </span>
                      {t(`locations.${episode.pain_location}`)}
                    </Meta>
                  )}
                  {episode.had_aura && <Meta icon={Sparkles}>{t('episode.withAura')}</Meta>}
                  {showDetails && meds.length > 0 && (
                    <Meta icon={Pill}>
                      <span className="sr-only">{t('episode.medication')} </span>
                      {new Intl.ListFormat(locale).format(meds.map((m) => m.medication_name))}
                    </Meta>
                  )}
                </p>
              </div>
              <div className="shrink-0">
                <span className="sr-only">{t('episode.peak')} </span>
                <IntensityBadge value={episode.peak_intensity} />
              </div>
            </div>

            {showDetails && episode.symptoms?.length > 0 && (
              <ul aria-label={t('episode.symptoms')} className="mt-3 flex flex-wrap gap-1.5">
                {episode.symptoms.map((symptom) => (
                  <li key={symptom} className="rounded-full border border-line px-2.5 py-0.5 text-xs text-ink-muted">
                    {t(`symptoms.${symptom}`)}
                  </li>
                ))}
              </ul>
            )}
            {showDetails && episode.notes && <p className="mt-3 text-sm text-ink-muted">{episode.notes}</p>}
          </li>
        )
      })}
    </ul>
  )
}
