import { renderHook, act } from '@testing-library/react'
import { useDebounce } from '../useDebounce'

// Mock timers
jest.useFakeTimers()

describe('useDebounce', () => {
  afterEach(() => {
    jest.clearAllTimers()
  })

  it('returns initial value immediately', () => {
    const { result } = renderHook(() => useDebounce('initial', 500))
    
    expect(result.current).toBe('initial')
  })

  it('debounces value changes', () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      {
        initialProps: { value: 'initial', delay: 500 }
      }
    )

    expect(result.current).toBe('initial')

    // Change the value
    rerender({ value: 'updated', delay: 500 })
    
    // Value should not change immediately
    expect(result.current).toBe('initial')

    // Fast-forward time by less than delay
    act(() => {
      jest.advanceTimersByTime(300)
    })
    
    // Value should still be the old one
    expect(result.current).toBe('initial')

    // Fast-forward time to complete the delay
    act(() => {
      jest.advanceTimersByTime(200)
    })
    
    // Now the value should be updated
    expect(result.current).toBe('updated')
  })

  it('cancels previous timeout when value changes quickly', () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      {
        initialProps: { value: 'initial', delay: 500 }
      }
    )

    // Change value multiple times quickly
    rerender({ value: 'first', delay: 500 })
    
    act(() => {
      jest.advanceTimersByTime(200)
    })
    
    rerender({ value: 'second', delay: 500 })
    
    act(() => {
      jest.advanceTimersByTime(200)
    })
    
    rerender({ value: 'final', delay: 500 })

    // Value should still be initial
    expect(result.current).toBe('initial')

    // Complete the final timeout
    act(() => {
      jest.advanceTimersByTime(500)
    })

    // Should have the final value, not intermediate ones
    expect(result.current).toBe('final')
  })

  it('works with different data types', () => {
    // Test with numbers
    const { result: numberResult, rerender: numberRerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      {
        initialProps: { value: 0, delay: 300 }
      }
    )

    numberRerender({ value: 42, delay: 300 })
    
    act(() => {
      jest.advanceTimersByTime(300)
    })
    
    expect(numberResult.current).toBe(42)

    // Test with objects
    const { result: objectResult, rerender: objectRerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      {
        initialProps: { value: { id: 1 }, delay: 300 }
      }
    )

    const newObject = { id: 2 }
    objectRerender({ value: newObject, delay: 300 })
    
    act(() => {
      jest.advanceTimersByTime(300)
    })
    
    expect(objectResult.current).toBe(newObject)

    // Test with arrays
    const { result: arrayResult, rerender: arrayRerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      {
        initialProps: { value: [1, 2, 3], delay: 300 }
      }
    )

    const newArray = [4, 5, 6]
    arrayRerender({ value: newArray, delay: 300 })
    
    act(() => {
      jest.advanceTimersByTime(300)
    })
    
    expect(arrayResult.current).toBe(newArray)
  })

  it('handles delay changes', () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      {
        initialProps: { value: 'initial', delay: 500 }
      }
    )

    // Change value and delay
    rerender({ value: 'updated', delay: 1000 })
    
    // Advance by original delay amount
    act(() => {
      jest.advanceTimersByTime(500)
    })
    
    // Should still be initial because delay was increased
    expect(result.current).toBe('initial')

    // Advance by remaining time
    act(() => {
      jest.advanceTimersByTime(500)
    })
    
    // Now should be updated
    expect(result.current).toBe('updated')
  })

  it('cleans up timeout on unmount', () => {
    const { unmount } = renderHook(() => useDebounce('test', 500))
    
    // Spy on clearTimeout to ensure cleanup
    const clearTimeoutSpy = jest.spyOn(global, 'clearTimeout')
    
    unmount()
    
    expect(clearTimeoutSpy).toHaveBeenCalled()
    
    clearTimeoutSpy.mockRestore()
  })

  it('handles zero delay', () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      {
        initialProps: { value: 'initial', delay: 0 }
      }
    )

    rerender({ value: 'updated', delay: 0 })
    
    // Even with zero delay, should wait for next tick
    expect(result.current).toBe('initial')
    
    act(() => {
      jest.advanceTimersByTime(0)
    })
    
    expect(result.current).toBe('updated')
  })

  it('handles same value updates', () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      {
        initialProps: { value: 'same', delay: 500 }
      }
    )

    // Update with same value
    rerender({ value: 'same', delay: 500 })
    
    act(() => {
      jest.advanceTimersByTime(500)
    })
    
    // Should still work correctly
    expect(result.current).toBe('same')
  })
})