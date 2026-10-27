import { Line } from 'react-chartjs-2'
import './chartSetup.js'
import { formatBucket } from '../../features/analytics/format.js'
import { useI18n } from '../../i18n/i18n-context.js'
import ChartCard, { ChartTable } from './ChartCard.jsx'
import { useChartTheme, withAlpha } from './useChartTheme.js'

/** Episodes per day / week / month. Empty buckets are real zeros from the API. */
export default function HeadacheFrequencyChart({ points, interval }) {
  const { t, locale } = useI18n()
  const chart = useChartTheme()
  const total = points.reduce((sum, p) => sum + p.count, 0)
  const unit = t(`dashboard.charts.per.${interval}`)

  const data = {
    labels: points.map((p) => formatBucket(p.date, interval, locale)),
    datasets: [
      {
        label: t('dashboard.charts.episodes'),
        data: points.map((p) => p.count),
        borderColor: chart.colors.brand,
        backgroundColor: withAlpha(chart.colors.brand, 0.12),
        fill: true,
        cubicInterpolationMode: 'monotone', // smooth, but never overshoots the real counts
        borderWidth: 2,
        pointRadius: points.length > 40 ? 0 : 2.5,
        pointHoverRadius: 5,
        pointBackgroundColor: chart.colors.brand,
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
        callbacks: {
          title: (items) => formatBucket(points[items[0].dataIndex].date, interval, locale, 'long'),
          label: (item) => t('dashboard.charts.episodeCount', { count: item.parsed.y }),
        },
      },
    },
    scales: {
      x: chart.axis({ grid: { display: false }, ticks: { ...chart.axis().ticks, maxTicksLimit: 8, maxRotation: 0 } }),
      y: chart.axis({ beginAtZero: true, suggestedMax: 2, ticks: { ...chart.axis().ticks, precision: 0 } }),
    },
  }

  return (
    <ChartCard
      title={t('dashboard.charts.frequencyTitle')}
      caption={t('dashboard.charts.frequencyCaption', { count: total, unit })}
      table={
        <ChartTable
          caption={t('dashboard.charts.frequencyTitle')}
          headers={[t('dashboard.charts.period'), t('dashboard.charts.episodes')]}
          rows={points.map((p) => [formatBucket(p.date, interval, locale, 'long'), p.count])}
        />
      }
    >
      <Line data={data} options={options} />
    </ChartCard>
  )
}
