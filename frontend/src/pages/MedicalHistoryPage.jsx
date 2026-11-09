import { useState } from 'react'
import { Brain, HeartPulse, Plus, Scissors, ShieldAlert, Stethoscope } from 'lucide-react'
import { useAuth } from '../auth/auth-context.js'
import Alert from '../components/ui/Alert.jsx'
import Button from '../components/ui/Button.jsx'
import Card, { CardHeader } from '../components/ui/Card.jsx'
import ConfirmDialog from '../components/ui/ConfirmDialog.jsx'
import PageHeader from '../components/ui/PageHeader.jsx'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/States.jsx'
import HistoryList from '../features/medical/components/HistoryList.jsx'
import { AllergyForm, ConditionForm, ProcedureForm } from '../features/medical/components/MedicalForms.jsx'
import NotesCard from '../features/medical/components/NotesCard.jsx'
import { describeItem } from '../features/medical/describeItem.js'
import {
  allergyFormFrom,
  conditionFormFrom,
  emptyAllergyForm,
  emptyConditionForm,
  emptyProcedureForm,
  procedureFormFrom,
} from '../features/medical/medicalForms.js'
import { CARDS } from '../features/medical/medicalOptions.js'
import { createItem, deleteItem, saveNotes, updateItem } from '../features/medical/medicalService.js'
import { useMedicalHistory } from '../features/medical/useMedicalHistory.js'
import { useI18n } from '../i18n/i18n-context.js'

const ICONS = { chronic: HeartPulse, headache: Brain, associated: Stethoscope, allergies: ShieldAlert, procedures: Scissors }

function itemsFor(card, data) {
  if (card.kind === 'conditions') return data.conditions.filter((c) => card.categories.includes(c.category))
  return data[card.kind]
}

function FormFor({ card, item, onSubmit, onCancel, submitLabel }) {
  if (card.kind === 'conditions') {
    const initialForm = item ? conditionFormFrom(item) : emptyConditionForm(card.categories[0])
    return <ConditionForm categories={card.categories} initialForm={initialForm} onSubmit={onSubmit} onCancel={onCancel} submitLabel={submitLabel} />
  }
  if (card.kind === 'allergies') {
    const initialForm = item ? allergyFormFrom(item) : emptyAllergyForm()
    return <AllergyForm initialForm={initialForm} onSubmit={onSubmit} onCancel={onCancel} submitLabel={submitLabel} />
  }
  const initialForm = item ? procedureFormFrom(item) : emptyProcedureForm()
  return <ProcedureForm initialForm={initialForm} onSubmit={onSubmit} onCancel={onCancel} submitLabel={submitLabel} />
}

/**
 * Medical history the user reports: long-term and serious past conditions,
 * headache disorders, other conditions, allergies, procedures and notes. It is
 * context for a clinician, shown in the medical report; Namat's analysis
 * never uses it.
 */
export default function MedicalHistoryPage() {
  const { t, locale } = useI18n()
  const { authRequest } = useAuth()
  const history = useMedicalHistory()
  const [editing, setEditing] = useState(null) // { cardId, item } (item null = new)
  const [flash, setFlash] = useState(null) // { cardId, key }
  const [deleting, setDeleting] = useState(null) // { card, item, busy, error }

  function startEditing(cardId, item = null) {
    setFlash(null)
    setEditing({ cardId, item })
  }

  async function save(card, payload) {
    if (editing.item) await updateItem(authRequest, card.kind, editing.item.id, payload)
    else await createItem(authRequest, card.kind, payload)
    setFlash({ cardId: card.id, key: editing.item ? 'medical.updated' : 'medical.saved' })
    setEditing(null)
    history.reload()
  }

  async function confirmDelete() {
    setDeleting((d) => ({ ...d, busy: true, error: null }))
    try {
      await deleteItem(authRequest, deleting.card.kind, deleting.item.id)
      setFlash({ cardId: deleting.card.id, key: 'medical.deleted' })
      setDeleting(null)
      history.reload()
    } catch (error) {
      setDeleting((d) => ({ ...d, busy: false, error: error?.key ?? 'errors.generic' }))
    }
  }

  let body
  if (history.status === 'loading') body = <LoadingState label={t('medical.loading')} />
  else if (history.status === 'error')
    body = (
      <Card>
        <ErrorState title={t('medical.loadError')} message={t(history.error?.key ?? 'errors.generic')} onRetry={history.retry} />
      </Card>
    )
  else
    body = (
      <div className="space-y-6">
        {CARDS.filter((card) => card.kind !== 'notes').map((card) => {
          const items = itemsFor(card, history.data)
          const editingHere = editing?.cardId === card.id
          const headingId = `medical-${card.id}-heading`
          const addButton = (
            <Button size="sm" variant="secondary" icon={Plus} onClick={() => startEditing(card.id)}>
              {t(`medical.cards.${card.id}.add`)}
            </Button>
          )
          return (
            <Card key={card.id} aria-labelledby={headingId}>
              <CardHeader
                id={headingId}
                title={t(`medical.cards.${card.id}.title`)}
                description={t(`medical.cards.${card.id}.description`)}
                action={!editingHere && items.length > 0 ? addButton : null}
              />
              <div className="mt-4">
                {flash?.cardId === card.id && (
                  <div className="px-5 pb-4 sm:px-6">
                    <Alert tone="success">{t(flash.key)}</Alert>
                  </div>
                )}
                {editingHere && (
                  <div className="border-t border-line px-5 pt-5 pb-6 sm:px-6">
                    <h3 className="mb-4 font-semibold text-ink">{t(`medical.${editing.item ? 'editTitle' : 'newTitle'}`)}</h3>
                    <FormFor
                      key={editing.item?.id ?? 'new'}
                      card={card}
                      item={editing.item}
                      onSubmit={(payload) => save(card, payload)}
                      onCancel={() => setEditing(null)}
                      submitLabel={t(editing.item ? 'medical.saveChanges' : 'medical.save')}
                    />
                  </div>
                )}
                {items.length > 0 ? (
                  <div className="border-t border-line">
                    <HistoryList
                      kind={card.kind}
                      items={items}
                      onEdit={(item) => startEditing(card.id, item)}
                      onDelete={(item) => setDeleting({ card, item, busy: false, error: null })}
                    />
                  </div>
                ) : (
                  !editingHere && (
                    <EmptyState icon={ICONS[card.id]} title={t(`medical.cards.${card.id}.emptyTitle`)} action={addButton} className="py-8">
                      {t(`medical.cards.${card.id}.emptyBody`)}
                    </EmptyState>
                  )
                )}
              </div>
            </Card>
          )
        })}
        <NotesCard initialNotes={history.data.notes.notes} onSave={(notes) => saveNotes(authRequest, notes)} />
      </div>
    )

  return (
    <>
      <PageHeader title={t('medical.title')} description={t('medical.description')} />
      <Alert tone="info" className="mb-6">
        {t('medical.privacy')}
      </Alert>
      {body}

      <ConfirmDialog
        open={Boolean(deleting)}
        title={t('medical.deleteTitle')}
        confirmLabel={t('common.delete')}
        cancelLabel={t('common.cancel')}
        busy={deleting?.busy}
        busyLabel={t('medical.deleting')}
        onConfirm={confirmDelete}
        onCancel={() => setDeleting(null)}
      >
        {deleting && t('medical.deleteBody', { title: describeItem(deleting.card.kind, deleting.item, t, locale).title })}
        {deleting?.error && <span className="mt-2 block font-medium text-danger">{t(deleting.error)}</span>}
      </ConfirmDialog>
    </>
  )
}
