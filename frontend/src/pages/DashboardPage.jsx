import { Link, useSearchParams } from 'react-router'
import { CalendarDays, CirclePlus, Gauge, History, LoaderCircle, NotebookPen, Timer } from 'lucide-react'
import { useAuth } from '../auth/auth-context.js'
import HeadacheFrequencyChart from '../components/charts/HeadacheFrequencyChart.jsx'
import IntensityTrendChart from '../components/charts/IntensityTrendChart.jsx'
import SymptomDistributionChart from '../components/charts/SymptomDistributionChart.jsx'
import Button, { ButtonLink } from '../components/ui/Button.jsx'
import Card, { CardHeader } from '../components/ui/Card.jsx'
import PageHeader from '../components/ui/PageHeader.jsx'
import { EmptyState, ErrorState } from '../components/ui/States.jsx'
import { cx } from '../components/ui/styles.js'
import { filtersFromSearch, filtersToSearch } from '../features/analytics/analyticsService.js'
import DateRangeFilter from '../features/analytics/DateRangeFilter.jsx'
import { formatRange } from '../features/analytics/format.js'
import InsightsSection from '../features/insights/InsightsSection.jsx'
import { useDashboardAnalytics } from '../features/analytics/useDashboardAnalytics.js'
import EpisodeList from '../features/episodes/components/EpisodeList.jsx'
import IntensityBadge from '../features/episodes/components/IntensityBadge.jsx'
import { intensityInfo } from '../features/episodes/constants.js'
import { formatDateTime, formatDuration } from '../features/episodes/format.js'
import { useEpisodes } from '../features/episodes/useEpisodes.js'
import { useI18n } from '../i18n/i18n-context.js'

function greetingKey(now = new Date()) {
  const hour = now.getHours()
  if (hour < 12) return 'dashboard.greeting.morning'
  if (hour < 18) return 'dashboard.greeting.afternoon'
  return 'dashboard.greeting.evening'
}

function MetricCard({ icon: Icon, label, value, detail, muted }) {
  return (
    <Card as="div" className="p-5">
      <p className="flex items-center gap-2 text-sm font-medium text-ink-muted">
        <Icon aria-hidden="true" className="size-4" />
        {label}
      </p>
      <p
        className={cx(
          'mt-3 font-display text-[1.75rem] leading-tight font-semibold text-balance tabular-nums',
          muted ? 'text-ink-muted' : 'text-ink',
        )}
      >
        {value}
      </p>
      {detail && <p className="mt-1 text-sm text-ink-muted">{detail}</p>}
    </Card>
  )
}

/** Placeholder shapes with the same footprint as the real content, so nothing jumps on load. */
function DashboardSkeleton() {
  const { t } = useI18n()
  const block = 'rounded-2xl border border-line bg-surface shadow-card motion-safe:animate-pulse'
  return (
    <div role="status" aria-live="polite">
      <span className="sr-only">{t('dashboard.loading')}</span>
      <div aria-hidden="true" className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className={cx(block, 'h-[8.5rem]')} />
          ))}
        </div>
        <div className="grid gap-6 lg:grid-cols-2">
          <div className={cx(block, 'h-80')} />
          <div className={cx(block, 'h-80')} />
        </div>
      </div>
    </div>
  )
}

function Summary({ data }) {
  const { t, locale } = useI18n()
  const s = data.summary
  const unavailable = t('dashboard.metrics.unavailable')
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard
        icon={NotebookPen}
        label={t('dashboard.metrics.episodes')}
        value={s.total_episodes}
        detail={formatRange(data.range.start_date, data.range.end_date, locale)}
      />
      <MetricCard
        icon={CalendarDays}
        label={t('dashboard.metrics.headacheDays')}
        value={s.headache_days}
        detail={t('dashboard.metrics.headacheDaysDetail', { count: data.range.days })}
      />
      <MetricCard
        icon={Gauge}
        label={t('dashboard.metrics.avgIntensity')}
        muted={s.average_intensity == null}
        value={s.average_intensity == null ? unavailable : <span dir="ltr">{t('intensity.badge', { value: s.average_intensity })}</span>}
        detail={
          s.average_intensity == null
            ? t('dashboard.metrics.noRatings')
            : t('dashboard.metrics.onAverage', { label: t(intensityInfo(Math.round(s.average_intensity)).key) })
        }
      />
      <MetricCard
        icon={Timer}
        label={t('dashboard.metrics.avgDuration')}
        muted={s.average_duration_minutes == null}
        value={s.average_duration_minutes == null ? unavailable : formatDuration(s.average_duration_minutes, locale)}
        detail={
          s.average_duration_minutes == null
            ? t('dashboard.metrics.noDuration')
            : t('dashboard.metrics.durationDetail', { count: s.episodes_with_duration })
        }
      />
    </div>
  )
}

export default function DashboardPage() {
  const { user } = useAuth()
  const { t, locale } = useI18n()
  // The period lives in the URL, so it survives navigating away and back.
  const [searchParams, setSearchParams] = useSearchParams()
  const filters = filtersFromSearch(searchParams)
  const analytics = useDashboardAnalytics(filters)
  // Real records only (never demo data), so this list always matches the analytics.
  const recent = useEpisodes({ limit: 4, includeDemo: false })

  const setFilters = (next) => setSearchParams(filtersToSearch(next), { replace: true })
  const greeting = t(greetingKey())
  const name = user?.display_name
  const { status, data, error, refreshing, retry } = analytics
  const hasAnyEpisodes = recent.status === 'ready' && recent.total > 0
  const firstTime = status === 'ready' && data.summary.total_episodes === 0 && recent.status === 'ready' && !hasAnyEpisodes

  const logAction = (
    <ButtonLink to="/log" icon={CirclePlus}>
      {t('nav.log')}
    </ButtonLink>
  )

  let body
  if (status === 'loading') body = <DashboardSkeleton />
  else if (status === 'error' && !data) {
    body = (
      <Card>
        <ErrorState title={t('dashboard.loadError')} message={t(error?.key ?? 'errors.generic')} onRetry={retry} />
      </Card>
    )
  } else if (firstTime) {
    body = (
      <Card>
        <EmptyState icon={NotebookPen} title={t('dashboard.emptyTitle')} action={logAction}>
          {t('dashboard.emptyBody')}
        </EmptyState>
      </Card>
    )
  } else if (data.summary.total_episodes === 0) {
    body = (
      <Card>
        <EmptyState
          icon={CalendarDays}
          title={t('dashboard.emptyRangeTitle')}
          action={
            <div className="flex flex-wrap justify-center gap-3">
              {filters.period !== '6m' && (
                <Button variant="secondary" onClick={() => setFilters({ period: '6m' })}>
                  {t('dashboard.showSixMonths')}
                </Button>
              )}
              {logAction}
            </div>
          }
        >
          {t('dashboard.emptyRangeBody')}
        </EmptyState>
      </Card>
    )
  } else {
    const latest = data.summary.latest_episode
    body = (
      <div className="space-y-6">
        <Summary data={data} />

        {latest && (
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink-muted">
            {t('dashboard.latest')}
            <Link to={`/episodes/${latest.id}`} className="font-semibold text-brand underline-offset-4 hover:underline">
              {formatDateTime(latest.started_at, locale)}
            </Link>
            <IntensityBadge value={latest.peak_intensity} />
          </p>
        )}

        <InsightsSection filters={filters} />

        <div className="grid gap-6 lg:grid-cols-2">
          <HeadacheFrequencyChart points={data.frequency} interval={data.range.interval} />
          <IntensityTrendChart points={data.intensity_trend} interval={data.range.interval} />
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <SymptomDistributionChart symptoms={data.symptoms} />
          <Card aria-labelledby="recent-heading">
            <CardHeader
              id="recent-heading"
              title={t('dashboard.recent')}
              action={
                <Link
                  to="/history"
                  className="inline-flex min-h-9 items-center gap-1.5 text-sm font-semibold text-brand underline-offset-4 hover:underline"
                >
                  <History aria-hidden="true" className="size-4" />
                  {t('dashboard.fullHistory')}
                </Link>
              }
            />
            <div className="mt-3">
              <EpisodeList episodes={recent.episodes} showDetails={false} />
            </div>
          </Card>
        </div>

        <p className="text-sm text-ink-muted">{t('dashboard.disclaimer')}</p>
      </div>
    )
  }

  return (
    <>
      <PageHeader
        title={name ? t('dashboard.greetingNamed', { greeting, name }) : greeting}
        description={t('dashboard.description')}
        actions={firstTime ? null : logAction}
      />

      {!firstTime && (
        <section aria-label={t('dashboard.filters.label')} className="mb-8 space-y-3">
          <DateRangeFilter value={filters} onChange={setFilters} disabled={refreshing} />
          <div className="flex min-h-6 flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-muted">
            {data && (
              <span>
                {t('dashboard.rangeSummary', {
                  range: formatRange(data.range.start_date, data.range.end_date, locale),
                  interval: t(`dashboard.intervalNames.${data.range.interval}`),
                  timezone: data.range.timezone,
                })}
              </span>
            )}
            {refreshing && (
              <span role="status" className="inline-flex items-center gap-1.5 font-medium text-ink">
                <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
                {t('dashboard.updating')}
              </span>
            )}
            {status === 'error' && data && (
              <span role="alert" className="inline-flex items-center gap-2 font-medium text-danger">
                {t(error?.key ?? 'errors.generic')}
                <Button variant="ghost" size="sm" onClick={retry}>
                  {t('common.tryAgain')}
                </Button>
              </span>
            )}
          </div>
        </section>
      )}

      <div className={cx('transition-opacity duration-200', refreshing && 'opacity-60')} aria-busy={refreshing || undefined}>
        {body}
      </div>
    </>
  )
}
