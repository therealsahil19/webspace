import { useState, useEffect, useCallback } from 'react'

interface UseInfiniteScrollOptions {
  hasNextPage: boolean
  isLoading: boolean
  threshold?: number
}

/**
 * Custom hook for infinite scroll functionality
 * @param fetchNextPage - Function to fetch the next page
 * @param options - Configuration options
 * @returns Object with loading state and ref for the trigger element
 */
export function useInfiniteScroll(
  fetchNextPage: () => void,
  { hasNextPage, isLoading, threshold = 100 }: UseInfiniteScrollOptions
) {
  const [isFetching, setIsFetching] = useState(false)

  const handleScroll = useCallback(() => {
    if (isLoading || !hasNextPage || isFetching) return

    const scrollTop = document.documentElement.scrollTop
    const scrollHeight = document.documentElement.scrollHeight
    const clientHeight = document.documentElement.clientHeight

    if (scrollTop + clientHeight >= scrollHeight - threshold) {
      setIsFetching(true)
    }
  }, [hasNextPage, isLoading, isFetching, threshold])

  useEffect(() => {
    if (!isFetching) return

    const loadMore = async () => {
      try {
        await fetchNextPage()
      } finally {
        setIsFetching(false)
      }
    }

    loadMore()
  }, [isFetching, fetchNextPage])

  useEffect(() => {
    window.addEventListener('scroll', handleScroll)
    return () => window.removeEventListener('scroll', handleScroll)
  }, [handleScroll])

  return { isFetching }
}