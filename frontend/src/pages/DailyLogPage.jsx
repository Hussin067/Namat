import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { ListChecks, Moon, Plus } from 'lucide-react'
import { useAuth } from '../auth/auth-context.js'
import Alert from '../components/ui/Alert.jsx'
import Button from '../components/ui/Button.jsx'
import Card, { CardHeader } from '../components/ui/Card.jsx'
import ConfirmDialog from '../components/ui/ConfirmDialog.jsx'
import PageHeader from '../components/ui/PageHeader.jsx'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/States.jsx'
import { cx } from '../components/ui/styles.js'
import EntryList from '../features/daily/components/EntryList.jsx'
import { describeEntry } from '../features/daily/describeEntry.js'
import FactorForm from '../features/daily/components/FactorForm.jsx'
import SleepForm from '../features/daily/components/SleepForm.jsx'
import { emptyFactorForm, emptySleepForm, factorFormFrom, sleepFormFrom } from '../features/daily/dailyForms.js'
import { createEntry, deleteEntry, updateEntry } from '../features/daily/dailyService.js'
import { useDailyEntries } from '../features/daily/useDailyEntries.js'
import { useI18n } from '../i18n/i18n-context.js'

const TABS = [
  { kind: 'sleep', icon: Moon },
  { kind: 'factors', icon: ListChecks },
]

/**
 * Sleep logs and daily factors: the records the insights and the medical
 * report compare with headache days. One tab per record type (kept in the
 * URL as ?tab=), a list with edit and delete, and an add/edit form.
 */
export default function DailyLogPage() {
  const { t, locale } = useI18n()
  const { authRequest } = useAuth()
  const [params, setParams] = useSearchParams()
  const kind = params.get('tab') === 'factors' ? 'factors' : 'sleep'
  const entries = useDailyEntries(kind)
  const [editing, setEditing] = useState(null) // { entry } (entry null = new)
  const [flash, setFlash] = useState(null) // message key
  const [deleting, setDeleting] = useState(null) // { entry, busy, error }

  function switchTab(next) {
    setEditing(null)
    setFlash(null)
    setParams(next === 'sleep' ? {} : { tab: next }, { replace: true })
  }

  async function save(payload) {
    if (editing.entry) await updateEntry(authRequest, kind, editing.entry.id, payload)
    else await createEntry(authRequest, kind, payload)
    setFlash(editing.entry ? 'daily.updated' : 'daily.saved')
    setEditing(null)
    entries.reload()
  }

  async function confirmDelete() {
    setDeleting((d) => ({ ...d, busy: true, error: null }))
    try {
      await deleteEntry(authRequest, kind, deleting.entry.id)
      setDeleting(null)
      setFlash('daily.deleted')
      entries.reload()
    } catch (error) {
      setDeleting((d) => ({ ...d, busy: false, error: error?.key ?? 'errors.generic' }))
    }
  }

  const startNew = () => {
    setFlash(null)
    setEditing({ entry: null })
  }
  const addButton = (
    <Button icon={Plus} onClick={startNew}>
      {t(`daily.${kind}.add`)}
    </Button>
  )

  let body
  if (entries.status === 'loading') body = <LoadingState />
  else if (entries.status === 'error')
    body = <ErrorState message={t(entries.error?.key ?? 'errors.generic')} onRetry={entries.reload} />
  else if (entries.items.length === 0)
    body = (
      <EmptyState icon={kind === 'sleep' ? Moon : ListChecks} title={t(`daily.${kind}.emptyTitle`)} action={addButton}>
        {t(`daily.${kind}.emptyBody`)}
      </EmptyState>
    )
  else
    body = (
      <>
        <p className="border-b border-line px-5 py-3 text-sm text-ink-muted sm:px-6">
          {t(`daily.${kind}.count`, { count: entries.total })}
        </p>
        <EntryList
          kind={kind}
          items={entries.items}
          onEdit={(entry) => {
            setFlash(null)
            setEditing({ entry })
          }}
          onDelete={(entry) => setDeleting({ entry, busy: false, error: null })}
        />
        {entries.hasMore && (
          <div className="border-t border-line px-5 py-4 sm:px-6">
            <Button variant="secondary" size="sm" onClick={entries.loadMore}>
              {t('daily.loadMore')}
            </Button>
          </div>
        )}
      </>
    )

  const Form = kind === 'sleep' ? SleepForm : FactorForm
  const initialForm = editing?.entry
    ? (kind === 'sleep' ? sleepFormFrom : factorFormFrom)(editing.entry)
    : (kind === 'sleep' ? emptySleepForm : emptyFactorForm)()

  return (
    <>
      <PageHeader title={t('daily.title')} description={t('daily.description')} />

      <div role="tablist" aria-label={t('daily.tabsLabel')} className="mb-6 inline-flex max-w-full rounded-xl border border-line bg-sunken p-1">
        {TABS.map(({ kind: tab, icon: Icon }) => (
          <button
            key={tab}
            type="button"
            role="tab"
            id={`tab-${tab}`}
            aria-selected={kind === tab}
            aria-controls="daily-panel"
            onClick={() => switchTab(tab)}
            className={cx(
              'inline-flex min-h-10 items-center gap-2 rounded-lg px-4 text-sm font-semibold transition-colors',
              kind === tab ? 'bg-surface text-ink shadow-card' : 'text-ink-muted hover:text-ink',
            )}
          >
            <Icon aria-hidden="true" className="size-4" />
            {t(`daily.${tab}.tab`)}
          </button>
        ))}
      </div>

      <div id="daily-panel" role="tabpanel" aria-labelledby={`tab-${kind}`} className="space-y-6">
        {flash && <Alert tone="success">{t(flash)}</Alert>}

        {editing ? (
          <Card>
            <CardHeader title={t(`daily.${kind}.${editing.entry ? 'editTitle' : 'newTitle'}`)} />
            <div className="px-5 pt-5 pb-6 sm:px-6">
              <Form
                key={`${kind}-${editing.entry?.id ?? 'new'}`}
                initialForm={initialForm}
                onSubmit={save}
                onCancel={() => setEditing(null)}
                submitLabel={t(editing.entry ? 'daily.saveChanges' : 'daily.save')}
              />
            </div>
          </Card>
        ) : (
          entries.status === 'ready' && entries.items.length > 0 && <div>{addButton}</div>
        )}

        <Card aria-label={t(`daily.${kind}.listLabel`)}>{body}</Card>
      </div>

      <ConfirmDialog
        open={Boolean(deleting)}
        title={t('daily.deleteTitle')}
        confirmLabel={t('common.delete')}
        cancelLabel={t('common.cancel')}
        busy={deleting?.busy}
        busyLabel={t('daily.deleting')}
        onConfirm={confirmDelete}
        onCancel={() => setDeleting(null)}
      >
        {deleting && t('daily.deleteBody', { title: describeEntry(kind, deleting.entry, t, locale).title })}
        {deleting?.error && <span className="mt-2 block font-medium text-danger">{t(deleting.error)}</span>}
      </ConfirmDialog>
    </>
  )
}
