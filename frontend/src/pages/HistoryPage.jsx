import { useLocation } from 'react-router'
import { CirclePlus, History } from 'lucide-react'
import Alert from '../components/ui/Alert.jsx'
import Button, { ButtonLink } from '../components/ui/Button.jsx'
import Card from '../components/ui/Card.jsx'
import PageHeader from '../components/ui/PageHeader.jsx'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/States.jsx'
import DataSourceNotice from '../features/episodes/components/DataSourceNotice.jsx'
import EpisodeList from '../features/episodes/components/EpisodeList.jsx'
import { useEpisodes } from '../features/episodes/useEpisodes.js'
import { useI18n } from '../i18n/i18n-context.js'

export default function HistoryPage() {
  const { t } = useI18n()
  const { status, episodes, total, error, reload, hasMore, loadMore, more } = useEpisodes()
  const location = useLocation()

  const logAction = (
    <ButtonLink to="/log" icon={CirclePlus}>
      {t('nav.log')}
    </ButtonLink>
  )

  let body
  if (status === 'loading') body = <LoadingState label={t('history.loading')} />
  else if (status === 'error') body = <ErrorState message={t(error?.key ?? 'errors.generic')} onRetry={reload} />
  else if (episodes.length === 0) {
    body = (
      <EmptyState icon={History} title={t('history.emptyTitle')} action={logAction}>
        {t('history.emptyBody')}
      </EmptyState>
    )
  } else {
    body = (
      <>
        <p className="border-b border-line px-5 py-3 text-sm text-ink-muted sm:px-6">
          {t('history.count', { count: total })}
        </p>
        <EpisodeList episodes={episodes} />
        {hasMore && (
          <div className="space-y-2 border-t border-line px-5 py-4 sm:px-6">
            <Button variant="secondary" size="sm" onClick={loadMore} loading={more.loading} loadingText={t('common.loading')}>
              {t('history.loadMore')}
            </Button>
            {more.error && <p className="text-sm text-danger" role="alert">{t(more.error.key ?? 'errors.generic')}</p>}
          </div>
        )}
      </>
    )
  }

  return (
    <>
      <PageHeader
        title={t('history.title')}
        description={t('history.description')}
        actions={status === 'ready' && episodes.length === 0 ? null : logAction}
      />
      {location.state?.flash && (
        <Alert tone="success" className="mb-6">
          {t(location.state.flash)}
        </Alert>
      )}
      <DataSourceNotice />
      <Card aria-label={t('history.listLabel')}>{body}</Card>
    </>
  )
}
