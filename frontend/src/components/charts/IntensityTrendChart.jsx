import { Line } from 'react-chartjs-2'
import './chartSetup.js'
import { formatBucket } from '../../features/analytics/format.js'
import { intensityInfo } from '../../features/episodes/constants.js'
import { useI18n } from '../../i18n/i18n-context.js'
import ChartCard, { ChartTable } from './ChartCard.jsx'
import { useChartTheme } from './useChartTheme.js'

/**
 * Average peak intensity (0–10) per bucket. Buckets without a rated episode
 * stay empty (a gap in the line), never a made-up value or a zero.
 */
export default function IntensityTrendChart({ points, interval }) {
  const { t, locale } = useI18n()
  const chart = useChartTheme()
  const rated = points.filter((p) => p.average_intensity != null)
  const unit = t(`dashboard.charts.per.${interval}`)

  const data = {
    labels: points.map((p) => formatBucket(p.date, interval, locale)),
    datasets: [
      {
        label: t('dashboard.charts.averageIntensity'),
        data: points.map((p) => p.average_intensity),
        borderColor: chart.colors.series[1],
        backgroundColor: chart.colors.series[1],
        spanGaps: false,
        cubicInterpolationMode: 'monotone',
        borderWidth: 2,
        pointRadius: 3,
        pointHoverRadius: 5,
      },
    ],
  }

  const options = {
    ...chart.base,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      ...chart.base.plugins,
      legend: { display: false },
      tooltip: {
        ...chart.base.plugins.tooltip,
        filter: (item) => item.parsed.y != null,
        callbacks: {
          title: (items) => formatBucket(points[items[0].dataIndex].date, interval, locale, 'long'),
          label: (item) => {
            const point = points[item.dataIndex]
            return t('dashboard.charts.intensityTooltip', {
              value: point.average_intensity,
              label: t(intensityInfo(Math.round(point.average_intensity)).key),
              count: point.rated_episodes,
            })
          },
        },
      },
    },
    scales: {
      x: chart.axis({ grid: { display: false }, ticks: { ...chart.axis().ticks, maxTicksLimit: 8, maxRotation: 0 } }),
      y: chart.axis({
        min: 0,
        max: 10,
        ticks: { ...chart.axis().ticks, stepSize: 2 },
        title: { display: true, text: t('dashboard.charts.intensityAxis'), color: chart.colors.muted, font: chart.font },
      }),
    },
  }

  return (
    <ChartCard
      title={t('dashboard.charts.intensityTitle')}
      caption={t('dashboard.charts.intensityCaption', { unit })}
      empty={rated.length === 0}
      emptyMessage={t('dashboard.charts.noRatings')}
      table={
        <ChartTable
          caption={t('dashboard.charts.intensityTitle')}
          headers={[t('dashboard.charts.period'), t('dashboard.charts.averageIntensity')]}
          rows={rated.map((p) => [
            formatBucket(p.date, interval, locale, 'long'),
            t('dashboard.charts.intensityValue', { value: p.average_intensity }),
          ])}
        />
      }
    >
      <Line data={data} options={options} />
    </ChartCard>
  )
}
