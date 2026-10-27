import { useId } from 'react'
import Card, { CardHeader } from '../ui/Card.jsx'
import { cx } from '../ui/styles.js'

/**
 * Frame shared by all charts: a heading, one sentence saying what the chart
 * shows, the chart (or an empty message) and a screen-reader data table.
 */
export default function ChartCard({ title, caption, empty, emptyMessage, table, children, className }) {
  const headingId = useId()
  return (
    // min-w-0: lets the grid column shrink, so Chart.js can resize the canvas
    // (without it, a canvas drawn at desktop width keeps the card too wide).
    <Card aria-labelledby={headingId} className={cx('min-w-0', className)}>
      <CardHeader id={headingId} title={title} description={caption} />
      <div className="px-5 pt-4 pb-6 sm:px-6">
        {empty ? (
          <p className="flex h-56 items-center justify-center rounded-xl border border-dashed border-line px-6 text-center text-ink-muted">
            {emptyMessage}
          </p>
        ) : (
          <>
            {/* The canvas is decorative for screen readers: the table below carries the data. */}
            <div className="relative h-56" aria-hidden="true">
              {children}
            </div>
            {table}
          </>
        )}
      </div>
    </Card>
  )
}

/** Visually hidden data table with the exact values behind a chart. */
export function ChartTable({ caption, headers, rows }) {
  return (
    <table className="sr-only">
      <caption>{caption}</caption>
      <thead>
        <tr>
          {headers.map((h) => (
            <th key={h} scope="col">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((cells, i) => (
          <tr key={i}>
            {cells.map((cell, j) => (
              <td key={j}>{cell}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
