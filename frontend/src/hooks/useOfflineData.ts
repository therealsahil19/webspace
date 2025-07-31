'use client'

import { useState, useEffect } from 'react'
import { LaunchData } from '@/lib/api'

interface CachedData<T> {
  data: T
  timestamp: number
  isStale: boolean
}

interface UseOfflineDataOptions {
  staleTime?: number // Time in milliseconds after which data is considered stale
  maxAge?: number // Maximum age in milliseconds before data is discarded
}

export function useOfflineData<T>(
  key: string,
  options: UseOfflineDataOptions = {}
) {
  const { staleTime = 5 * 60 * 1000, maxAge = 24 * 60 * 60 * 1000 } = options
  const [cachedData, setCachedData] = useState<CachedData<T> | null>(null)
  const [isOnline, setIsOnline] = useState(true)

  // Monitor online/offline status
  useEffect(() => {
    const handleOnline = () => setIsOnline(true)
    const handleOffline = () => setIsOnline(false)

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    // Set initial state
    setIsOnline(navigator.onLine)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  // Load cached data on mount
  useEffect(() => {
    const loadCachedData = () => {
      try {
        const cached = localStorage.getItem(`offline_cache_${key}`)
        if (cached) {
          const parsedData: CachedData<T> = JSON.parse(cached)
          const now = Date.now()
          
          // Check if data is too old
          if (now - parsedData.timestamp > maxAge) {
            localStorage.removeItem(`offline_cache_${key}`)
            return
          }

          // Mark as stale if needed
          const isStale = now - parsedData.timestamp > staleTime
          setCachedData({ ...parsedData, isStale })
        }
      } catch (error) {
        console.error('Error loading cached data:', error)
        localStorage.removeItem(`offline_cache_${key}`)
      }
    }

    loadCachedData()
  }, [key, staleTime, maxAge])

  const saveToCache = (data: T) => {
    try {
      const cacheData: CachedData<T> = {
        data,
        timestamp: Date.now(),
        isStale: false,
      }
      localStorage.setItem(`offline_cache_${key}`, JSON.stringify(cacheData))
      setCachedData(cacheData)
    } catch (error) {
      console.error('Error saving to cache:', error)
    }
  }

  const clearCache = () => {
    localStorage.removeItem(`offline_cache_${key}`)
    setCachedData(null)
  }

  const getCacheAge = () => {
    if (!cachedData) return null
    return Date.now() - cachedData.timestamp
  }

  const getCacheAgeString = () => {
    const age = getCacheAge()
    if (!age) return null

    const minutes = Math.floor(age / (1000 * 60))
    const hours = Math.floor(minutes / 60)
    const days = Math.floor(hours / 24)

    if (days > 0) return `${days} day${days > 1 ? 's' : ''} ago`
    if (hours > 0) return `${hours} hour${hours > 1 ? 's' : ''} ago`
    if (minutes > 0) return `${minutes} minute${minutes > 1 ? 's' : ''} ago`
    return 'Just now'
  }

  return {
    cachedData: cachedData?.data || null,
    isStale: cachedData?.isStale || false,
    isOnline,
    cacheAge: getCacheAge(),
    cacheAgeString: getCacheAgeString(),
    saveToCache,
    clearCache,
  }
}