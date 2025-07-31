'use client'

import React from 'react'
import { ErrorBoundary } from './ErrorBoundary'
import { ErrorMessage } from './ErrorMessage'

interface ApiErrorBoundaryProps {
  children: React.ReactNode
  onRetry?: () => void
}

export function ApiErrorBoundary({ children, onRetry }: ApiErrorBoundaryProps) {
  const handleError = (error: Error) => {
    // Check if it's an API-related error
    if (error.message.includes('fetch') || error.message.includes('network')) {
      console.error('API Error:', error)
    }
  }

  const fallbackUI = (
    <div className="p-4">
      <ErrorMessage
        message="Unable to load data. Please check your connection and try again."
        onRetry={onRetry}
      />
    </div>
  )

  return (
    <ErrorBoundary fallback={fallbackUI} onError={handleError}>
      {children}
    </ErrorBoundary>
  )
}