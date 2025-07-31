'use client'

import { useState, useEffect, useCallback } from 'react'
import { apiClient } from '@/lib/api'

interface DataConflict {
  id: number
  launch_slug: string
  mission_name: string
  field_name: string
  source1_value: string
  source2_value: string
  resolved: boolean
  created_at: string
}

export default function DataConflictsPage() {
  const [conflicts, setConflicts] = useState<DataConflict[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<'all' | 'unresolved' | 'resolved'>('unresolved')
  const [resolvingId, setResolvingId] = useState<number | null>(null)

  useEffect(() => {
    loadConflicts()
  }, [filter, loadConflicts])

  const loadConflicts = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)
      const resolved = filter === 'resolved' ? true : filter === 'unresolved' ? false : undefined
      const response = await apiClient.getDataConflicts({ resolved, limit: 50 })
      setConflicts(response.data)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load conflicts')
    } finally {
      setIsLoading(false)
    }
  }, [filter])

  const resolveConflict = async (conflictId: number, chosenValue: string, notes?: string) => {
    try {
      setResolvingId(conflictId)
      await apiClient.resolveConflict(conflictId, { chosen_value: chosenValue, notes })
      
      // Update the conflict in the local state
      setConflicts(prev => prev.map(conflict => 
        conflict.id === conflictId 
          ? { ...conflict, resolved: true }
          : conflict
      ))
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to resolve conflict')
    } finally {
      setResolvingId(null)
    }
  }

  const getFieldDisplayName = (fieldName: string) => {
    return fieldName.split('_').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ')
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">
          Data Conflicts
        </h1>
        <div className="flex items-center space-x-4">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as typeof filter)}
            className="block w-full pl-3 pr-10 py-2 text-base border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md"
          >
            <option value="unresolved">Unresolved</option>
            <option value="resolved">Resolved</option>
            <option value="all">All</option>
          </select>
          <button
            onClick={loadConflicts}
            className="inline-flex items-center px-3 py-2 border border-gray-300 dark:border-gray-600 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 dark:bg-red-900/20 p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="ml-3">
              <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
            </div>
          </div>
        </div>
      )}

      {conflicts.length === 0 ? (
        <div className="text-center py-12">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">
            No conflicts found
          </h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {filter === 'unresolved' 
              ? 'All data conflicts have been resolved.'
              : filter === 'resolved'
              ? 'No resolved conflicts to display.'
              : 'No data conflicts exist in the system.'
            }
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {conflicts.map((conflict) => (
            <div
              key={conflict.id}
              className="bg-white dark:bg-gray-800 shadow rounded-lg border border-gray-200 dark:border-gray-700"
            >
              <div className="px-6 py-4">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                      {conflict.mission_name}
                    </h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      Field: {getFieldDisplayName(conflict.field_name)} • 
                      Created: {new Date(conflict.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  {conflict.resolved && (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400">
                      Resolved
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Source 1 Value */}
                  <div className="border border-gray-200 dark:border-gray-600 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="text-sm font-medium text-gray-900 dark:text-white">
                        Source 1 Value
                      </h4>
                      {!conflict.resolved && (
                        <button
                          onClick={() => resolveConflict(conflict.id, conflict.source1_value)}
                          disabled={resolvingId === conflict.id}
                          className="inline-flex items-center px-2 py-1 border border-transparent text-xs font-medium rounded text-blue-700 bg-blue-100 hover:bg-blue-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 dark:bg-blue-900/20 dark:text-blue-400 dark:hover:bg-blue-900/40"
                        >
                          {resolvingId === conflict.id ? 'Resolving...' : 'Choose This'}
                        </button>
                      )}
                    </div>
                    <p className="text-sm text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-700 p-2 rounded">
                      {conflict.source1_value || 'No value'}
                    </p>
                  </div>

                  {/* Source 2 Value */}
                  <div className="border border-gray-200 dark:border-gray-600 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="text-sm font-medium text-gray-900 dark:text-white">
                        Source 2 Value
                      </h4>
                      {!conflict.resolved && (
                        <button
                          onClick={() => resolveConflict(conflict.id, conflict.source2_value)}
                          disabled={resolvingId === conflict.id}
                          className="inline-flex items-center px-2 py-1 border border-transparent text-xs font-medium rounded text-blue-700 bg-blue-100 hover:bg-blue-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 dark:bg-blue-900/20 dark:text-blue-400 dark:hover:bg-blue-900/40"
                        >
                          {resolvingId === conflict.id ? 'Resolving...' : 'Choose This'}
                        </button>
                      )}
                    </div>
                    <p className="text-sm text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-700 p-2 rounded">
                      {conflict.source2_value || 'No value'}
                    </p>
                  </div>
                </div>

                {!conflict.resolved && (
                  <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Choose the correct value to resolve this conflict. The selected value will be used for the launch data.
                    </p>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}