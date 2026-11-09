import { Link } from 'react-router'
import { ClipboardPlus } from 'lucide-react'
import Card from '../../components/ui/Card.jsx'
import { useI18n } from '../../i18n/i18n-context.js'
import { contextNames } from './describeItem.js'
import { useMedicalHistory } from './useMedicalHistory.js'

const MAX_NAMES = 4

/**
 * "You reported a history of …" on the dashboard. Renders nothing while
 * loading, on error, or when nothing current was reported.
 */
export default function MedicalHistoryContext() {
  const { t, lang } = useI18n()
  const history = useMedicalHistory()
  if (history.status !== 'ready') return null
  const names = contextNames(history.data.conditions, t)
  if (!names.length) return null

  const shown = names.slice(0, MAX_NAMES)
  const list = new Intl.ListFormat(lang, { type: 'conjunction' }).format(shown)
  const more = names.length - shown.length

  return (
    <Card as="aside" aria-labelledby="medical-context-heading" className="p-5">
      <div className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand-ink">
          <ClipboardPlus aria-hidden="true" className="size-5" />
        </span>
        <div className="min-w-0 space-y-1">
          <h2 id="medical-context-heading" className="font-semibold text-ink">
            {t('medical.context.title')}
          </h2>
          <p className="text-ink">
            {t('medical.context.reported', { list })}
            {more > 0 && ` ${t('medical.context.more', { count: more })}`}
          </p>
          <p className="text-sm text-ink-muted">{t('medical.context.note')}</p>
          <Link to="/medical-history" className="inline-flex min-h-9 items-center text-sm font-semibold text-brand underline-offset-4 hover:underline">
            {t('medical.context.link')}
          </Link>
        </div>
      </div>
    </Card>
  )
}
