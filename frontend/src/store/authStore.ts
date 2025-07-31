import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface User {
  id: string
  username: string
  role: 'admin' | 'user'
}

export interface AuthStore {
  // Auth state
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  
  // Actions
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  setUser: (user: User | null) => void
  setToken: (token: string | null) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  clearError: () => void
  checkAuth: () => void
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      // Initial state
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      // Actions
      login: async (username: string, password: string) => {
        set({ isLoading: true, error: null })
        
        try {
          const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/auth/login`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, password }),
          })

          if (!response.ok) {
            const errorData = await response.json()
            throw new Error(errorData.detail || 'Login failed')
          }

          const data = await response.json()
          const token = data.access_token
          
          // Store token in localStorage for API client
          localStorage.setItem('auth_token', token)
          
          // Decode token to get user info (simplified - in production use proper JWT library)
          const payload = JSON.parse(atob(token.split('.')[1]))
          const user: User = {
            id: payload.sub,
            username: payload.username || username,
            role: payload.role || 'admin'
          }

          set({
            user,
            token,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          })
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Login failed',
            isLoading: false,
          })
          throw error
        }
      },

      logout: () => {
        localStorage.removeItem('auth_token')
        set({
          user: null,
          token: null,
          isAuthenticated: false,
          error: null,
        })
      },

      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setToken: (token) => set({ token }),
      setLoading: (isLoading) => set({ isLoading }),
      setError: (error) => set({ error }),
      clearError: () => set({ error: null }),

      checkAuth: () => {
        const token = localStorage.getItem('auth_token')
        if (token) {
          try {
            const payload = JSON.parse(atob(token.split('.')[1]))
            const now = Date.now() / 1000
            
            if (payload.exp && payload.exp > now) {
              const user: User = {
                id: payload.sub,
                username: payload.username,
                role: payload.role || 'admin'
              }
              set({
                user,
                token,
                isAuthenticated: true,
              })
            } else {
              // Token expired
              get().logout()
            }
          } catch {
            // Invalid token
            get().logout()
          }
        }
      },
    }),
    {
      name: 'auth-store',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)