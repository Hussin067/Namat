// Chart.js is tree-shakeable: register only what Namat's charts use.
import {
  ArcElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from 'chart.js'

ChartJS.register(
  CategoryScale, // date labels on the x axis
  LinearScale, // counts and the 0–10 intensity axis
  PointElement,
  LineElement, // frequency and intensity lines
  Filler, // soft area under the frequency line
  ArcElement, // symptom doughnut
  Tooltip,
  Legend,
)
