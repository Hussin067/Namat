import { useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router'
import { ArrowLeft, History, Pencil, Trash2 } from 'lucide-react'
import { useAuth } from '../auth/auth-context.js'
import Alert from '../components/ui/Alert.jsx'
import Button, { ButtonLink } from '../components/ui/Button.jsx'
import Card, { CardHeader } from '../components/ui/Card.jsx'
import ConfirmDialog from '../components/ui/ConfirmDialog.jsx'
import PageHeader from '../components/ui/PageHeader.jsx'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/States.jsx'
import IntensityBadge from '../features/episodes/components/IntensityBadge.jsx'
import { DOSE_UNITS } from '../features/episodes/constants.js'
import { deleteEpisode } from '../features/episodes/episodeService.js'
import { durationMinutes, formatDate, formatDateTime, formatDuration } from '../features/episodes/format.js'
import { useEpisode } from '../features/episodes/useEpisode.js'
import { useI18n } from '../i18n/i18n-context.js'

function Row({ label, children }) {
  return (
    <div className="grid gap-1 px-5 py-3.5 sm:grid-cols-[11rem_1fr] sm:gap-6 sm:px-6">
      <dt className="text-sm font-medium text-ink-muted">{label}</dt>
      <dd className="min-w-0 text-ink">{children}</dd>
    </div>
  )
}

function BackLink() {
  const { t } = useI18n()
  return (
    <Link
      to="/history"
      className="mb-6 inline-flex min-h-9 items-center gap-1.5 text-sm font-semibold text-brand underline-offset-4 hover:underline"
    >
      <ArrowLeft aria-hidden="true" className="size-4 rtl:-scale-x-100" />
      {t('episodeDetail.backToHistory')}
    </Link>
  )
}

export default function EpisodeDetailPage() {
  const { episodeId } = useParams()
  const { t, locale } = useI18n()
  const { authRequest } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const { status, episode, error, reload } = useEpisode(episodeId)
  const [confirming, setConfirming] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState(null)

  async function handleDelete() {
    setDeleting(true)
    setDeleteError(null)
    try {
      await deleteEpisode(authRequest, episodeId)
      navigate('/history', { replace: true, state: { flash: 'history.deleted' } })
    } catch (err) {
      setDeleting(false)
      setConfirming(false)
      setDeleteError(err.key ?? 'errors.generic')
    }
  }

  if (status === 'loading') {
    return (
      <>
        <BackLink />
        <LoadingState label={t('episodeDetail.loading')} />
      </>
    )
  }
  if (status === 'error') {
    return (
      <>
        <BackLink />
        <Card>
          {error?.status === 404 ? (
            <EmptyState
              icon={History}
              title={t('episodeDetail.notFoundTitle')}
              action={<ButtonLink to="/history">{t('episodeDetail.backToHistory')}</ButtonLink>}
            >
              {t('episodeDetail.notFoundBody')}
            </EmptyState>
          ) : (
            <ErrorState message={t(error?.key ?? 'errors.generic')} onRetry={reload} />
          )}
        </Card>
      </>
    )
  }

  const notRecorded = <span className="text-ink-muted">{t('episodeDetail.notRecorded')}</span>
  const number = new Intl.NumberFormat(locale)
  const unitLabel = (unit) => (DOSE_UNITS.includes(unit) ? t(`units.${unit}`) : unit)
  const edited = new Date(episode.updated_at) - new Date(episode.created_at) > 1000

  return (
    <>
      <BackLink />
      <PageHeader
        title={formatDateTime(episode.started_at, locale)}
        description={t('episodeDetail.eyebrow')}
        actions={
          <>
            <ButtonLink to={`/episodes/${episode.id}/edit`} variant="secondary" icon={Pencil}>
              {t('episodeDetail.edit')}
            </ButtonLink>
            <Button variant="danger" icon={Trash2} onClick={() => setConfirming(true)}>
              {t('episodeDetail.delete')}
            </Button>
          </>
        }
      />

      {location.state?.flash && (
        <Alert tone="success" className="mb-6">
          {t(location.state.flash)}
        </Alert>
      )}
      {deleteError && (
        <Alert tone="danger" title={t('episodeDetail.deleteFailed')} className="mb-6">
          {t(deleteError)}
        </Alert>
      )}

      <div className="space-y-6">
        <Card aria-labelledby="overview-heading">
          <CardHeader id="overview-heading" title={t('episodeDetail.overview')} />
          <dl className="mt-4 divide-y divide-line border-t border-line">
            <Row label={t('episodeDetail.started')}>{formatDateTime(episode.started_at, locale)}</Row>
            <Row label={t('episodeDetail.ended')}>
              {episode.ended_at ? formatDateTime(episode.ended_at, locale) : t('episodeDetail.stillGoing')}
            </Row>
            <Row label={t('episodeDetail.duration')}>
              {formatDuration(durationMinutes(episode), locale) ?? t('episodeDetail.stillGoing')}
            </Row>
            <Row label={t('episodeDetail.intensity')}>
              <IntensityBadge value={episode.peak_intensity} />
            </Row>
            <Row label={t('episodeDetail.location')}>
              {episode.pain_location ? t(`locations.${episode.pain_location}`) : notRecorded}
            </Row>
            <Row label={t('episodeDetail.aura')}>{episode.had_aura ? t('episodeDetail.yes') : t('episodeDetail.no')}</Row>
          </dl>
        </Card>

        <Card aria-labelledby="symptoms-heading">
          <CardHeader id="symptoms-heading" title={t('episodeDetail.symptoms')} />
          <div className="px-5 pt-3 pb-6 sm:px-6">
            {episode.symptoms.length ? (
              <ul className="flex flex-wrap gap-2">
                {episode.symptoms.map((name) => (
                  <li key={name} className="rounded-full border border-line px-3 py-1 text-sm text-ink">
                    {t(`symptoms.${name}`)}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-ink-muted">{t('episodeDetail.noSymptoms')}</p>
            )}
          </div>
        </Card>

        <Card aria-labelledby="medication-heading">
          <CardHeader id="medication-heading" title={t('episodeDetail.medication')} />
          <div className="px-5 pt-3 pb-6 sm:px-6">
            {episode.medications.length ? (
              <ul className="divide-y divide-line">
                {episode.medications.map((dose) => (
                  <li key={dose.id} className="py-3 first:pt-0 last:pb-0">
                    <p className="font-semibold text-ink">
                      {dose.medication_name}
                      {dose.dose_amount != null && (
                        <span className="ms-2 font-normal text-ink-muted">
                          {number.format(dose.dose_amount)} {dose.dose_unit && unitLabel(dose.dose_unit)}
                        </span>
                      )}
                    </p>
                    <p className="text-sm text-ink-muted">
                      {t('episodeDetail.taken', { time: formatDateTime(dose.taken_at, locale) })}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-ink-muted">{t('episodeDetail.noMedication')}</p>
            )}
          </div>
        </Card>

        <Card aria-labelledby="notes-heading">
          <CardHeader id="notes-heading" title={t('episodeDetail.notes')} />
          <div className="px-5 pt-3 pb-6 sm:px-6">
            {episode.notes ? (
              <p className="whitespace-pre-line text-ink">{episode.notes}</p>
            ) : (
              <p className="text-ink-muted">{t('episodeDetail.noNotes')}</p>
            )}
          </div>
        </Card>

        <p className="text-sm text-ink-muted">
          {t('episodeDetail.logged', { date: formatDate(episode.created_at, locale) })}
          {edited && <> · {t('episodeDetail.edited', { date: formatDateTime(episode.updated_at, locale) })}</>}
        </p>
      </div>

      <ConfirmDialog
        open={confirming}
        title={t('episodeDetail.deleteTitle')}
        confirmLabel={t('episodeDetail.deleteConfirm')}
        cancelLabel={t('episodeDetail.cancel')}
        busy={deleting}
        busyLabel={t('episodeDetail.deleting')}
        onConfirm={handleDelete}
        onCancel={() => setConfirming(false)}
      >
        {t('episodeDetail.deleteBody')}
      </ConfirmDialog>
    </>
  )
}
