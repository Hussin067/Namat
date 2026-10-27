import { FlaskConical, Info } from 'lucide-react'
import { useI18n } from '../../../i18n/i18n-context.js'
import { DEMO_MODE_SUPPORTED, useDemoMode } from '../demo-context.js'

/**
 * Says where the numbers come from (your saved records, or dev-only demo
 * fixtures) and holds the dev-only demo toggle. Hidden in production builds.
 */
export default function DataSourceNotice() {
  const { enabled, setEnabled } = useDemoMode()
  const { t } = useI18n()
  if (!DEMO_MODE_SUPPORTED) return null

  return (
    <div
      role="status"
      className={
        enabled
          ? 'mb-8 flex flex-col gap-3 rounded-xl border border-dashed border-warning/50 bg-warning-soft px-4 py-3 text-sm text-warning sm:flex-row sm:items-center sm:justify-between'
          : 'mb-8 flex flex-col gap-3 rounded-xl border border-line bg-surface px-4 py-3 text-sm text-ink-muted sm:flex-row sm:items-center sm:justify-between'
      }
    >
      <p className="flex items-start gap-2.5">
        {enabled ? (
          <>
            <FlaskConical aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <span>
              <strong className="font-semibold">{t('demo.bannerStrong')}</strong> {t('demo.bannerBody')}
            </span>
          </>
        ) : (
          <>
            <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <span>{t('demo.showingSaved')}</span>
          </>
        )}
      </p>
      {DEMO_MODE_SUPPORTED && (
        <label className="inline-flex min-h-9 shrink-0 cursor-pointer items-center gap-2.5 font-semibold">
          <input
            type="checkbox"
            role="switch"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
            className="size-4 accent-brand"
          />
          {t('demo.toggle')}
        </label>
      )}
    </div>
  )
}
