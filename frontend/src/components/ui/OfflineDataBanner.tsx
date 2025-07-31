'use client'

interface OfflineDataBannerProps {
  isOnline: boolean
  isStale: boolean
  cacheAgeString: string | null
  onRefresh?: () => void
}

export function OfflineDataBanner({
  isOnline,
  isStale,
  cacheAgeString,
  onRefresh,
}: OfflineDataBannerProps) {
  if (isOnline && !isStale) {
    return null
  }

  const getBannerContent = () => {
    if (!isOnline) {
      return {
        icon: (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M18.364 5.636l-3.536 3.536m0 5.656l3.536 3.536M9.172 9.172L5.636 5.636m3.536 9.192L5.636 18.364M12 2.25a9.75 9.75 0 109.75 9.75A9.75 9.75 0 0012 2.25z"
            />
          </svg>
        ),
        message: `You're offline. Showing cached data${cacheAgeString ? ` from ${cacheAgeString}` : ''}.`,
        bgColor: 'bg-orange-50 dark:bg-orange-900/20',
        borderColor: 'border-orange-200 dark:border-orange-800',
        textColor: 'text-orange-800 dark:text-orange-200',
        iconColor: 'text-orange-400',
      }
    }

    if (isStale) {
      return {
        icon: (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
            />
          </svg>
        ),
        message: `Data may be outdated${cacheAgeString ? ` (last updated ${cacheAgeString})` : ''}.`,
        bgColor: 'bg-yellow-50 dark:bg-yellow-900/20',
        borderColor: 'border-yellow-200 dark:border-yellow-800',
        textColor: 'text-yellow-800 dark:text-yellow-200',
        iconColor: 'text-yellow-400',
      }
    }

    return null
  }

  const bannerContent = getBannerContent()
  if (!bannerContent) return null

  return (
    <div className={`${bannerContent.bgColor} ${bannerContent.borderColor} border rounded-lg p-3 mb-4`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center">
          <div className={`flex-shrink-0 ${bannerContent.iconColor}`}>
            {bannerContent.icon}
          </div>
          <div className="ml-3">
            <p className={`text-sm ${bannerContent.textColor}`}>
              {bannerContent.message}
            </p>
          </div>
        </div>
        {onRefresh && isOnline && (
          <button
            onClick={onRefresh}
            className={`text-sm ${bannerContent.textColor} hover:opacity-75 font-medium ml-4`}
          >
            Refresh
          </button>
        )}
      </div>
    </div>
  )
}