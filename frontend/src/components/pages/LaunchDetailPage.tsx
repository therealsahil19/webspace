'use client'

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import Link from 'next/link'

interface Props {
  slug: string
}

export function LaunchDetailPage({ slug }: Props) {
  const { data: launch, isLoading, error, refetch } = useQuery({
    queryKey: ['launch', slug],
    queryFn: () => apiClient.getLaunch(slug),
  })

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error) {
    return (
      <ErrorMessage 
        message="Failed to load launch details. Please try again later."
        onRetry={() => refetch()}
      />
    )
  }

  if (!launch) {
    return (
      <div className="text-center py-12">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
          Launch Not Found
        </h1>
        <p className="text-gray-600 dark:text-gray-300 mb-6">
          The launch you&apos;re looking for doesn&apos;t exist or has been removed.
        </p>
        <Link
          href="/launches"
          className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-semibold transition-colors"
        >
          Back to Launches
        </Link>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Back Navigation */}
      <Link
        href="/launches"
        className="inline-flex items-center text-blue-600 hover:text-blue-700 font-medium"
      >
        <svg
          className="w-4 h-4 mr-2"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 19l-7-7 7-7"
          />
        </svg>
        Back to Launches
      </Link>

      {/* Header */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-8">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
              {launch.mission_name}
            </h1>
            <div className="flex items-center space-x-4">
              <span
                className={`px-3 py-1 text-sm font-medium rounded-full ${
                  launch.status === 'success'
                    ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                    : launch.status === 'upcoming'
                    ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                    : launch.status === 'failure'
                    ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                    : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                }`}
              >
                {launch.status.charAt(0).toUpperCase() + launch.status.slice(1)}
              </span>
            </div>
          </div>
          
          {launch.mission_patch_url && (
            <div className="flex-shrink-0">
              <img
                src={launch.mission_patch_url}
                alt={`${launch.mission_name} mission patch`}
                className="w-24 h-24 object-contain"
              />
            </div>
          )}
        </div>

        {/* Mission Details Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-4">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              Mission Details
            </h2>
            <div className="space-y-3">
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
          </div>

          {/* Countdown Timer for Upcoming Launches */}
          {launch.status === 'upcoming' && launch.launch_date && (
            <div className="space-y-4">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                Countdown
              </h2>
              <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                <CountdownTimer targetDate={launch.launch_date} />
              </div>
            </div>
          )}
        </div>

        {/* Mission Description */}
        {launch.details && (
          <div className="mt-8">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              Mission Description
            </h2>
            <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
              {launch.details}
            </p>
          </div>
        )}

        {/* External Links */}
        {launch.webcast_url && (
          <div className="mt-8">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              Watch Live
            </h2>
            <a
              href={launch.webcast_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center bg-red-600 hover:bg-red-700 text-white px-6 py-3 rounded-lg font-semibold transition-colors"
            >
              <svg
                className="w-5 h-5 mr-2"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z"
                  clipRule="evenodd"
                />
              </svg>
              Watch on YouTube
            </a>
          </div>
        )}
      </div>
    </div>
  )
}

// Simple countdown timer component
function CountdownTimer({ targetDate }: { targetDate: string }) {
  const [timeLeft, setTimeLeft] = useState<{
    days: number
    hours: number
    minutes: number
    seconds: number
  } | null>(null)

  useEffect(() => {
    const calculateTimeLeft = () => {
      const difference = +new Date(targetDate) - +new Date()
      
      if (difference > 0) {
        return {
          days: Math.floor(difference / (1000 * 60 * 60 * 24)),
          hours: Math.floor((difference / (1000 * 60 * 60)) % 24),
          minutes: Math.floor((difference / 1000 / 60) % 60),
          seconds: Math.floor((difference / 1000) % 60),
        }
      }
      return null
    }

    setTimeLeft(calculateTimeLeft())
    const timer = setInterval(() => {
      setTimeLeft(calculateTimeLeft())
    }, 1000)

    return () => clearInterval(timer)
  }, [targetDate])

  if (!timeLeft) {
    return (
      <div className="text-center text-gray-600 dark:text-gray-300">
        Launch time has passed
      </div>
    )
  }

  return (
    <div className="grid grid-cols-4 gap-4 text-center">
      <div>
        <div className="text-2xl font-bold text-gray-900 dark:text-white">
          {timeLeft.days}
        </div>
        <div className="text-sm text-gray-600 dark:text-gray-300">Days</div>
      </div>
      <div>
        <div className="text-2xl font-bold text-gray-900 dark:text-white">
          {timeLeft.hours}
        </div>
        <div className="text-sm text-gray-600 dark:text-gray-300">Hours</div>
      </div>
      <div>
        <div className="text-2xl font-bold text-gray-900 dark:text-white">
          {timeLeft.minutes}
        </div>
        <div className="text-sm text-gray-600 dark:text-gray-300">Minutes</div>
      </div>
      <div>
        <div className="text-2xl font-bold text-gray-900 dark:text-white">
          {timeLeft.seconds}
        </div>
        <div className="text-sm text-gray-600 dark:text-gray-300">Seconds</div>
      </div>
    </div>
  )
}

import { useState, useEffect } from 'react'