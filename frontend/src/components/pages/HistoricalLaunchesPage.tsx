'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { useLaunchStore } from '@/store/launchStore'
import Link from 'next/link'

export function HistoricalLaunchesPage() {
  const [page, setPage] = useState(1)
  const { preferences } = useLaunchStore()
  const limit = preferences.itemsPerPage

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['historicalLaunches', page, limit],
    queryFn: () => apiClient.getHistoricalLaunches({ page, limit }),
  })

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
        Historical Launches
      </h1>

      {isLoading && (
        <div className="flex justify-center py-12">
          <LoadingSpinner />
        </div>
      )}

      {error && (
        <ErrorMessage 
          message="Failed to load historical launches. Please try again later."
          onRetry={() => refetch()}
        />
      )}

      {data && (
        <>
          {/* Results Info */}
          <div className="text-sm text-gray-600 dark:text-gray-300">
            Showing {data.data.length} of {data.total} historical launches
          </div>

          {/* Launch Timeline */}
          <div className="space-y-6">
            {data.data.map((launch, index) => (
              <div
                key={launch.slug}
                className="relative bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow"
              >
                {/* Timeline connector */}
                {index < data.data.length - 1 && (
                  <div className="absolute left-8 top-full w-0.5 h-6 bg-gray-300 dark:bg-gray-600 z-10" />
                )}

                <div className="flex gap-6">
                  {/* Timeline dot */}
                  <div className="flex-shrink-0 pt-1">
                    <div
                      className={`w-4 h-4 rounded-full border-2 ${
                        launch.status === 'success'
                          ? 'bg-green-500 border-green-500'
                          : launch.status === 'failure'
                          ? 'bg-red-500 border-red-500'
                          : 'bg-gray-400 border-gray-400'
                      }`}
                    />
                  </div>

                  {/* Launch content */}
                  <div className="flex-1">
                    <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4 mb-4">
                      <div>
                        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-1">
                          {launch.mission_name}
                        </h2>
                        {launch.launch_date && (
                          <p className="text-sm text-gray-600 dark:text-gray-300">
                            {new Date(launch.launch_date).toLocaleDateString('en-US', {
                              year: 'numeric',
                              month: 'long',
                              day: 'numeric',
                            })}
                          </p>
                        )}
                      </div>
                      
                      <div className="flex items-center gap-3">
                        <span
                          className={`px-3 py-1 text-sm font-medium rounded-full ${
                            launch.status === 'success'
                              ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                              : launch.status === 'failure'
                              ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                              : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                          }`}
                        >
                          {launch.status === 'success' ? 'Success' : 
                           launch.status === 'failure' ? 'Failure' : 
                           launch.status.charAt(0).toUpperCase() + launch.status.slice(1)}
                        </span>
                        
                        {launch.mission_patch_url && (
                          <img
                            src={launch.mission_patch_url}
                            alt={`${launch.mission_name} mission patch`}
                            className="w-12 h-12 object-contain"
                          />
                        )}
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4 text-sm">
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
                            Orbit:
                          </span>
                          <p className="text-gray-900 dark:text-white">{launch.orbit}</p>
                        </div>
                      )}
                      {launch.payload_mass && (
                        <div>
                          <span className="font-medium text-gray-700 dark:text-gray-300">
                            Payload:
                          </span>
                          <p className="text-gray-900 dark:text-white">
                            {launch.payload_mass.toLocaleString()} kg
                          </p>
                        </div>
                      )}
                    </div>

                    {launch.details && (
                      <p className="text-gray-700 dark:text-gray-300 mb-4 line-clamp-2">
                        {launch.details}
                      </p>
                    )}

                    <Link
                      href={`/launches/${launch.slug}`}
                      className="inline-flex items-center text-blue-600 hover:text-blue-700 font-medium text-sm"
                    >
                      View Details
                      <svg
                        className="w-4 h-4 ml-1"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M9 5l7 7-7 7"
                        />
                      </svg>
                    </Link>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {data.total && data.total > limit && (
            <div className="flex justify-center items-center space-x-4 mt-8">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              
              <span className="text-sm text-gray-600 dark:text-gray-300">
                Page {page} of {Math.ceil(data.total / limit)}
              </span>
              
              <button
                onClick={() => setPage(page + 1)}
                disabled={page >= Math.ceil(data.total / limit)}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}

      {data && data.data.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-600 dark:text-gray-300">
            No historical launches found.
          </p>
        </div>
      )}
    </div>
  )
}