// The medical report (backend: GET /reports/medical and /reports/medical/pdf).
// The backend builds every section, in the
// report's language, from the signed-in user's records; the preview and the
// PDF show exactly the same content. `request` is useAuth().authRequest, so
// the token never passes through page code.

function reportQuery({ filters, lang }) {
  const params = new URLSearchParams({ lang })
  if (filters.period === 'custom') {
    params.set('start_date', filters.start)
    params.set('end_date', filters.end)
  } else {
    params.set('period', filters.period)
  }
  return params
}

export function getMedicalReport(request, options, { signal } = {}) {
  return request(`/reports/medical?${reportQuery(options)}`, { signal })
}

/** Resolves to { blob, filename } for the PDF of the same report. */
export function getMedicalReportPdf(request, options) {
  return request(`/reports/medical/pdf?${reportQuery(options)}`, { responseType: 'file' })
}

/** Hand a downloaded file to the browser's "save" flow. Nothing is stored or uploaded. */
export function saveFile({ blob, filename }) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename ?? 'namat-medical-report.pdf'
  document.body.append(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
