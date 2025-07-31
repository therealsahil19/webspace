'use client'

import { useEffect, useState } from 'react'

interface ServiceWorkerState {
  isSupported: boolean
  isRegistered: boolean
  isOnline: boolean
  updateAvailable: boolean
  registration: ServiceWorkerRegistration | null
}

export function useServiceWorker() {
  const [state, setState] = useState<ServiceWorkerState>({
    isSupported: false,
    isRegistered: false,
    isOnline: true,
    updateAvailable: false,
    registration: null,
  })

  useEffect(() => {
    // Check if service workers are supported
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
      return
    }

    setState(prev => ({ ...prev, isSupported: true }))

    // Register service worker
    const registerSW = async () => {
      try {
        const registration = await navigator.serviceWorker.register('/sw.js', {
          scope: '/',
        })

        console.log('Service Worker registered successfully:', registration)

        setState(prev => ({
          ...prev,
          isRegistered: true,
          registration,
        }))

        // Check for updates
        registration.addEventListener('updatefound', () => {
          const newWorker = registration.installing
          if (newWorker) {
            newWorker.addEventListener('statechange', () => {
              if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                setState(prev => ({ ...prev, updateAvailable: true }))
              }
            })
          }
        })

        // Listen for messages from service worker
        navigator.serviceWorker.addEventListener('message', (event) => {
          console.log('Message from service worker:', event.data)
        })

      } catch (error) {
        console.error('Service Worker registration failed:', error)
      }
    }

    registerSW()

    // Monitor online/offline status
    const handleOnline = () => setState(prev => ({ ...prev, isOnline: true }))
    const handleOffline = () => setState(prev => ({ ...prev, isOnline: false }))

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    // Set initial online status
    setState(prev => ({ ...prev, isOnline: navigator.onLine }))

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  const updateServiceWorker = async () => {
    if (state.registration) {
      const newWorker = state.registration.waiting
      if (newWorker) {
        newWorker.postMessage({ type: 'SKIP_WAITING' })
        window.location.reload()
      }
    }
  }

  const requestBackgroundSync = async (tag: string) => {
    if ('serviceWorker' in navigator && 'sync' in window.ServiceWorkerRegistration.prototype) {
      try {
        const registration = await navigator.serviceWorker.ready
        await registration.sync.register(tag)
        console.log('Background sync registered:', tag)
      } catch (error) {
        console.error('Background sync registration failed:', error)
      }
    }
  }

  const requestNotificationPermission = async () => {
    if ('Notification' in window) {
      const permission = await Notification.requestPermission()
      return permission === 'granted'
    }
    return false
  }

  return {
    ...state,
    updateServiceWorker,
    requestBackgroundSync,
    requestNotificationPermission,
  }
}