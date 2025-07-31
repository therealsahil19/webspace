'use client'

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import Link from 'next/link'

export function UpcomingLaunchesPage() {
  const { data: launches, isLoading, error, refetch } = useQuery({
    queryKey: ['upcomingLaunches'],
    queryFn: () => apiClient.getUpcomingLaunches(),
  })

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
        Upcoming Launches
      </h1>

      {isLoading && (
        <div className="flex justify-center py-12">
          <LoadingSpinner />
        </div>
      )}

      {error && (
        <ErrorMessage 
          message="Failed to load upcoming launches. Please try again later."
          onRetry={() => refetch()}
        />
      )}

      {launches && launches.length > 0 && (
        <div className="space-y-6">
          {launches.map((launch) => (
            <div
              key={launch.slug}
              className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow"
            >
              <div className="flex flex-col lg:flex-row gap-6">
                {/* Mission Patch */}
                {launch.mission_patch_url && (
                  <div className="flex-shrink-0">
                    <img
                      src={launch.mission_patch_url}
                      alt={`${launch.mission_name} mission patch`}
                      className="w-24 h-24 object-contain mx-auto lg:mx-0"
                    />
                  </div>
                )}

                {/* Launch Info */}
                <div className="flex-1">
                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-4">
                    <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
                      {launch.mission_name}
                    </h2>
                    <span className="px-3 py-1 text-sm font-medium rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                      Upcoming
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    {launch.launch_date && (
                      <div>
                        <span className="font-medium text-gray-700 dark:text-gray-300">
                          Launch Date:
                        </span>
                        <p className="text-gray-900 dark:text-white">
                          {new Date(launch.launch_date).toLocaleString()}
                        </p>
                      </div>
                    )}
                    {launch.vehicle_type && (
                      <div>
                        <span className="font-medium text-gray-700 dark:text-gray-300">
                          Vehicle:
                        </span>
                        <p className="text-gray-900 dark:text-white">{launch.vehicle_type}</p>
                      </div>
                    )}
                    {launch.orbit && (
                      <div>
                        <span className="font-medium text-gray-700 dark:text-gray-300">
                          Target Orbit:
                        </span>
                        <p className="text-gray-900 dark:text-white">{launch.orbit}</p>
                      </div>
                    )}
                    {launch.payload_mass && (
                      <div>
                        <span className="font-medium text-gray-700 dark:text-gray-300">
                          Payload Mass:
                        </span>
                        <p className="text-gray-900 dark:text-white">
                          {launch.payload_mass.toLocaleString()} kg
                        </p>
                      </div>
                    )}
                  </div>

                  {launch.details && (
                    <p className="text-gray-700 dark:text-gray-300 mb-4 line-clamp-3">
                      {launch.details}
                    </p>
                  )}

                  <div className="flex flex-col sm:flex-row gap-3">
                    <Link
                      href={`/launches/${launch.slug}`}
                      className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg font-semibold transition-colors text-center"
                    >
                      View Details
                    </Link>
                    {launch.webcast_url && (
                      <a
                        href={launch.webcast_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="border border-red-600 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 px-6 py-2 rounded-lg font-semibold transition-colors text-center"
                      >
                        Watch Live
                      </a>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {launches && launches.length === 0 && (
        <div className="text-center py-12">
          <div className="text-6xl mb-4">🚀</div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
            No Upcoming Launches
          </h2>
          <p className="text-gray-600 dark:text-gray-300 mb-6">
            There are no upcoming SpaceX launches scheduled at this time.
          </p>
          <Link
            href="/launches"
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-semibold transition-colors"
          >
            View All Launches
          </Link>
        </div>
      )}
    </div>
  )
}