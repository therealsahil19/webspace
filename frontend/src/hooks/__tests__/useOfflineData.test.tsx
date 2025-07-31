import React from 'react'
import { renderHook, act } from '@testing-library/react'
import '@testing-library/jest-dom'
import { useOfflineData } from '../useOfflineData'

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
}

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
})

// Mock navigator.onLine
Object.defineProperty(navigator, 'onLine', {
  writable: true,
  value: true,
})

describe('useOfflineData', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    localStorageMock.getItem.mockReturnValue(null)
  })

  it('initializes with default values', () => {
    const { result } = renderHook(() => useOfflineData('test-key'))

    expect(result.current.cachedData).toBeNull()
    expect(result.current.isStale).toBe(false)
    expect(result.current.isOnline).toBe(true)
    expect(result.current.cacheAge).toBeNull()
    expect(result.current.cacheAgeString).toBeNull()
  })

  it('loads cached data from localStorage', () => {
    const cachedData = {
      data: { test: 'data' },
      timestamp: Date.now() - 1000, // 1 second ago
      isStale: false,
    }
    localStorageMock.getItem.mockReturnValue(JSON.stringify(cachedData))

    const { result } = renderHook(() => useOfflineData('test-key'))

    expect(result.current.cachedData).toEqual({ test: 'data' })
    expect(result.current.isStale).toBe(false)
  })

  it('marks data as stale when older than staleTime', () => {
    const cachedData = {
      data: { test: 'data' },
      timestamp: Date.now() - 10 * 60 * 1000, // 10 minutes ago
      isStale: false,
    }
    localStorageMock.getItem.mockReturnValue(JSON.stringify(cachedData))

    const { result } = renderHook(() => 
      useOfflineData('test-key', { staleTime: 5 * 60 * 1000 }) // 5 minutes
    )

    expect(result.current.isStale).toBe(true)
  })

  it('removes data older than maxAge', () => {
    const cachedData = {
      data: { test: 'data' },
      timestamp: Date.now() - 25 * 60 * 60 * 1000, // 25 hours ago
      isStale: false,
    }
    localStorageMock.getItem.mockReturnValue(JSON.stringify(cachedData))

    const { result } = renderHook(() => 
      useOfflineData('test-key', { maxAge: 24 * 60 * 60 * 1000 }) // 24 hours
    )

    expect(result.current.cachedData).toBeNull()
    expect(localStorageMock.removeItem).toHaveBeenCalledWith('offline_cache_test-key')
  })

  it('saves data to cache', () => {
    const { result } = renderHook(() => useOfflineData('test-key'))

    act(() => {
      result.current.saveToCache({ test: 'data' })
    })

    expect(localStorageMock.setItem).toHaveBeenCalledWith(
      'offline_cache_test-key',
      expect.stringContaining('"data":{"test":"data"}')
    )
    expect(result.current.cachedData).toEqual({ test: 'data' })
  })

  it('clears cache', () => {
    const { result } = renderHook(() => useOfflineData('test-key'))

    act(() => {
      result.current.clearCache()
    })

    expect(localStorageMock.removeItem).toHaveBeenCalledWith('offline_cache_test-key')
    expect(result.current.cachedData).toBeNull()
  })

  it('tracks online/offline status', () => {
    const { result } = renderHook(() => useOfflineData('test-key'))

    expect(result.current.isOnline).toBe(true)

    // Simulate going offline
    act(() => {
      Object.defineProperty(navigator, 'onLine', { value: false })
      window.dispatchEvent(new Event('offline'))
    })

    expect(result.current.isOnline).toBe(false)

    // Simulate going online
    act(() => {
      Object.defineProperty(navigator, 'onLine', { value: true })
      window.dispatchEvent(new Event('online'))
    })

    expect(result.current.isOnline).toBe(true)
  })

  it('calculates cache age correctly', () => {
    const now = Date.now()
    const cachedData = {
      data: { test: 'data' },
      timestamp: now - 5 * 60 * 1000, // 5 minutes ago
      isStale: false,
    }
    localStorageMock.getItem.mockReturnValue(JSON.stringify(cachedData))

    const { result } = renderHook(() => useOfflineData('test-key'))

    expect(result.current.cacheAge).toBeCloseTo(5 * 60 * 1000, -2) // Within 100ms
    expect(result.current.cacheAgeString).toBe('5 minutes ago')
  })

  it('handles localStorage errors gracefully', () => {
    localStorageMock.getItem.mockImplementation(() => {
      throw new Error('localStorage error')
    })

    const { result } = renderHook(() => useOfflineData('test-key'))

    expect(result.current.cachedData).toBeNull()
    expect(localStorageMock.removeItem).toHaveBeenCalledWith('offline_cache_test-key')
  })
})