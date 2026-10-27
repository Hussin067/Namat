import { useState } from 'react'
import { Link } from 'react-router'
import { useAuth } from '../auth/auth-context.js'
import Alert from '../components/ui/Alert.jsx'
import Button from '../components/ui/Button.jsx'
import PageHeader from '../components/ui/PageHeader.jsx'
import EpisodeForm from '../features/episodes/components/EpisodeForm.jsx'
import { useDemoMode } from '../features/episodes/demo-context.js'
import { emptyEpisodeForm } from '../features/episodes/episodeForm.js'
import { createEpisode } from '../features/episodes/episodeService.js'
import { useI18n } from '../i18n/i18n-context.js'

export default function LogEpisodePage() {
  const { t } = useI18n()
  const { authRequest } = useAuth()
  const demo = useDemoMode()
  // Changing the key mounts a fresh, empty form.
  const [formKey, setFormKey] = useState(0)
  // Stored as message keys plus a link, so it follows a language switch.
  const [result, setResult] = useState(null) // { tone, title, body, link: { to, label } }

  async function handleSubmit(payload, form) {
    setResult(null)
    if (demo.enabled) {
      // Demo records keep symptom names, like the fixtures; never sent to the server.
      demo.addEpisode({ ...payload, symptoms: form.symptoms })
      setResult({
        tone: 'warning',
        title: 'log.result.demoTitle',
        body: 'log.result.demoBody',
        link: { to: '/history', label: 'log.viewHistory' },
      })
    } else {
      const saved = await createEpisode(authRequest, payload) // throws if not saved
      setResult({
        tone: 'success',
        title: 'log.result.savedTitle',
        body: 'log.result.savedBody',
        link: { to: `/episodes/${saved.id}`, label: 'log.viewEpisode' },
      })
    }
    setFormKey((k) => k + 1)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <>
      <PageHeader title={t('log.title')} description={t('log.description')} />

      {result && (
        <Alert
          tone={result.tone}
          title={t(result.title)}
          className="mb-6"
          action={
            <Link to={result.link.to} className="font-semibold underline underline-offset-4">
              {t(result.link.label)}
            </Link>
          }
        >
          {t(result.body)}
        </Alert>
      )}

      <EpisodeForm
        key={formKey}
        initialForm={emptyEpisodeForm()}
        onSubmit={handleSubmit}
        submitLabel={demo.enabled ? t('log.addDemo') : t('log.save')}
        submittingLabel={t('log.saving')}
        secondaryAction={
          <Button
            variant="ghost"
            onClick={() => {
              setFormKey((k) => k + 1)
              setResult(null)
            }}
          >
            {t('log.clear')}
          </Button>
        }
      />
    </>
  )
}
