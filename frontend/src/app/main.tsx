/* eslint-disable react-refresh/only-export-components */
import React from 'react'
import ReactDOM from 'react-dom/client'
import { ErrorBoundary } from 'react-error-boundary'
import App from './App'
import './globals.css'

function GlobalErrorFallback({ error }: { error: Error }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-2xl font-bold text-destructive">Something went wrong</h1>
      <p className="text-muted-foreground">{error.message}</p>
      <button
        className="rounded bg-primary px-4 py-2 text-primary-foreground"
        onClick={() => window.location.reload()}
      >
        Reload page
      </button>
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary FallbackComponent={GlobalErrorFallback}>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
)
