import { renderHook, act } from '@testing-library/react'
import { useLaunchStore } from '../launchStore'

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

describe('useLaunchStore', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    localStorageMock.getItem.mockReturnValue(null)
  })

  it('initializes with default state', () => {
    const { result } = renderHook(() => useLaunchStore())

    expect(result.current.launches).toEqual([])
    expect(result.current.upcomingLaunches).toEqual([])
    expect(result.current.currentLaunch).toBeNull()
    expect(result.current.isLoading).toBe(false)
    expect(result.current.error).toBeNull()
    expect(result.current.preferences).toEqual({
      theme: 'system',
      itemsPerPage: 12,
      defaultView: 'grid',
    })
  })

  it('updates launches correctly', () => {
    const { result } = renderHook(() => useLaunchStore())
    const mockLaunches = [
      {
        slug: 'test-launch',
        mission_name: 'Test Launch',
        launch_date: '2024-01-01T00:00:00Z',
        status: 'upcoming' as const,
        vehicle_type: null,
        payload_mass: null,
        orbit: null,
        details: null,
        mission_patch_url: null,
        webcast_url: null,
      },
    ]

    act(() => {
      result.current.setLaunches(mockLaunches)
    })

    expect(result.current.launches).toEqual(mockLaunches)
  })

  it('updates loading state correctly', () => {
    const { result } = renderHook(() => useLaunchStore())

    act(() => {
      result.current.setLoading(true)
    })

    expect(result.current.isLoading).toBe(true)

    act(() => {
      result.current.setLoading(false)
    })

    expect(result.current.isLoading).toBe(false)
  })

  it('updates error state correctly', () => {
    const { result } = renderHook(() => useLaunchStore())
    const errorMessage = 'Something went wrong'

    act(() => {
      result.current.setError(errorMessage)
    })

    expect(result.current.error).toBe(errorMessage)

    act(() => {
      result.current.clearError()
    })

    expect(result.current.error).toBeNull()
  })

  it('updates preferences correctly', () => {
    const { result } = renderHook(() => useLaunchStore())

    act(() => {
      result.current.updatePreferences({
        theme: 'dark',
        itemsPerPage: 24,
      })
    })

    expect(result.current.preferences).toEqual({
      theme: 'dark',
      itemsPerPage: 24,
      defaultView: 'grid',
    })
  })

  it('sets current launch correctly', () => {
    const { result } = renderHook(() => useLaunchStore())
    const mockLaunch = {
      slug: 'test-launch',
      mission_name: 'Test Launch',
      launch_date: '2024-01-01T00:00:00Z',
      status: 'upcoming' as const,
      vehicle_type: null,
      payload_mass: null,
      orbit: null,
      details: null,
      mission_patch_url: null,
      webcast_url: null,
    }

    act(() => {
      result.current.setCurrentLaunch(mockLaunch)
    })

    expect(result.current.currentLaunch).toEqual(mockLaunch)

    act(() => {
      result.current.setCurrentLaunch(null)
    })

    expect(result.current.currentLaunch).toBeNull()
  })
})