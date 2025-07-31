'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import { useAuthStore } from '@/store/authStore'
import { useServiceWorker } from '@/hooks/useServiceWorker'
import { getErrorType } from '@/components/ui/ErrorMessage'

function AuthInitializer({ children }: { children: React.ReactNode }) {
  const checkAuth = useAuthStore(state => state.checkAuth)
  
  useEffect(() => {
    checkAuth()
  }, [checkAuth])
  
  return <>{children}</>
}

function ServiceWorkerInitializer({ children }: { children: React.ReactNode }) {
  const { isSupported, isRegistered, updateAvailable } = useServiceWorker()
  
  useEffect(() => {
    if (updateAvailable) {
      // You could show a toast notification here
      console.log('App update available')
    }
  }, [updateAvailable])
  
  return <>{children}</>
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5 * 60 * 1000, // 5 minutes
            gcTime: 10 * 60 * 1000, // 10 minutes
            retry: (failureCount, error: unknown) => {
              // Don't retry on 4xx errors
              const errorType = getErrorType(error)
              if (errorType === 'unauthorized' || errorType === 'not-found' || errorType === 'validation') {
                return false
              }
              return failureCount < 3
            },
            retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
          },
          mutations: {
            retry: (failureCount, error: unknown) => {
              const errorType = getErrorType(error)
              if (errorType === 'unauthorized' || errorType === 'not-found' || errorType === 'validation') {
                return false
              }
              return failureCount < 2
            },
          },
        },
      })
  )

  return (
    <QueryClientProvider client={queryClient}>
      <ServiceWorkerInitializer>
        <AuthInitializer>
          {children}
        </AuthInitializer>
      </ServiceWorkerInitializer>
    </QueryClientProvider>
  )
}