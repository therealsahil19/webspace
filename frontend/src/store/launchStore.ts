import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { LaunchData } from '@/lib/api'

interface LaunchStore {
  // Launch data
  launches: LaunchData[]
  upcomingLaunches: LaunchData[]
  currentLaunch: LaunchData | null
  
  // UI state
  isLoading: boolean
  error: string | null
  
  // User preferences
  preferences: {
    theme: 'light' | 'dark' | 'system'
    itemsPerPage: number
    defaultView: 'grid' | 'list'
  }
  
  // Actions
  setLaunches: (launches: LaunchData[]) => void
  setUpcomingLaunches: (launches: LaunchData[]) => void
  setCurrentLaunch: (launch: LaunchData | null) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  updatePreferences: (preferences: Partial<LaunchStore['preferences']>) => void
  clearError: () => void
}

export const useLaunchStore = create<LaunchStore>()(
  persist(
    (set) => ({
      // Initial state
      launches: [],
      upcomingLaunches: [],
      currentLaunch: null,
      isLoading: false,
      error: null,
      preferences: {
        theme: 'system',
        itemsPerPage: 12,
        defaultView: 'grid',
      },

      // Actions
      setLaunches: (launches) => set({ launches }),
      setUpcomingLaunches: (upcomingLaunches) => set({ upcomingLaunches }),
      setCurrentLaunch: (currentLaunch) => set({ currentLaunch }),
      setLoading: (isLoading) => set({ isLoading }),
      setError: (error) => set({ error }),
      clearError: () => set({ error: null }),
      updatePreferences: (newPreferences) =>
        set((state) => ({
          preferences: { ...state.preferences, ...newPreferences },
        })),
    }),
    {
      name: 'launch-store',
      // Only persist user preferences, not the launch data
      partialize: (state) => ({ preferences: state.preferences }),
    }
  )
)