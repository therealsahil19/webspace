import { renderHook, act } from '@testing-library/react'
import { useInfiniteScroll } from '../useInfiniteScroll'

// Mock DOM properties
Object.defineProperty(document.documentElement, 'scrollTop', {
  writable: true,
  value: 0,
})

Object.defineProperty(document.documentElement, 'scrollHeight', {
  writable: true,
  value: 1000,
})

Object.defineProperty(document.documentElement, 'clientHeight', {
  writable: true,
  value: 800,
})

describe('useInfiniteScroll', () => {
  const mockFetchNextPage = jest.fn()

  beforeEach(() => {
    jest.clearAllMocks()
    // Reset scroll position
    document.documentElement.scrollTop = 0
    document.documentElement.scrollHeight = 1000
    document.documentElement.clientHeight = 800
  })

  afterEach(() => {
    // Clean up event listeners
    window.removeEventListener('scroll', expect.any(Function))
  })

  it('initializes with correct default state', () => {
    const { result } = renderHook(() =>
      useInfiniteScroll(mockFetchNextPage, {
        hasNextPage: true,
        isLoading: false,
      })
    )

    expect(result.current.isFetching).toBe(false)
  })

  it('triggers fetch when scrolled near bottom', async () => {
    mockFetchNextPage.mockResolvedValue(undefined)

    const { result } = renderHook(() =>
      useInfiniteScroll(mockFetchNextPage, {
        hasNextPage: true,
        isLoading: false,
        threshold: 100,
      })
    )

    // Simulate scrolling near bottom (within threshold)
    document.documentElement.scrollTop = 750 // 750 + 800 = 1550, which is > 1000 - 100

    // Trigger scroll event
    act(() => {
      window.dispatchEvent(new Event('scroll'))
    })

    expect(result.current.isFetching).toBe(true)

    // Wait for async operation to complete
    await act(async () => {
      await Promise.resolve()
    })

    expect(mockFetchNextPage).toHaveBeenCalledTimes(1)
    expect(result.current.isFetching).toBe(false)
  })

  it('does not trigger fetch when not scrolled enough', () => {
    const { result } = renderHook(() =>
      useInfiniteScroll(mockFetchNextPage, {
        hasNextPage: true,
        isLoading: false,
        threshold: 100,
      })
    )

    // Simulate scrolling but not near bottom
    document.documentElement.scrollTop = 100

    act(() => {
      window.dispatchEvent(new Event('scroll'))
    })

    expect(result.current.isFetching).toBe(false)
    expect(mockFetchNextPage).not.toHaveBeenCalled()
  })

  it('does not trigger fetch when hasNextPage is false', () => {
    const { result } = renderHook(() =>
      useInfiniteScroll(mockFetchNextPage, {
        hasNextPage: false,
        isLoading: false,
        threshold: 100,
      })
    )

    // Simulate scrolling to bottom
    document.documentElement.scrollTop = 900

    act(() => {
      window.dispatchEvent(new Event('scroll'))
    })

    expect(result.current.isFetching).toBe(false)
    expect(mockFetchNextPage).not.toHaveBeenCalled()
  })

  it('does not trigger fetch when already loading', () => {
    const { result } = renderHook(() =>
      useInfiniteScroll(mockFetchNextPage, {
        hasNextPage: true,
        isLoading: true,
        threshold: 100,
      })
    )

    // Simulate scrolling to bottom
    document.documentElement.scrollTop = 900

    act(() => {
      window.dispatchEvent(new Event('scroll'))
    })

    expect(result.current.isFetching).toBe(false)
    expect(mockFetchNextPage).not.toHaveBeenCalled()
  })

  it('does not trigger fetch when already fetching', async () => {
    let resolvePromise: () => void
    const slowFetchNextPage = jest.fn(() => new Promise<void>(resolve => {
      resolvePromise = resolve
    }))

    const { result } = renderHook(() =>
      useInfiniteScroll(slowFetchNextPage, {
        hasNextPage: true,
        isLoading: false,
        threshold: 100,
      })
    )

    // First scroll event
    document.documentElement.scrollTop = 900
    act(() => {
      window.dispatchEvent(new Event('scroll'))
    })

    expect(result.current.isFetching).toBe(true)
    expect(slowFetchNextPage).toHaveBeenCalledTimes(1)

    // Second scroll event while still fetching
    act(() => {
      window.dispatchEvent(new Event('scroll'))
    })

    // Should not trigger another fetch
    expect(slowFetchNextPage).toHaveBeenCalledTimes(1)

    // Resolve the promise
    await act(async () => {
      resolvePromise!()
      await Promise.resolve()
    })

    expect(result.current.isFetching).toBe(false)
  })

  it('uses custom threshold correctly', () => {
    const { result } = renderHook(() =>
      useInfiniteScroll(mockFetchNextPage, {
        hasNextPage: true,
        isLoading: false,
        threshold: 200,
      })
    )

    // Scroll to position that would trigger with default threshold but not custom
    document.documentElement.scrollTop = 850 // 850 + 800 = 1650, which is > 1000 - 200 but < 1000 - 100

    act(() => {
      window.dispatchEvent(new Event('scroll'))
    })

    expect(result.current.isFetching).toBe(true)
    expect(mockFetchNextPage).toHaveBeenCalled()
  })

  it('uses default threshold when not provided', () => {
    const { result } = renderHook(() =>
      useInfiniteScroll(mockFetchNextPage, {
        hasNextPage: true,
        isLoading: false,
        // threshold not provided, should default to 100
      })
    )

    // Scroll to position that triggers with default threshold (100)
    document.documentElement.scrollTop = 850 // 850 + 800 = 1650, which is > 1000 - 100

    act(() => {
      window.dispatchEvent(new Event('scroll'))
    })

    expect(result.current.isFetching).toBe(true)
    expect(mockFetchNextPage).toHaveBeenCalled()
  })

  it('handles fetch errors gracefully', async () => {
    const mockError = new Error('Fetch failed')
    mockFetchNextPage.mockRejectedValue(mockError)

    const { result } = renderHook(() =>
      useInfiniteScroll(mockFetchNextPage, {
        hasNextPage: true,
        isLoading: false,
      })
    )

    document.documentElement.scrollTop = 900

    act(() => {
      window.dispatchEvent(new Event('scroll'))
    })

    expect(result.current.isFetching).toBe(true)

    // Wait for error to be handled
    await act(async () => {
      try {
        await Promise.resolve()
      } catch (error) {
        // Ignore the error in test
      }
    })

    // Should reset fetching state even after error
    expect(result.current.isFetching).toBe(false)
  })

  it('cleans up scroll event listener on unmount', () => {
    const removeEventListenerSpy = jest.spyOn(window, 'removeEventListener')

    const { unmount } = renderHook(() =>
      useInfiniteScroll(mockFetchNextPage, {
        hasNextPage: true,
        isLoading: false,
      })
    )

    unmount()

    expect(removeEventListenerSpy).toHaveBeenCalledWith('scroll', expect.any(Function))

    removeEventListenerSpy.mockRestore()
  })

  it('updates scroll handler when dependencies change', () => {
    const { rerender } = renderHook(
      ({ hasNextPage, isLoading }) =>
        useInfiniteScroll(mockFetchNextPage, {
          hasNextPage,
          isLoading,
        }),
      {
        initialProps: { hasNextPage: true, isLoading: false }
      }
    )

    // Scroll to trigger
    document.documentElement.scrollTop = 900
    act(() => {
      window.dispatchEvent(new Event('scroll'))
    })

    expect(mockFetchNextPage).toHaveBeenCalledTimes(1)

    // Change props to prevent fetching
    rerender({ hasNextPage: false, isLoading: false })

    // Reset mock and scroll again
    mockFetchNextPage.mockClear()
    act(() => {
      window.dispatchEvent(new Event('scroll'))
    })

    // Should not fetch because hasNextPage is now false
    expect(mockFetchNextPage).not.toHaveBeenCalled()
  })

  it('handles edge case where scroll position equals threshold exactly', () => {
    const { result } = renderHook(() =>
      useInfiniteScroll(mockFetchNextPage, {
        hasNextPage: true,
        isLoading: false,
        threshold: 100,
      })
    )

    // Set scroll position exactly at threshold
    document.documentElement.scrollTop = 100 // 100 + 800 = 900, which equals 1000 - 100

    act(() => {
      window.dispatchEvent(new Event('scroll'))
    })

    expect(result.current.isFetching).toBe(true)
    expect(mockFetchNextPage).toHaveBeenCalled()
  })
})