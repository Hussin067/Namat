import { Pencil, Trash2 } from 'lucide-react'
import Badge from '../../../components/ui/Badge.jsx'
import Button from '../../../components/ui/Button.jsx'
import { useI18n } from '../../../i18n/i18n-context.js'
import { describeItem } from '../describeItem.js'

const CONFIRMATION_TONE = { clinician_confirmed: 'success', self_reported: 'neutral', unsure: 'warning' }

/** One card's items: name, the recorded details, edit and delete. */
export default function HistoryList({ kind, items, onEdit, onDelete }) {
  const { t, locale } = useI18n()
  return (
    <ul className="divide-y divide-line">
      {items.map((item) => {
        const { title, parts } = describeItem(kind, item, t, locale)
        return (
          <li key={item.id} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-start sm:justify-between sm:px-6">
            <div className="min-w-0 space-y-1">
              <p className="font-semibold break-words text-ink" dir="auto">
                {title}
              </p>
              {kind === 'conditions' && (
                <div className="flex flex-wrap gap-1.5">
                  {item.category === 'serious_history' && <Badge tone="brand">{t('medical.categories.serious_history')}</Badge>}
                  <Badge tone={CONFIRMATION_TONE[item.confirmation]}>{t(`medical.confirmationBadges.${item.confirmation}`)}</Badge>
                </div>
              )}
              {parts.length > 0 && <p className="text-sm text-ink-muted">{parts.join(' · ')}</p>}
              {item.reaction && (
                <p className="text-sm break-words text-ink-muted">
                  {t('medical.fields.reaction')}: <span dir="auto">{item.reaction}</span>
                </p>
              )}
              {item.notes && (
                <p className="line-clamp-2 text-sm break-words text-ink-muted" dir="auto">
                  {item.notes}
                </p>
              )}
            </div>
            <div className="flex shrink-0 gap-2">
              <Button variant="secondary" size="sm" icon={Pencil} onClick={() => onEdit(item)} aria-label={t('medical.editLabel', { title })}>
                {t('common.edit')}
              </Button>
              <Button variant="ghost" size="sm" icon={Trash2} onClick={() => onDelete(item)} aria-label={t('medical.deleteLabel', { title })}>
                {t('common.delete')}
              </Button>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
