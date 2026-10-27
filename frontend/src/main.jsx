import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
// Self-hosted fonts: no requests to third-party font servers.
import '@fontsource-variable/atkinson-hyperlegible-next/wght.css'
import '@fontsource-variable/fraunces/opsz.css'
import '@fontsource-variable/noto-sans-arabic/wght.css'
import './index.css'
import App from './App.jsx'
import AuthProvider from './auth/AuthProvider.jsx'
import I18nProvider from './i18n/I18nProvider.jsx'
import ThemeProvider from './theme/ThemeProvider.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <I18nProvider>
      <ThemeProvider>
        <AuthProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </AuthProvider>
      </ThemeProvider>
    </I18nProvider>
  </StrictMode>,
)
