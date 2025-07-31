'use client'

import React from 'react'
import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { ErrorMessage, getErrorType } from '@/components/ui/ErrorMessage'
import { useOfflineData } from '@/hooks/useOfflineData'
import { OfflineDataBanner } from '@/components/ui/OfflineDataBanner'
import { LaunchListSkeleton, StatCardSkeleton } from '@/components/ui/SkeletonLoader'
import { ApiErrorBoundary } from '@/components/ui/ApiErrorBoundary'

export function HomePage() {
  const { 
    data: upcomingLaunches, 
    isLoading, 
    error,
    refetch 
  } = useQuery({
    queryKey: ['upcomingLaunches'],
    queryFn: () => apiClient.getUpcomingLaunches(),
  })

  const {
    cachedData: cachedLaunches,
    isStale,
    isOnline,
    cacheAgeString,
    saveToCache,
  } = useOfflineData<typeof upcomingLaunches>('upcoming-launches')

  // Save successful data to cache
  React.useEffect(() => {
    if (upcomingLaunches && !error) {
      saveToCache(upcomingLaunches)
    }
  }, [upcomingLaunches, error, saveToCache])

  // Use cached data when offline or when there's an error
  const displayData = upcomingLaunches || cachedLaunches
  const shouldShowOfflineBanner = !isOnline || (isStale && !upcomingLaunches)

  const handleRetry = () => {
    refetch()
  }

  return (
    <div className="space-y-12">
      {/* Hero Section */}
      <section className="text-center py-12">
        <h1 className="text-4xl md:text-6xl font-bold text-gray-900 dark:text-white mb-6">
          SpaceX Launch Tracker
        </h1>
        <p className="text-xl text-gray-600 dark:text-gray-300 mb-8 max-w-3xl mx-auto">
          Stay up-to-date with the latest SpaceX launches, mission details, and real-time countdown timers.
          Track upcoming missions and explore the history of space exploration.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            href="/launches"
            className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-3 rounded-lg font-semibold transition-colors"
          >
            View All Launches
          </Link>
          <Link
            href="/launches/upcoming"
            className="border border-blue-600 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 px-8 py-3 rounded-lg font-semibold transition-colors"
          >
            Upcoming Launches
          </Link>
        </div>
      </section>

      {/* Featured Upcoming Launches */}
      <section>
        <div className="flex justify-between items-center mb-8">
          <h2 className="text-3xl font-bold text-gray-900 dark:text-white">
            Next Launches
          </h2>
          <Link
            href="/launches/upcoming"
            className="text-blue-600 hover:text-blue-700 font-medium"
          >
            View all →
          </Link>
        </div>

        {shouldShowOfflineBanner && (
          <OfflineDataBanner
            isOnline={isOnline}
            isStale={isStale}
            cacheAgeString={cacheAgeString}
            onRefresh={handleRetry}
          />
        )}

        <ApiErrorBoundary onRetry={handleRetry}>
          {isLoading && !displayData && (
            <LaunchListSkeleton count={3} />
          )}

          {error && !displayData && (
            <ErrorMessage 
              type={getErrorType(error)}
              message="Failed to load upcoming launches. Please try again later."
              onRetry={handleRetry}
            />
          )}

          {displayData && displayData.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {displayData.slice(0, 3).map((launch) => (
                <div
                  key={launch.slug}
                  className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow"
                >
                  <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                    {launch.mission_name}
                  </h3>
                  <div className="space-y-2 text-sm text-gray-600 dark:text-gray-300">
                    {launch.launch_date && (
                      <p>
                        <span className="font-medium">Launch Date:</span>{' '}
                        {new Date(launch.launch_date).toLocaleDateString()}
                      </p>
                    )}
                    {launch.vehicle_type && (
                      <p>
                        <span className="font-medium">Vehicle:</span> {launch.vehicle_type}
                      </p>
                    )}
                    {launch.orbit && (
                      <p>
                        <span className="font-medium">Orbit:</span> {launch.orbit}
                      </p>
                    )}
                  </div>
                  <Link
                    href={`/launches/${launch.slug}`}
                    className="inline-block mt-4 text-blue-600 hover:text-blue-700 font-medium"
                  >
                    View Details →
                  </Link>
                </div>
              ))}
            </div>
          )}

          {displayData && displayData.length === 0 && (
            <div className="text-center py-12">
              <p className="text-gray-600 dark:text-gray-300">
                No upcoming launches scheduled at this time.
              </p>
            </div>
          )}
        </ApiErrorBoundary>
      </section>

      {/* Stats Section */}
      <section className="bg-white dark:bg-gray-800 rounded-lg p-8">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6 text-center">
          Mission Statistics
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 text-center">
          <div>
            <div className="text-3xl font-bold text-blue-600 mb-2">200+</div>
            <div className="text-gray-600 dark:text-gray-300">Total Launches</div>
          </div>
          <div>
            <div className="text-3xl font-bold text-green-600 mb-2">95%</div>
            <div className="text-gray-600 dark:text-gray-300">Success Rate</div>
          </div>
          <div>
            <div className="text-3xl font-bold text-purple-600 mb-2">150+</div>
            <div className="text-gray-600 dark:text-gray-300">Successful Landings</div>
          </div>
        </div>
      </section>
    </div>
  )
}