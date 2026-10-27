import { Link } from 'react-router'
import { Activity, CalendarDays, Clock, Gauge, ListChecks, Moon, Pill } from 'lucide-react'
import Badge from '../../components/ui/Badge.jsx'
import Card from '../../components/ui/Card.jsx'
import { useI18n } from '../../i18n/i18n-context.js'
import { describeInsight, EPISODE_CATEGORIES } from './describeInsight.js'

const ICONS = {
  frequency: CalendarDays,
  intensity: Gauge,
  timing: Clock,
  symptoms: Activity,
  sleep: Moon,
  factors: ListChecks,
  medication: Pill,
}

/**
 * One observation: what was noticed, the numbers behind it, how much evidence
 * there is, and how many records it rests on. All text is rendered as plain
 * text (React escapes it); nothing is ever injected as HTML.
 */
export default function InsightCard({ insight }) {
  const { t, locale } = useI18n()
  const text = describeInsight(insight, t, locale)
  if (!text) return null
  const Icon = ICONS[insight.category]
  const limited = insight.evidence_level === 'limited'

  return (
    <Card as="article" className="flex min-w-0 flex-col p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-sm font-medium text-ink-muted">
          <Icon aria-hidden="true" className="size-4" />
          {t(`insights.categories.${insight.category}`)}
        </p>
        <Badge tone={limited ? 'neutral' : 'brand'}>{t(`insights.levels.${insight.evidence_level}`)}</Badge>
      </div>

      <h3 className="mt-3 text-lg font-semibold text-ink">{text.title}</h3>
      <p className="mt-1.5 text-ink">{text.description}</p>

      {text.facts.length > 0 && (
        <dl className="mt-4 grid gap-2 rounded-xl bg-sunken px-4 py-3 text-sm">
          {text.facts.map((fact) => (
            <div key={fact.label} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5">
              <dt className="text-ink-muted first-letter:uppercase">{fact.label}</dt>
              <dd dir="auto" className="font-semibold text-ink tabular-nums">
                {fact.value}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {text.note && <p className="mt-3 text-sm text-ink-muted">{text.note}</p>}

      <div className="mt-auto flex flex-wrap items-center justify-between gap-x-4 gap-y-1 pt-4 text-sm text-ink-muted">
        <span>{text.sample}</span>
        {EPISODE_CATEGORIES.has(insight.category) && (
          <Link to="/history" className="font-semibold text-brand underline-offset-4 hover:underline">
            {t('insights.seeEpisodes')}
          </Link>
        )}
      </div>
      {limited && <p className="mt-2 text-sm text-ink-muted">{t('insights.keepTracking')}</p>}
    </Card>
  )
}
