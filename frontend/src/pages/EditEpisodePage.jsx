import { useNavigate, useParams } from 'react-router'
import { useAuth } from '../auth/auth-context.js'
import { ButtonLink } from '../components/ui/Button.jsx'
import PageHeader from '../components/ui/PageHeader.jsx'
import { ErrorState, LoadingState } from '../components/ui/States.jsx'
import EpisodeForm from '../features/episodes/components/EpisodeForm.jsx'
import { episodeToForm } from '../features/episodes/episodeForm.js'
import { updateEpisode } from '../features/episodes/episodeService.js'
import { useEpisode } from '../features/episodes/useEpisode.js'
import { useI18n } from '../i18n/i18n-context.js'

export default function EditEpisodePage() {
  const { episodeId } = useParams()
  const { t } = useI18n()
  const { authRequest } = useAuth()
  const navigate = useNavigate()
  const { status, episode, error, reload } = useEpisode(episodeId)

  async function handleSubmit(payload) {
    await updateEpisode(authRequest, episodeId, payload) // throws if not saved
    navigate(`/episodes/${episodeId}`, { state: { flash: 'episodeDetail.updated' } })
  }

  let body
  if (status === 'loading') body = <LoadingState label={t('episodeDetail.loading')} />
  else if (status === 'error') {
    body = (
      <ErrorState
        title={error?.status === 404 ? t('episodeDetail.notFoundTitle') : undefined}
        message={t(error?.status === 404 ? 'episodeDetail.notFoundBody' : (error?.key ?? 'errors.generic'))}
        onRetry={error?.status === 404 ? undefined : reload}
      />
    )
  } else {
    body = (
      <EpisodeForm
        initialForm={episodeToForm(episode)}
        onSubmit={handleSubmit}
        submitLabel={t('editEpisode.save')}
        submittingLabel={t('editEpisode.saving')}
        secondaryAction={
          <ButtonLink to={`/episodes/${episodeId}`} variant="ghost">
            {t('editEpisode.cancel')}
          </ButtonLink>
        }
      />
    )
  }

  return (
    <>
      <PageHeader title={t('editEpisode.title')} description={t('editEpisode.description')} />
      {body}
    </>
  )
}
