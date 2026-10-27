import { useEffect, useRef, useState } from 'react'
import { Download, FileText, RefreshCw } from 'lucide-react'
import { useAuth } from '../auth/auth-context.js'
import Alert from '../components/ui/Alert.jsx'
import Button from '../components/ui/Button.jsx'
import Card from '../components/ui/Card.jsx'
import PageHeader from '../components/ui/PageHeader.jsx'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/States.jsx'
import DateRangeFilter from '../features/analytics/DateRangeFilter.jsx'
import ChoiceGroup from '../features/daily/components/ChoiceGroup.jsx'
import ReportPreview from '../features/reports/ReportPreview.jsx'
import { getMedicalReport, getMedicalReportPdf, saveFile } from '../features/reports/reportService.js'
import { useI18n } from '../i18n/i18n-context.js'

const sameOptions = (a, b) =>
  a.lang === b.lang && a.filters.period === b.filters.period && a.filters.start === b.filters.start && a.filters.end === b.filters.end

/**
 * Choose a period and a language, generate the report, preview every section,
 * then download the PDF of exactly the report on screen. Both come from the
 * backend, built from the signed-in user's own records.
 */
export default function MedicalReportPage() {
  const { t, lang: uiLang } = useI18n()
  const { authRequest } = useAuth()
  const [options, setOptions] = useState({ filters: { period: '3m' }, lang: uiLang })
  const [result, setResult] = useState({ status: 'idle', report: null, options: null, error: null })
  const [download, setDownload] = useState({ busy: false, error: null })
  const controller = useRef(null)

  useEffect(() => () => controller.current?.abort(), [])

  async function generate() {
    controller.current?.abort()
    const current = new AbortController()
    controller.current = current
    const requested = options
    setDownload({ busy: false, error: null })
    setResult((r) => ({ ...r, status: 'loading', error: null }))
    try {
      const report = await getMedicalReport(authRequest, requested, { signal: current.signal })
      setResult({ status: 'ready', report, options: requested, error: null })
    } catch (error) {
      if (current.signal.aborted) return
      setResult((r) => ({ ...r, status: 'error', error }))
    }
  }

  async function downloadPdf() {
    setDownload({ busy: true, error: null })
    try {
      saveFile(await getMedicalReportPdf(authRequest, result.options))
      setDownload({ busy: false, error: null })
    } catch (error) {
      setDownload({ busy: false, error: error?.key ?? 'errors.generic' })
    }
  }

  const report = result.report
  const changed = report && !sameOptions(options, result.options)
  const overview = report?.data.overview
  const nothingRecorded =
    report && overview.total_episodes === 0 && report.data.sleep.nights === 0 && report.data.factors.days === 0 && report.data.medication.doses === 0

  let body
  if (result.status === 'loading' && !report) body = <LoadingState label={t('report.generating')} />
  else if (result.status === 'error' && !report)
    body = <ErrorState title={t('report.loadError')} message={t(result.error?.key ?? 'errors.generic')} onRetry={generate} />
  else if (!report)
    body = (
      <EmptyState icon={FileText} title={t('report.idleTitle')}>
        {t('report.idleBody')}
      </EmptyState>
    )
  else
    body = (
      <div className={result.status === 'loading' ? 'opacity-60 transition-opacity' : undefined} aria-busy={result.status === 'loading'}>
        <div className="px-5 py-6 sm:px-8 sm:py-8">
          <ReportPreview report={report} />
        </div>
      </div>
    )

  return (
    <>
      <PageHeader title={t('report.title')} description={t('report.description')} />

      <Card className="mb-6 space-y-5 p-5 sm:p-6">
        <div className="space-y-2">
          <p className="text-sm font-semibold text-ink">{t('report.period')}</p>
          <DateRangeFilter value={options.filters} onChange={(filters) => setOptions((o) => ({ ...o, filters }))} />
        </div>
        <ChoiceGroup
          name="report-language"
          legend={t('report.language')}
          value={options.lang}
          onChange={(lang) => setOptions((o) => ({ ...o, lang }))}
          options={[
            { value: 'en', label: 'English' },
            { value: 'ar', label: 'العربية' },
          ]}
        />
        <div className="flex flex-wrap gap-3 border-t border-line pt-5">
          <Button icon={report ? RefreshCw : FileText} onClick={generate} loading={result.status === 'loading'} loadingText={t('report.generating')}>
            {report ? t('report.regenerate') : t('report.generate')}
          </Button>
          {report && (
            <Button variant="secondary" icon={Download} onClick={downloadPdf} loading={download.busy} loadingText={t('report.preparingPdf')}>
              {t('report.downloadPdf')}
            </Button>
          )}
        </div>
        {changed && <Alert tone="info">{t('report.optionsChanged')}</Alert>}
        {download.error && (
          <Alert tone="danger" title={t('report.pdfFailed')}>
            {t(download.error)}
          </Alert>
        )}
        {result.status === 'error' && report && (
          <Alert tone="danger" title={t('report.loadError')}>
            {t(result.error?.key ?? 'errors.generic')}
          </Alert>
        )}
        {report && <p className="text-sm text-ink-muted">{t('report.privacy')}</p>}
      </Card>

      {nothingRecorded && (
        <Alert tone="warning" className="mb-6" title={t('report.emptyTitle')}>
          {t('report.emptyBody')}
        </Alert>
      )}

      <Card aria-label={t('report.previewLabel')}>{body}</Card>
    </>
  )
}
