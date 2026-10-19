export default function Profile({ user, expiresAt, onLogout }) {
  const expiry = new Date(expiresAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

  return (
    <div className="space-y-5">
      <p role="status" className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
        You are logged in.
      </p>

      <dl className="divide-y divide-slate-100 rounded-lg border border-slate-200 text-sm">
        {[
          ['Email', user.email],
          ['Display name', user.display_name ?? '—'],
          ['Time zone', user.timezone],
          ['Member since', new Date(user.created_at).toLocaleDateString()],
        ].map(([label, value]) => (
          <div key={label} className="flex justify-between gap-4 px-4 py-3">
            <dt className="text-slate-500">{label}</dt>
            <dd className="truncate font-medium text-slate-900">{value}</dd>
          </div>
        ))}
      </dl>

      <p className="text-xs text-slate-500">
        For your security, this session ends at {expiry} or when you reload the page.
      </p>

      <button
        type="button"
        onClick={onLogout}
        className="w-full rounded-lg border border-slate-300 py-2.5 font-semibold text-slate-700 transition hover:bg-slate-50"
      >
        Log out
      </button>
    </div>
  )
}
