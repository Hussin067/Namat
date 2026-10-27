import { useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { useI18n } from '../../i18n/i18n-context.js'
import { Input } from './Field.jsx'

export default function PasswordInput({ id, ...props }) {
  const [visible, setVisible] = useState(false)
  const { t } = useI18n()
  return (
    <div className="relative">
      <Input id={id} type={visible ? 'text' : 'password'} className="pe-12" {...props} />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={t('auth.showPassword')}
        aria-pressed={visible}
        aria-controls={id}
        className="absolute inset-y-0 end-0 flex w-11 items-center justify-center rounded-e-xl text-ink-muted transition-colors hover:text-ink"
      >
        {visible ? <EyeOff aria-hidden="true" className="size-5" /> : <Eye aria-hidden="true" className="size-5" />}
      </button>
    </div>
  )
}
