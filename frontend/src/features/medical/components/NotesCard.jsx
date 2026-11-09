import { useState } from 'react'
import { Save } from 'lucide-react'
import Alert from '../../../components/ui/Alert.jsx'
import Button from '../../../components/ui/Button.jsx'
import Card, { CardHeader } from '../../../components/ui/Card.jsx'
import Field, { Textarea } from '../../../components/ui/Field.jsx'
import { useI18n } from '../../../i18n/i18n-context.js'
import { validateNotes } from '../medicalForms.js'
import { ADDITIONAL_NOTES_MAX } from '../medicalOptions.js'

/** Additional notes: one free-text field. Saving an empty text removes the notes. */
export default function NotesCard({ initialNotes, onSave }) {
  const { t } = useI18n()
  const [text, setText] = useState(initialNotes ?? '')
  const [saved, setSaved] = useState(initialNotes ?? '')
  const [error, setError] = useState(null)
  const [failure, setFailure] = useState(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)

  async function submit(event) {
    event.preventDefault()
    const problem = validateNotes(text)
    setError(problem)
    setFailure(null)
    setDone(false)
    if (problem) return
    setBusy(true)
    try {
      const result = await onSave(text.trim() || null)
      const stored = result?.notes ?? ''
      setText(stored)
      setSaved(stored)
      setDone(true)
    } catch (err) {
      setFailure(err?.key ?? 'errors.generic')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card aria-labelledby="medical-notes-heading">
      <CardHeader id="medical-notes-heading" title={t('medical.cards.notes.title')} description={t('medical.cards.notes.description')} />
      <form onSubmit={submit} noValidate className="space-y-4 px-5 pt-4 pb-6 sm:px-6">
        {failure && (
          <Alert tone="danger" title={t('medical.saveFailed')}>
            {t(failure)}
          </Alert>
        )}
        {done && <Alert tone="success">{t('medical.notesSaved')}</Alert>}
        <Field id="medical-notes" label={t('medical.fields.additionalNotes')} error={error && t(error)} optional>
          <Textarea
            id="medical-notes"
            dir="auto"
            maxLength={ADDITIONAL_NOTES_MAX}
            value={text}
            placeholder={t('medical.cards.notes.placeholder')}
            onChange={(e) => {
              setText(e.target.value)
              setDone(false)
            }}
            error={error && t(error)}
          />
        </Field>
        <Button type="submit" icon={Save} loading={busy} loadingText={t('medical.saving')} disabled={text === saved}>
          {t('medical.saveNotes')}
        </Button>
      </form>
    </Card>
  )
}
