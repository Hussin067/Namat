import Badge from '../../../components/ui/Badge.jsx'
import { useI18n } from '../../../i18n/i18n-context.js'
import { intensityInfo } from '../constants.js'

/** "6/10 · Moderate": number and word, so meaning never depends on colour. */
export default function IntensityBadge({ value }) {
  const { t } = useI18n()
  const { key, tone } = intensityInfo(value)
  return (
    <Badge tone={tone}>
      {value != null && (
        <span dir="ltr" className="tabular-nums">
          {t('intensity.badge', { value })}
        </span>
      )}
      {value != null && <span aria-hidden="true">·</span>}
      {t(key)}
    </Badge>
  )
}
