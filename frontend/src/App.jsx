import { lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router'
import { GuestOnly, RequireAuth } from './auth/RouteGuards.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import AppShell from './components/layout/AppShell.jsx'
import { DemoModeProvider } from './features/episodes/DemoModeProvider.jsx'
import LoginPage from './pages/LoginPage.jsx'
import NotFoundPage from './pages/NotFoundPage.jsx'
import RegisterPage from './pages/RegisterPage.jsx'

// Signed-in pages load on first visit, so the login screen doesn't wait for
// Chart.js or the report preview. AppShell shows a loading state meanwhile.
const DailyLogPage = lazy(() => import('./pages/DailyLogPage.jsx'))
const DashboardPage = lazy(() => import('./pages/DashboardPage.jsx'))
const EditEpisodePage = lazy(() => import('./pages/EditEpisodePage.jsx'))
const EpisodeDetailPage = lazy(() => import('./pages/EpisodeDetailPage.jsx'))
const HistoryPage = lazy(() => import('./pages/HistoryPage.jsx'))
const LogEpisodePage = lazy(() => import('./pages/LogEpisodePage.jsx'))
const MedicalReportPage = lazy(() => import('./pages/MedicalReportPage.jsx'))
const ProfilePage = lazy(() => import('./pages/ProfilePage.jsx'))

function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route element={<GuestOnly />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
        </Route>

        <Route element={<RequireAuth />}>
          <Route
            element={
              <DemoModeProvider>
                <AppShell />
              </DemoModeProvider>
            }
          >
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/episodes/:episodeId" element={<EpisodeDetailPage />} />
            <Route path="/episodes/:episodeId/edit" element={<EditEpisodePage />} />
            <Route path="/log" element={<LogEpisodePage />} />
            <Route path="/daily" element={<DailyLogPage />} />
            <Route path="/report" element={<MedicalReportPage />} />
            <Route path="/profile" element={<ProfilePage />} />
          </Route>
        </Route>

        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </ErrorBoundary>
  )
}

export default App
