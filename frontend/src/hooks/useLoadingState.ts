'use client'

import React, { useState, useCallback } from 'react'

interface LoadingState {
  isLoading: boolean
  message?: string
  progress?: number
}

interface UseLoadingStateReturn {
  isLoading: boolean
  message?: string
  progress?: number
  startLoading: (message?: string) => void
  stopLoading: () => void
  setProgress: (progress: number) => void
  setMessage: (message: string) => void
  withLoading: <T>(
    asyncFn: () => Promise<T>,
    message?: string
  ) => Promise<T>
}

export function useLoadingState(initialMessage?: string): UseLoadingStateReturn {
  const [state, setState] = useState<LoadingState>({
    isLoading: false,
    message: initialMessage,
    progress: undefined,
  })

  const startLoading = useCallback((message?: string) => {
    setState(prev => ({
      ...prev,
      isLoading: true,
      message: message || prev.message,
      progress: undefined,
    }))
  }, [])

  const stopLoading = useCallback(() => {
    setState(prev => ({
      ...prev,
      isLoading: false,
      progress: undefined,
    }))
  }, [])

  const setProgress = useCallback((progress: number) => {
    setState(prev => ({
      ...prev,
      progress: Math.max(0, Math.min(100, progress)),
    }))
  }, [])

  const setMessage = useCallback((message: string) => {
    setState(prev => ({
      ...prev,
      message,
    }))
  }, [])

  const withLoading = useCallback(async <T>(
    asyncFn: () => Promise<T>,
    message?: string
  ): Promise<T> => {
    startLoading(message)
    try {
      const result = await asyncFn()
      return result
    } finally {
      stopLoading()
    }
  }, [startLoading, stopLoading])

  return {
    isLoading: state.isLoading,
    message: state.message,
    progress: state.progress,
    startLoading,
    stopLoading,
    setProgress,
    setMessage,
    withLoading,
  }
}

// Global loading state for app-wide loading indicators
let globalLoadingState = {
  isLoading: false,
  message: undefined as string | undefined,
  listeners: new Set<(state: { isLoading: boolean; message?: string }) => void>(),
}

export function useGlobalLoading() {
  const [state, setState] = useState({
    isLoading: globalLoadingState.isLoading,
    message: globalLoadingState.message,
  })

  const subscribe = useCallback((listener: typeof setState) => {
    globalLoadingState.listeners.add(listener)
    return () => globalLoadingState.listeners.delete(listener)
  }, [])

  const startGlobalLoading = useCallback((message?: string) => {
    globalLoadingState.isLoading = true
    globalLoadingState.message = message
    globalLoadingState.listeners.forEach(listener => 
      listener({ isLoading: true, message })
    )
  }, [])

  const stopGlobalLoading = useCallback(() => {
    globalLoadingState.isLoading = false
    globalLoadingState.message = undefined
    globalLoadingState.listeners.forEach(listener => 
      listener({ isLoading: false, message: undefined })
    )
  }, [])

  // Subscribe to global state changes
  React.useEffect(() => {
    return subscribe(setState)
  }, [subscribe])

  return {
    isLoading: state.isLoading,
    message: state.message,
    startGlobalLoading,
    stopGlobalLoading,
  }
}