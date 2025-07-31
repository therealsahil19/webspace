import { renderHook, act } from '@testing-library/react'
import { useAuthStore } from '../authStore'

// Mock fetch
global.fetch = jest.fn()

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

// Mock atob for JWT decoding
global.atob = jest.fn()

describe('useAuthStore', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    // Reset store state
    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    })
  })

  describe('login', () => {
    it('should login successfully with valid credentials', async () => {
      const mockToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwidXNlcm5hbWUiOiJhZG1pbiIsInJvbGUiOiJhZG1pbiIsImV4cCI6OTk5OTk5OTk5OX0.test'
      const mockPayload = {
        sub: '1234567890',
        username: 'admin',
        role: 'admin',
        exp: 9999999999
      }

      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ access_token: mockToken, token_type: 'bearer' })
      })

      ;(global.atob as jest.Mock).mockReturnValueOnce(JSON.stringify(mockPayload))

      const { result } = renderHook(() => useAuthStore())

      await act(async () => {
        await result.current.login('admin', 'password')
      })

      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/auth/login',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: 'admin', password: 'password' })
        })
      )

      expect(localStorageMock.setItem).toHaveBeenCalledWith('auth_token', mockToken)
      expect(result.current.isAuthenticated).toBe(true)
      expect(result.current.user).toEqual({
        id: '1234567890',
        username: 'admin',
        role: 'admin'
      })
      expect(result.current.token).toBe(mockToken)
      expect(result.current.error).toBeNull()
    })

    it('should handle login failure', async () => {
      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: 'Invalid credentials' })
      })

      const { result } = renderHook(() => useAuthStore())

      await act(async () => {
        try {
          await result.current.login('admin', 'wrongpassword')
        } catch (error) {
          // Expected to throw
        }
      })

      expect(result.current.isAuthenticated).toBe(false)
      expect(result.current.user).toBeNull()
      expect(result.current.error).toBe('Invalid credentials')
    })

    it('should handle network errors', async () => {
      ;(fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'))

      const { result } = renderHook(() => useAuthStore())

      await act(async () => {
        try {
          await result.current.login('admin', 'password')
        } catch (error) {
          // Expected to throw
        }
      })

      expect(result.current.isAuthenticated).toBe(false)
      expect(result.current.error).toBe('Network error')
    })
  })

  describe('logout', () => {
    it('should logout and clear all auth data', () => {
      const { result } = renderHook(() => useAuthStore())

      // Set initial authenticated state
      act(() => {
        result.current.setUser({ id: '1', username: 'admin', role: 'admin' })
        result.current.setToken('token')
      })

      expect(result.current.isAuthenticated).toBe(true)

      act(() => {
        result.current.logout()
      })

      expect(localStorageMock.removeItem).toHaveBeenCalledWith('auth_token')
      expect(result.current.isAuthenticated).toBe(false)
      expect(result.current.user).toBeNull()
      expect(result.current.token).toBeNull()
      expect(result.current.error).toBeNull()
    })
  })

  describe('checkAuth', () => {
    it('should restore auth state from valid token', () => {
      const mockToken = 'valid.token.here'
      const mockPayload = {
        sub: '1234567890',
        username: 'admin',
        role: 'admin',
        exp: Math.floor(Date.now() / 1000) + 3600 // 1 hour from now
      }

      localStorageMock.getItem.mockReturnValue(mockToken)
      ;(global.atob as jest.Mock).mockReturnValue(JSON.stringify(mockPayload))

      const { result } = renderHook(() => useAuthStore())

      act(() => {
        result.current.checkAuth()
      })

      expect(result.current.isAuthenticated).toBe(true)
      expect(result.current.user).toEqual({
        id: '1234567890',
        username: 'admin',
        role: 'admin'
      })
      expect(result.current.token).toBe(mockToken)
    })

    it('should logout if token is expired', () => {
      const mockToken = 'expired.token.here'
      const mockPayload = {
        sub: '1234567890',
        username: 'admin',
        role: 'admin',
        exp: Math.floor(Date.now() / 1000) - 3600 // 1 hour ago
      }

      localStorageMock.getItem.mockReturnValue(mockToken)
      ;(global.atob as jest.Mock).mockReturnValue(JSON.stringify(mockPayload))

      const { result } = renderHook(() => useAuthStore())

      act(() => {
        result.current.checkAuth()
      })

      expect(localStorageMock.removeItem).toHaveBeenCalledWith('auth_token')
      expect(result.current.isAuthenticated).toBe(false)
      expect(result.current.user).toBeNull()
    })

    it('should logout if token is invalid', () => {
      const mockToken = 'invalid.token'

      localStorageMock.getItem.mockReturnValue(mockToken)
      ;(global.atob as jest.Mock).mockImplementation(() => {
        throw new Error('Invalid token')
      })

      const { result } = renderHook(() => useAuthStore())

      act(() => {
        result.current.checkAuth()
      })

      expect(localStorageMock.removeItem).toHaveBeenCalledWith('auth_token')
      expect(result.current.isAuthenticated).toBe(false)
    })

    it('should do nothing if no token exists', () => {
      localStorageMock.getItem.mockReturnValue(null)

      const { result } = renderHook(() => useAuthStore())

      act(() => {
        result.current.checkAuth()
      })

      expect(result.current.isAuthenticated).toBe(false)
      expect(result.current.user).toBeNull()
    })
  })

  describe('state setters', () => {
    it('should set user and update authentication status', () => {
      const { result } = renderHook(() => useAuthStore())
      const user = { id: '1', username: 'admin', role: 'admin' as const }

      act(() => {
        result.current.setUser(user)
      })

      expect(result.current.user).toEqual(user)
      expect(result.current.isAuthenticated).toBe(true)
    })

    it('should clear user and update authentication status', () => {
      const { result } = renderHook(() => useAuthStore())

      act(() => {
        result.current.setUser({ id: '1', username: 'admin', role: 'admin' })
      })

      expect(result.current.isAuthenticated).toBe(true)

      act(() => {
        result.current.setUser(null)
      })

      expect(result.current.user).toBeNull()
      expect(result.current.isAuthenticated).toBe(false)
    })

    it('should set and clear errors', () => {
      const { result } = renderHook(() => useAuthStore())

      act(() => {
        result.current.setError('Test error')
      })

      expect(result.current.error).toBe('Test error')

      act(() => {
        result.current.clearError()
      })

      expect(result.current.error).toBeNull()
    })

    it('should set loading state', () => {
      const { result } = renderHook(() => useAuthStore())

      act(() => {
        result.current.setLoading(true)
      })

      expect(result.current.isLoading).toBe(true)

      act(() => {
        result.current.setLoading(false)
      })

      expect(result.current.isLoading).toBe(false)
    })
  })
})