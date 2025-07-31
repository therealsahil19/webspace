interface SkeletonProps {
  className?: string
  width?: string | number
  height?: string | number
  rounded?: boolean
}

export function Skeleton({ className = '', width, height, rounded = false }: SkeletonProps) {
  const style: React.CSSProperties = {}
  if (width) style.width = typeof width === 'number' ? `${width}px` : width
  if (height) style.height = typeof height === 'number' ? `${height}px` : height

  return (
    <div
      className={`animate-pulse bg-gray-200 dark:bg-gray-700 ${
        rounded ? 'rounded-full' : 'rounded'
      } ${className}`}
      style={style}
    />
  )
}

export function LaunchCardSkeleton() {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
      <div className="space-y-4">
        {/* Mission name */}
        <Skeleton height={24} className="w-3/4" />
        
        {/* Launch details */}
        <div className="space-y-2">
          <Skeleton height={16} className="w-1/2" />
          <Skeleton height={16} className="w-2/3" />
          <Skeleton height={16} className="w-1/3" />
        </div>
        
        {/* Action button */}
        <div className="pt-2">
          <Skeleton height={20} className="w-24" />
        </div>
      </div>
    </div>
  )
}

export function LaunchDetailSkeleton() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="space-y-4">
        <Skeleton height={40} className="w-3/4" />
        <Skeleton height={20} className="w-1/2" />
      </div>
      
      {/* Mission patch */}
      <div className="flex justify-center">
        <Skeleton width={200} height={200} rounded />
      </div>
      
      {/* Details grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-4">
          <Skeleton height={24} className="w-1/3" />
          <div className="space-y-2">
            <Skeleton height={16} />
            <Skeleton height={16} />
            <Skeleton height={16} className="w-3/4" />
          </div>
        </div>
        <div className="space-y-4">
          <Skeleton height={24} className="w-1/3" />
          <div className="space-y-2">
            <Skeleton height={16} />
            <Skeleton height={16} className="w-2/3" />
            <Skeleton height={16} />
          </div>
        </div>
      </div>
      
      {/* Description */}
      <div className="space-y-4">
        <Skeleton height={24} className="w-1/4" />
        <div className="space-y-2">
          <Skeleton height={16} />
          <Skeleton height={16} />
          <Skeleton height={16} className="w-4/5" />
        </div>
      </div>
    </div>
  )
}

export function LaunchListSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {Array.from({ length: count }, (_, i) => (
        <LaunchCardSkeleton key={i} />
      ))}
    </div>
  )
}

export function TableSkeleton({ rows = 5, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <div className="space-y-4">
      {/* Table header */}
      <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}>
        {Array.from({ length: columns }, (_, i) => (
          <Skeleton key={i} height={20} className="w-3/4" />
        ))}
      </div>
      
      {/* Table rows */}
      {Array.from({ length: rows }, (_, rowIndex) => (
        <div key={rowIndex} className="grid gap-4" style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}>
          {Array.from({ length: columns }, (_, colIndex) => (
            <Skeleton key={colIndex} height={16} className={colIndex === 0 ? 'w-full' : 'w-2/3'} />
          ))}
        </div>
      ))}
    </div>
  )
}

export function StatCardSkeleton() {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg p-6 text-center">
      <Skeleton height={32} className="w-16 mx-auto mb-2" />
      <Skeleton height={16} className="w-24 mx-auto" />
    </div>
  )
}

export function SearchBarSkeleton() {
  return (
    <div className="flex flex-col sm:flex-row gap-4 mb-6">
      <Skeleton height={40} className="flex-1" />
      <Skeleton height={40} className="w-32" />
      <Skeleton height={40} className="w-24" />
    </div>
  )
}