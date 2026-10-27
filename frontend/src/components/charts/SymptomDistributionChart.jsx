import { Doughnut } from 'react-chartjs-2'
import './chartSetup.js'
import { useI18n } from '../../i18n/i18n-context.js'
import ChartCard, { ChartTable } from './ChartCard.jsx'
import { useChartTheme } from './useChartTheme.js'

// With more than TOP_SYMPTOMS + 1 symptoms, the least frequent ones are merged
// into one "Other symptoms" slice so the chart stays readable. The data table
// for screen readers always lists every symptom separately.
const TOP_SYMPTOMS = 5

export default function SymptomDistributionChart({ symptoms }) {
  const { t } = useI18n()
  const chart = useChartTheme()
  const name = (s) => t(`symptoms.${s.name}`)

  const grouped =
    symptoms.length > TOP_SYMPTOMS + 1
      ? [
          ...symptoms.slice(0, TOP_SYMPTOMS),
          {
            id: 'other',
            other: true,
            count: symptoms.slice(TOP_SYMPTOMS).reduce((sum, s) => sum + s.count, 0),
            kinds: symptoms.length - TOP_SYMPTOMS,
          },
        ]
      : symptoms
  const label = (s) => (s.other ? t('dashboard.charts.otherSymptoms', { count: s.kinds }) : name(s))

  const data = {
    labels: grouped.map(label),
    datasets: [
      {
        data: grouped.map((s) => s.count),
        backgroundColor: grouped.map((s, i) => (s.other ? chart.colors.series[6] : chart.colors.series[i % 6])),
        borderColor: chart.colors.surface,
        borderWidth: 2,
        hoverOffset: 6,
      },
    ],
  }

  const options = {
    ...chart.base,
    cutout: '62%',
    plugins: {
      ...chart.base.plugins,
      legend: { ...chart.base.plugins.legend, position: 'bottom' },
      tooltip: {
        ...chart.base.plugins.tooltip,
        callbacks: {
          label: (item) => ` ${item.label}: ${t('dashboard.charts.episodeCount', { count: item.parsed })}`,
        },
      },
    },
  }

  return (
    <ChartCard
      title={t('dashboard.charts.symptomsTitle')}
      caption={t('dashboard.charts.symptomsCaption')}
      empty={symptoms.length === 0}
      emptyMessage={t('dashboard.charts.noSymptoms')}
      table={
        <ChartTable
          caption={t('dashboard.charts.symptomsTitle')}
          headers={[t('dashboard.charts.symptom'), t('dashboard.charts.episodes')]}
          rows={symptoms.map((s) => [name(s), s.count])}
        />
      }
    >
      <Doughnut data={data} options={options} />
    </ChartCard>
  )
}
