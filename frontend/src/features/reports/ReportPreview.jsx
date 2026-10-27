import Badge from '../../components/ui/Badge.jsx'
import { cx } from '../../components/ui/styles.js'

// Renders the report exactly as the backend built it (the same sections the PDF
// shows). Every string arrives already in the report's language, so this file
// has no text of its own. All text is rendered as plain text: nothing typed by
// the user can inject HTML. Text the user typed uses dir="auto", so an English
// note in an Arabic report (or the reverse) keeps its own direction.

function Facts({ items }) {
  return (
    <dl className="divide-y divide-line rounded-xl border border-line">
      {items.map((item, i) => (
        <div key={i} className="grid gap-x-4 gap-y-0.5 px-4 py-2.5 sm:grid-cols-[minmax(0,13rem)_1fr]">
          <dt className="text-sm font-semibold text-ink-muted">{item.label}</dt>
          <dd className="min-w-0 text-ink break-words whitespace-pre-line">{item.value}</dd>
        </div>
      ))}
    </dl>
  )
}

function Paragraph({ block }) {
  const styles = {
    muted: 'text-sm text-ink-muted',
    label: 'text-sm font-semibold text-ink-muted',
    body: 'text-ink',
  }
  return (
    <p dir={block.user_text ? 'auto' : undefined} className={cx(styles[block.style] ?? styles.body, 'break-words whitespace-pre-line')}>
      {block.text}
    </p>
  )
}

function Table({ block }) {
  return (
    <div className="space-y-2">
      {block.title && <h4 className="font-semibold text-ink">{block.title}</h4>}
      {/* Wide tables scroll inside their own box on phones, never the page. */}
      <div className="overflow-x-auto rounded-xl border border-line" tabIndex={0} role="region" aria-label={block.title ?? undefined}>
        <table className="w-full min-w-[32rem] border-collapse text-sm">
          <thead className="bg-sunken">
            <tr>
              {block.columns.map((c, i) => (
                <th key={i} scope="col" className="px-3 py-2 text-start font-semibold text-ink">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {block.rows.map((row, r) => (
              <tr key={r}>
                {row.map((cell, i) => (
                  <td key={i} className="px-3 py-2 align-top text-ink break-words">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Bars({ block }) {
  if (!block.items.length) return null
  return (
    <figure className="min-w-0 space-y-2">
      <figcaption className="font-semibold text-ink">{block.title}</figcaption>
      <ul className="space-y-1.5">
        {block.items.map((item, i) => (
          <li key={i} className="grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)] items-center gap-3 text-sm sm:grid-cols-[minmax(0,14rem)_minmax(0,1fr)]">
            <span className="text-ink">{item.label}</span>
            <span className="flex min-w-0 items-center gap-2">
              <span
                aria-hidden="true"
                className="h-3 min-w-0 shrink rounded-sm bg-brand"
                style={{ width: `${(item.value / block.max) * 70}%`, minWidth: item.value ? '0.25rem' : 0 }}
              />
              <span className="shrink-0 text-ink-muted tabular-nums">{item.display}</span>
            </span>
          </li>
        ))}
      </ul>
    </figure>
  )
}

function Episode({ block }) {
  return (
    <article className="overflow-hidden rounded-xl border border-line">
      <h4 className="bg-brand-soft px-4 py-2 font-semibold text-brand-ink">{block.heading}</h4>
      <dl className="divide-y divide-line">
        {block.fields.map((f, i) => (
          <div key={i} className="grid grid-cols-[minmax(0,8rem)_1fr] gap-3 px-4 py-1.5 text-sm sm:grid-cols-[minmax(0,11rem)_1fr]">
            <dt className="font-semibold text-ink-muted">{f.label}</dt>
            <dd dir={f.label ? undefined : 'auto'} className="min-w-0 text-ink break-words">
              {f.value}
            </dd>
          </div>
        ))}
      </dl>
      {block.notes && (
        <div className="border-t border-line px-4 py-2.5">
          <p className="text-sm font-semibold text-ink-muted">{block.notes_label}</p>
          <p dir="auto" className="mt-0.5 text-ink break-words whitespace-pre-line">
            {block.notes}
          </p>
        </div>
      )}
    </article>
  )
}

function Observation({ block }) {
  return (
    <article className="space-y-3 rounded-xl border border-line p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h4 className="font-semibold text-ink">{block.title}</h4>
        <Badge tone={block.level === 'observed' ? 'brand' : 'neutral'}>{block.level_label}</Badge>
      </div>
      <p className="text-ink">{block.description}</p>
      <Facts items={block.facts} />
      <p className="text-sm text-ink-muted">{block.limitation}</p>
    </article>
  )
}

function Block({ block }) {
  switch (block.type) {
    case 'facts':
      return <Facts items={block.items} />
    case 'paragraph':
      return <Paragraph block={block} />
    case 'subheading':
      return <h4 className="pt-2 font-semibold text-ink">{block.text}</h4>
    case 'list':
      return (
        <ul className="list-disc space-y-1.5 ps-5 text-ink marker:text-brand">
          {block.items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      )
    case 'table':
      return <Table block={block} />
    case 'bars':
      return <Bars block={block} />
    case 'episode':
      return <Episode block={block} />
    case 'observation':
      return <Observation block={block} />
    case 'callout':
      return <p className="rounded-xl border border-line bg-sunken px-4 py-3 text-ink">{block.text}</p>
    default:
      return null // an unknown block type is skipped, never guessed
  }
}

export default function ReportPreview({ report }) {
  return (
    <article lang={report.language} dir={report.direction} className="space-y-10" aria-label={report.title}>
      <header className="border-b-4 border-brand pb-4">
        <h2 className="text-2xl font-semibold text-brand sm:text-3xl">{report.title}</h2>
        <p className="mt-1 text-ink-muted">{report.subtitle}</p>
        <p className="mt-1 font-semibold text-ink">{report.period_label}</p>
      </header>
      {report.sections.map((s) => (
        <section key={s.id} aria-labelledby={`report-${s.id}`} className="space-y-4">
          <h3 id={`report-${s.id}`} className="border-b-2 border-brand pb-1 text-xl font-semibold text-brand">
            {s.title}
          </h3>
          {s.blocks.map((b, i) => (
            <Block key={i} block={b} />
          ))}
        </section>
      ))}
    </article>
  )
}
