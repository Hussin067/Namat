import { Pencil, Trash2 } from 'lucide-react'
import Button from '../../../components/ui/Button.jsx'
import { useI18n } from '../../../i18n/i18n-context.js'
import { describeEntry } from '../describeEntry.js'

export default function EntryList({ kind, items, onEdit, onDelete }) {
  const { t, locale } = useI18n()
  return (
    <ul className="divide-y divide-line">
      {items.map((entry) => {
        const { title, parts } = describeEntry(kind, entry, t, locale)
        return (
          <li key={entry.id} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <div className="min-w-0">
              <p className="font-semibold text-ink">{title}</p>
              <p className="mt-0.5 text-sm text-ink-muted">{parts.join(' · ')}</p>
              {entry.notes && <p className="mt-1 line-clamp-2 text-sm break-words text-ink-muted" dir="auto">{entry.notes}</p>}
            </div>
            <div className="flex shrink-0 gap-2">
              <Button variant="secondary" size="sm" icon={Pencil} onClick={() => onEdit(entry)} aria-label={t('daily.editLabel', { title })}>
                {t('common.edit')}
              </Button>
              <Button variant="ghost" size="sm" icon={Trash2} onClick={() => onDelete(entry)} aria-label={t('daily.deleteLabel', { title })}>
                {t('common.delete')}
              </Button>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
