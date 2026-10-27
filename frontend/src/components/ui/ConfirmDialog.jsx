import { useEffect, useId, useRef } from 'react'
import Button from './Button.jsx'

/**
 * Confirmation built on the native <dialog>: the browser traps focus, closes
 * on Escape and restores focus afterwards. "Cancel" gets focus first, so a
 * stray Enter never confirms a destructive action.
 */
export default function ConfirmDialog({ open, title, children, confirmLabel, cancelLabel, busy, busyLabel, onConfirm, onCancel }) {
  const ref = useRef(null)
  const titleId = useId()
  const bodyId = useId()

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      aria-describedby={bodyId}
      onCancel={(event) => {
        event.preventDefault() // keep React in charge of open/closed
        if (!busy) onCancel()
      }}
      className="m-auto w-[calc(100%-2rem)] max-w-md rounded-2xl border border-line bg-surface p-0 text-ink shadow-pop backdrop:bg-black/45"
    >
      <div className="p-6">
        <h2 id={titleId} className="text-xl font-semibold">
          {title}
        </h2>
        <div id={bodyId} className="mt-2 text-ink-muted">
          {children}
        </div>
        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Button variant="secondary" onClick={onCancel} disabled={busy} autoFocus>
            {cancelLabel}
          </Button>
          <Button variant="danger" onClick={onConfirm} loading={busy} loadingText={busyLabel}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </dialog>
  )
}
