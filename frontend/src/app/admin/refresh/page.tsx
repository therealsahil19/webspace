'use client'

import { useState } from 'react'
import { apiClient } from '@/lib/api'

export default function ManualRefreshPage() {
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [lastRefresh, setLastRefresh] = useState<{
    timestamp: Date
    taskId: string
    success: boolean
    message: string
  } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const triggerRefresh = async () => {
    try {
      setIsRefreshing(true)
      setError(null)
      
      const response = await apiClient.triggerManualRefresh()
      
      setLastRefresh({
        timestamp: new Date(),
        taskId: response.task_id,
        success: true,
        message: response.message
      })
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to trigger refresh'
      setError(errorMessage)
      setLastRefresh({
        timestamp: new Date(),
        taskId: '',
        success: false,
        message: errorMessage
      })
    } finally {
      setIsRefreshing(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">
          Manual Data Refresh
        </h1>
        <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
          Trigger an immediate refresh of launch data from all configured sources.
        </p>
      </div>

      {/* Refresh Card */}
      <div className="bg-white dark:bg-gray-800 shadow rounded-lg">
        <div className="px-6 py-8">
          <div className="text-center">
            <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-blue-100 dark:bg-blue-900/20">
              <svg
                className="h-8 w-8 text-blue-600 dark:text-blue-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
            </div>
            <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">
              Refresh Launch Data
            </h3>
            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
              This will immediately start a scraping task to collect the latest launch information 
              from SpaceX, NASA, Wikipedia, and other configured sources.
            </p>
            
            <div className="mt-6">
              <button
                onClick={triggerRefresh}
                disabled={isRefreshing}
                className="inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed dark:bg-blue-700 dark:hover:bg-blue-600"
              >
                {isRefreshing ? (
                  <>
                    <svg
                      className="animate-spin -ml-1 mr-3 h-5 w-5 text-white"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    Refreshing Data...
                  </>
                ) : (
                  <>
                    <svg
                      className="w-5 h-5 mr-2"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                      />
                    </svg>
                    Start Refresh
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Status Messages */}
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
              <h3 className="text-sm font-medium text-red-800 dark:text-red-200">
                Refresh Failed
              </h3>
              <p className="mt-1 text-sm text-red-700 dark:text-red-300">{error}</p>
            </div>
          </div>
        </div>
      )}

      {lastRefresh && lastRefresh.success && (
        <div className="rounded-md bg-green-50 dark:bg-green-900/20 p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-green-400" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-green-800 dark:text-green-200">
                Refresh Started Successfully
              </h3>
              <div className="mt-1 text-sm text-green-700 dark:text-green-300">
                <p>{lastRefresh.message}</p>
                <p className="mt-1">
                  Task ID: <code className="font-mono text-xs">{lastRefresh.taskId}</code>
                </p>
                <p className="mt-1">
                  Started at: {lastRefresh.timestamp.toLocaleString()}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Information Card */}
      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-6">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg
              className="h-5 w-5 text-blue-400"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                clipRule="evenodd"
              />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-blue-800 dark:text-blue-200">
              About Manual Refresh
            </h3>
            <div className="mt-2 text-sm text-blue-700 dark:text-blue-300">
              <ul className="list-disc list-inside space-y-1">
                <li>The refresh process runs in the background and may take several minutes to complete</li>
                <li>Data is collected from multiple sources including SpaceX website, NASA, and Wikipedia</li>
                <li>The system will automatically handle rate limiting and retry failed requests</li>
                <li>You can monitor the progress in the System Logs section</li>
                <li>Automatic refreshes continue to run on schedule regardless of manual triggers</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="bg-white dark:bg-gray-800 shadow rounded-lg">
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-medium text-gray-900 dark:text-white">
            Refresh History
          </h3>
        </div>
        <div className="px-6 py-4">
          {lastRefresh ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between py-2">
                <div className="flex items-center">
                  <div className={`flex-shrink-0 w-2 h-2 rounded-full ${
                    lastRefresh.success ? 'bg-green-400' : 'bg-red-400'
                  }`}></div>
                  <div className="ml-3">
                    <p className="text-sm font-medium text-gray-900 dark:text-white">
                      Manual Refresh
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {lastRefresh.timestamp.toLocaleString()}
                    </p>
                  </div>
                </div>
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  lastRefresh.success 
                    ? 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400'
                    : 'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400'
                }`}>
                  {lastRefresh.success ? 'Started' : 'Failed'}
                </span>
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-4">
              No manual refreshes have been triggered yet.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}