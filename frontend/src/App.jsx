import { useCallback, useEffect, useState } from 'react'
import { fetchCurrentUser, loginUser, registerUser } from './api.js'
import AuthForm from './components/AuthForm.jsx'
import Profile from './components/Profile.jsx'

function App() {
  // The access token lives only in React memory: never in localStorage or
  // sessionStorage. Reloading the page or closing the tab logs the user out.
  const [session, setSession] = useState(null) // { token, user, expiresAt }
  const [mode, setMode] = useState('login')
  const [notice, setNotice] = useState(null)

  const logout = useCallback((message = null) => {
    setSession(null)
    setMode('login')
    setNotice(message)
  }, [])

  // Log out automatically when the token expires.
  useEffect(() => {
    if (!session) return undefined
    const timer = setTimeout(
      () => logout('Your session expired. Please log in again.'),
      session.expiresAt - Date.now(),
    )
    return () => clearTimeout(timer)
  }, [session, logout])

  async function handleSubmit(email, password) {
    setNotice(null)
    if (mode === 'register') {
      await registerUser(email, password)
      setMode('login')
      setNotice('Account created. You can log in now.')
      return
    }
    const { access_token: token, expires_in: expiresIn } = await loginUser(email, password)
    const user = await fetchCurrentUser(token)
    setSession({ token, user, expiresAt: Date.now() + expiresIn * 1000 })
  }

  return (
    <main className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
      <div className="max-w-md w-full rounded-2xl bg-white p-8 shadow-lg">
        <h1 className="text-3xl font-bold text-indigo-600">Migraine Tracker</h1>
        <p className="mt-2 mb-6 text-slate-600">
          {session ? 'Your account' : 'Log in or create an account to get started.'}
        </p>

        {session ? (
          <Profile user={session.user} expiresAt={session.expiresAt} onLogout={() => logout()} />
        ) : (
          <AuthForm
            mode={mode}
            onModeChange={(next) => {
              setMode(next)
              setNotice(null)
            }}
            onSubmit={handleSubmit}
            notice={notice}
          />
        )}
      </div>
    </main>
  )
}

export default App
