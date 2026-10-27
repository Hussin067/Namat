import { useState } from 'react'
import { Lightbulb, LoaderCircle, SearchX, Sprout } from 'lucide-react'
import Button from '../../components/ui/Button.jsx'
import Card from '../../components/ui/Card.jsx'
import { EmptyState, ErrorState } from '../../components/ui/States.jsx'
import { cx } from '../../components/ui/styles.js'
import { useI18n } from '../../i18n/i18n-context.js'
import { formatRange } from '../analytics/format.js'
import { describeInsight } from './describeInsight.js'
import InsightCard from './InsightCard.jsx'
import { useInsights } from './useInsights.js'

const VISIBLE = 4 // the most useful insights first; the rest on request

function Skeleton() {
  const { t } = useI18n()
  return (
    <div role="status" className="grid gap-4 lg:grid-cols-2">
      <span className="sr-only">{t('insights.loading')}</span>
      {[0, 1].map((i) => (
        <div key={i} aria-hidden="true" className="h-56 rounded-2xl border border-line bg-surface shadow-card motion-safe:animate-pulse" />
      ))}
    </div>
  )
}

function Gaps({ gaps }) {
  const { t } = useI18n()
  if (!gaps.length) return null
  return (
    <div className="rounded-2xl border border-dashed border-line px-5 py-4">
      <h3 className="flex items-center gap-2 text-base font-semibold text-ink">
        <Sprout aria-hidden="true" className="size-4 text-brand" />
        {t('insights.gapsTitle')}
      </h3>
      <ul className="mt-2 list-disc space-y-1.5 ps-5 text-sm text-ink-muted">
        {gaps.map((gap) => (
          <li key={gap.code}>{t(`insights.gaps.${gap.code}`, { needed: gap.needed, have: gap.have })}</li>
        ))}
      </ul>
    </div>
  )
}

/** "Your insights" on the dashboard, driven by the same date filters as the charts. */
export default function InsightsSection({ filters }) {
  const { t, locale } = useI18n()
  const { status, data, error, refreshing, retry } = useInsights(filters)
  const [showAll, setShowAll] = useState(false)

  let body
  if (status === 'loading') body = <Skeleton />
  else if (status === 'error' && !data) {
    body = (
      <Card>
        <ErrorState title={t('insights.loadError')} message={t(error?.key ?? 'errors.generic')} onRetry={retry} />
      </Card>
    )
  } else {
    // Only insight types this app version can describe; never placeholders.
    const insights = data.insights.filter((i) => describeInsight(i, t, locale))
    const episodesGap = data.data_gaps.find((g) => g.code === 'episodes')
    const otherGaps = data.data_gaps.filter((g) => g.code !== 'episodes')
    const visible = showAll ? insights : insights.slice(0, VISIBLE)

    body = (
      <div className="space-y-4">
        {data.data_status === 'insufficient' ? (
          <Card>
            <EmptyState icon={SearchX} title={t('insights.insufficientTitle')}>
              {t('insights.insufficientBody', { needed: episodesGap?.needed ?? '', have: episodesGap?.have ?? 0 })}
            </EmptyState>
          </Card>
        ) : insights.length === 0 ? (
          <Card>
            <EmptyState icon={Lightbulb} title={t('insights.noPatternsTitle')}>
              {t('insights.noPatternsBody')}
            </EmptyState>
          </Card>
        ) : (
          <>
            <div className="grid gap-4 lg:grid-cols-2">
              {visible.map((insight) => (
                <InsightCard key={insight.id} insight={insight} />
              ))}
            </div>
            {insights.length > VISIBLE && (
              <Button variant="ghost" size="sm" onClick={() => setShowAll((v) => !v)} aria-expanded={showAll}>
                {showAll ? t('insights.showFewer') : t('insights.showAll', { count: insights.length })}
              </Button>
            )}
          </>
        )}
        <Gaps gaps={otherGaps} />
        <div className="space-y-1 text-sm text-ink-muted">
          <p>{t('insights.disclaimer')}</p>
          <p>
            <strong className="font-semibold">{t('insights.levels.observed')}:</strong> {t('insights.levels.observedHelp')}{' '}
            <strong className="font-semibold">{t('insights.levels.limited')}:</strong> {t('insights.levels.limitedHelp')}
          </p>
        </div>
      </div>
    )
  }

  return (
    <section aria-labelledby="insights-heading" className="space-y-4">
      <div>
        <h2 id="insights-heading" className="text-xl font-semibold text-ink">
          {t('insights.title')}
        </h2>
        <p className="mt-1 text-ink-muted">{t('insights.intro')}</p>
        <div className="mt-1 flex min-h-6 flex-wrap items-center gap-x-3 text-sm text-ink-muted">
          {data && <span>{formatRange(data.period.start, data.period.end, locale)}</span>}
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
      </div>
      <div className={cx('transition-opacity duration-200', refreshing && 'opacity-60')} aria-busy={refreshing || undefined}>
        {body}
      </div>
    </section>
  )
}
