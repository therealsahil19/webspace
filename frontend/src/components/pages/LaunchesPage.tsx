'use client'

import { useState, useEffect, useMemo } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { LaunchCard } from '@/components/ui/LaunchCard'
import { SearchAndFilters, FilterOptions } from '@/components/ui/SearchAndFilters'
import { useInfiniteScroll } from '@/hooks/useInfiniteScroll'
import { useLaunchStore } from '@/store/launchStore'

export function LaunchesPage() {
  const { preferences } = useLaunchStore()
  const limit = preferences.itemsPerPage

  const [filters, setFilters] = useState<FilterOptions>({
    search: '',
    status: '',
    vehicleType: '',
    dateRange: { start: '', end: '' },
    sortBy: 'launch_date',
    sortOrder: 'desc'
  })

  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [useInfiniteScrollMode, setUseInfiniteScrollMode] = useState(false)

  // Build query parameters
  const queryParams = useMemo(() => {
    const params: Record<string, any> = {
      limit,
      search: filters.search || undefined,
      status: filters.status || undefined,
      vehicle_type: filters.vehicleType || undefined,
      sort_by: filters.sortBy,
      sort_order: filters.sortOrder,
    }

    if (filters.dateRange.start) {
      params.date_from = filters.dateRange.start
    }
    if (filters.dateRange.end) {
      params.date_to = filters.dateRange.end
    }

    return params
  }, [filters, limit])

  // Infinite query for infinite scroll mode
  const {
    data: infiniteData,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading: isInfiniteLoading,
    error: infiniteError,
    refetch: refetchInfinite
  } = useInfiniteQuery({
    queryKey: ['launches-infinite', queryParams],
    queryFn: ({ pageParam = 1 }) => 
      apiClient.getLaunches({ ...queryParams, page: pageParam }),
    getNextPageParam: (lastPage, pages) => {
      if (!lastPage.total) return undefined
      const totalPages = Math.ceil(lastPage.total / limit)
      return pages.length < totalPages ? pages.length + 1 : undefined
    },
    enabled: useInfiniteScrollMode,
  })

  // Regular paginated query
  const [currentPage, setCurrentPage] = useState(1)
  const {
    data: paginatedData,
    isLoading: isPaginatedLoading,
    error: paginatedError,
    refetch: refetchPaginated
  } = useInfiniteQuery({
    queryKey: ['launches-paginated', queryParams, currentPage],
    queryFn: () => apiClient.getLaunches({ ...queryParams, page: currentPage }),
    getNextPageParam: () => undefined, // Disable infinite behavior
    enabled: !useInfiniteScrollMode,
  })

  // Infinite scroll hook
  const { isFetching } = useInfiniteScroll(
    fetchNextPage,
    {
      hasNextPage: hasNextPage || false,
      isLoading: isFetchingNextPage,
      threshold: 200
    }
  )

  // Reset page when filters change
  useEffect(() => {
    setCurrentPage(1)
  }, [queryParams])

  // Get current data based on mode
  const currentData = useInfiniteScrollMode ? infiniteData : paginatedData
  const isLoading = useInfiniteScrollMode ? isInfiniteLoading : isPaginatedLoading
  const error = useInfiniteScrollMode ? infiniteError : paginatedError
  const refetch = useInfiniteScrollMode ? refetchInfinite : refetchPaginated

  // Flatten data for display
  const launches = useMemo(() => {
    if (!currentData?.pages) return []
    return currentData.pages.flatMap(page => page.data || [])
  }, [currentData])

  // Get unique vehicle types for filter
  const vehicleTypes = useMemo(() => {
    const types = new Set<string>()
    launches.forEach(launch => {
      if (launch.vehicle_type) {
        types.add(launch.vehicle_type)
      }
    })
    return Array.from(types).sort()
  }, [launches])

  // Get total count
  const totalCount = currentData?.pages?.[0]?.total || 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            All Launches
          </h1>
          <p className="text-gray-600 dark:text-gray-300 mt-1">
            {totalCount > 0 && `${totalCount.toLocaleString()} launches found`}
          </p>
        </div>
        
        {/* View Controls */}
        <div className="flex items-center gap-4">
          {/* View Mode Toggle */}
          <div className="flex items-center bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 rounded-md transition-colors ${
                viewMode === 'grid'
                  ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path d="M5 3a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2V5a2 2 0 00-2-2H5zM5 11a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2v-2a2 2 0 00-2-2H5zM11 5a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V5zM11 13a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
              </svg>
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 rounded-md transition-colors ${
                viewMode === 'list'
                  ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
              </svg>
            </button>
          </div>

          {/* Scroll Mode Toggle */}
          <div className="flex items-center">
            <label className="flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={useInfiniteScrollMode}
                onChange={(e) => setUseInfiniteScrollMode(e.target.checked)}
                className="sr-only"
              />
              <div className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                useInfiniteScrollMode ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-700'
              }`}>
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  useInfiniteScrollMode ? 'translate-x-6' : 'translate-x-1'
                }`} />
              </div>
              <span className="ml-2 text-sm text-gray-600 dark:text-gray-300">
                Infinite Scroll
              </span>
            </label>
          </div>
        </div>
      </div>

      {/* Search and Filters */}
      <SearchAndFilters
        filters={filters}
        onFiltersChange={setFilters}
        vehicleTypes={vehicleTypes}
        isLoading={isLoading}
      />

      {/* Loading State */}
      {isLoading && (
        <div className="flex justify-center py-12">
          <LoadingSpinner />
        </div>
      )}

      {/* Error State */}
      {error && (
        <ErrorMessage 
          message="Failed to load launches. Please try again later."
          onRetry={() => refetch()}
        />
      )}

      {/* Results */}
      {launches.length > 0 && (
        <>
          {/* Results Info */}
          <div className="flex justify-between items-center text-sm text-gray-600 dark:text-gray-300">
            <span>
              Showing {launches.length} of {totalCount.toLocaleString()} launches
            </span>
            {useInfiniteScrollMode && hasNextPage && (
              <span className="text-blue-600 dark:text-blue-400">
                Scroll down to load more
              </span>
            )}
          </div>

          {/* Launch Display */}
          {viewMode === 'grid' ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {launches.map((launch) => (
                <LaunchCard key={launch.slug} launch={launch} />
              ))}
            </div>
          ) : (
            <div className="space-y-4">
              {launches.map((launch) => (
                <div key={launch.slug} className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
                  <LaunchCard launch={launch} />
                </div>
              ))}
            </div>
          )}

          {/* Infinite Scroll Loading */}
          {useInfiniteScrollMode && (isFetchingNextPage || isFetching) && (
            <div className="flex justify-center py-8">
              <LoadingSpinner />
            </div>
          )}

          {/* Traditional Pagination */}
          {!useInfiniteScrollMode && totalCount > limit && (
            <div className="flex justify-center items-center space-x-4 mt-8">
              <button
                onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                disabled={currentPage === 1 || isLoading}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Previous
              </button>
              
              <div className="flex items-center space-x-2">
                {/* Page Numbers */}
                {Array.from({ length: Math.min(5, Math.ceil(totalCount / limit)) }, (_, i) => {
                  const pageNum = Math.max(1, currentPage - 2) + i
                  const totalPages = Math.ceil(totalCount / limit)
                  
                  if (pageNum > totalPages) return null
                  
                  return (
                    <button
                      key={pageNum}
                      onClick={() => setCurrentPage(pageNum)}
                      disabled={isLoading}
                      className={`px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
                        pageNum === currentPage
                          ? 'bg-blue-600 text-white'
                          : 'text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700'
                      } disabled:opacity-50 disabled:cursor-not-allowed`}
                    >
                      {pageNum}
                    </button>
                  )
                })}
              </div>
              
              <button
                onClick={() => setCurrentPage(currentPage + 1)}
                disabled={currentPage >= Math.ceil(totalCount / limit) || isLoading}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Next
              </button>
            </div>
          )}

          {/* End of Results for Infinite Scroll */}
          {useInfiniteScrollMode && !hasNextPage && launches.length > 0 && (
            <div className="text-center py-8">
              <p className="text-gray-600 dark:text-gray-300">
                You&apos;ve reached the end of the results
              </p>
            </div>
          )}
        </>
      )}

      {/* Empty State */}
      {!isLoading && launches.length === 0 && (
        <div className="text-center py-12">
          <div className="mx-auto w-24 h-24 bg-gray-100 dark:bg-gray-700 rounded-full flex items-center justify-center mb-4">
            <svg className="w-12 h-12 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            No launches found
          </h3>
          <p className="text-gray-600 dark:text-gray-300 mb-4">
            Try adjusting your search criteria or filters to find more launches.
          </p>
          <button
            onClick={() => setFilters({
              search: '',
              status: '',
              vehicleType: '',
              dateRange: { start: '', end: '' },
              sortBy: 'launch_date',
              sortOrder: 'desc'
            })}
            className="inline-flex items-center px-4 py-2 text-sm font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
          >
            Clear all filters
          </button>
        </div>
      )}
    </div>
  )
}