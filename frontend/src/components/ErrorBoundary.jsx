import { Component } from 'react'
import { I18nContext } from '../i18n/i18n-context.js'
import { ErrorState } from './ui/States.jsx'

/** Keeps one broken component from blanking the whole app. */
export default class ErrorBoundary extends Component {
  static contextType = I18nContext

  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  render() {
    if (!this.state.hasError) return this.props.children
    const { t } = this.context
    return (
      <div className="flex min-h-[60dvh] items-center justify-center px-5">
        <ErrorState
          title={t('errorBoundary.title')}
          message={t('errorBoundary.body')}
          onRetry={() => window.location.reload()}
        />
      </div>
    )
  }
}
