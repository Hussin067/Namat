import { Suspense, useEffect, useRef } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'
import { CirclePlus, FileText, History, LayoutDashboard, LogOut, NotebookPen, UserRound } from 'lucide-react'
import { useAuth } from '../../auth/auth-context.js'
import { useI18n } from '../../i18n/i18n-context.js'
import LanguageSwitch from '../ui/LanguageSwitch.jsx'
import Logo from '../ui/Logo.jsx'
import { LoadingState } from '../ui/States.jsx'
import ThemeToggle from '../ui/ThemeToggle.jsx'
import { cx } from '../ui/styles.js'

const NAV_ITEMS = [
  { to: '/dashboard', key: 'dashboard', icon: LayoutDashboard },
  { to: '/history', key: 'history', icon: History },
  { to: '/log', key: 'log', icon: CirclePlus },
  { to: '/daily', key: 'daily', icon: NotebookPen },
  { to: '/report', key: 'report', icon: FileText },
  { to: '/profile', key: 'profile', icon: UserRound },
]

function SidebarLink({ to, label, icon: Icon, forceActive }) {
  return (
    <NavLink
      to={to}
      className={({ isActive: routeActive }) => {
        const isActive = routeActive || forceActive
        return cx(
          'group flex min-h-11 items-center gap-3 rounded-xl px-3 text-[0.9375rem] font-medium transition-colors',
          isActive ? 'bg-brand-soft text-brand-ink' : 'text-ink-muted hover:bg-sunken hover:text-ink',
        )
      }}
    >
      <Icon aria-hidden="true" className="size-5 shrink-0" />
      {label}
    </NavLink>
  )
}

function TabLink({ to, label, icon: Icon, forceActive }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cx(
          'flex min-h-14 min-w-0 flex-1 flex-col items-center justify-center gap-0.5 text-[0.6875rem] font-semibold transition-colors',
          isActive || forceActive ? 'text-brand' : 'text-ink-muted hover:text-ink',
        )
      }
    >
      {({ isActive: routeActive }) => {
        const isActive = routeActive || forceActive
        return (
        <>
          <span className={cx('rounded-full px-3 py-1 transition-colors', isActive && 'bg-brand-soft')}>
            <Icon aria-hidden="true" className="size-5" />
          </span>
          {label}
        </>
        )
      }}
    </NavLink>
  )
}

export default function AppShell() {
  const { user, logout } = useAuth()
  const { t } = useI18n()
  const { pathname } = useLocation()
  const onEpisode = pathname.startsWith('/episodes/')
  const mainRef = useRef(null)
  const firstRender = useRef(true)

  // After navigating, move focus to the new page so screen readers announce it.
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    window.scrollTo({ top: 0 })
    mainRef.current?.focus({ preventScroll: true })
  }, [pathname])

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[17rem_1fr]">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:start-3 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-4 focus:py-2 focus:shadow-pop"
      >
        {t('common.skipToMain')}
      </a>

      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-dvh flex-col border-e border-line bg-surface/60 px-4 py-6 lg:flex">
        <div className="px-2">
          <Logo />
        </div>
        <nav aria-label={t('nav.main')} className="mt-10 flex flex-col gap-1">
          {NAV_ITEMS.map(({ to, key, icon }) => (
            <SidebarLink key={to} to={to} icon={icon} label={t(`nav.${key}`)} forceActive={onEpisode && key === 'history'} />
          ))}
        </nav>
        <div className="mt-auto space-y-3 border-t border-line pt-5">
          <div className="flex gap-2">
            <ThemeToggle className="flex-1" />
            <LanguageSwitch />
          </div>
          <div className="px-1 pt-1">
            <p className="truncate text-sm font-semibold text-ink" title={user?.email}>
              {user?.display_name || user?.email}
            </p>
            <button
              type="button"
              onClick={() => logout()}
              className="mt-1 inline-flex min-h-9 items-center gap-2 rounded-lg text-sm font-medium text-ink-muted transition-colors hover:text-ink"
            >
              <LogOut aria-hidden="true" className="size-4 rtl:-scale-x-100" />
              {t('common.logOut')}
            </button>
          </div>
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-line bg-canvas/90 px-4 py-3 backdrop-blur lg:hidden">
        <Logo />
        <div className="flex items-center gap-2">
          <LanguageSwitch />
          <ThemeToggle />
        </div>
      </header>

      <main
        id="main"
        ref={mainRef}
        tabIndex={-1}
        className="mx-auto w-full max-w-5xl px-4 pt-8 pb-28 focus:outline-none sm:px-6 lg:px-10 lg:pt-12 lg:pb-16"
      >
        <Suspense fallback={<LoadingState />}>
          <Outlet />
        </Suspense>
      </main>

      {/* Mobile tab bar */}
      <nav
        aria-label={t('nav.main')}
        className="fixed inset-x-0 bottom-0 z-20 flex border-t border-line bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden"
      >
        {NAV_ITEMS.map(({ to, key, icon }) => (
          <TabLink key={to} to={to} icon={icon} label={t(`nav.short.${key}`)} forceActive={onEpisode && key === 'history'} />
        ))}
      </nav>
    </div>
  )
}
