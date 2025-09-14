/**
 * Loading state for Analytics page
 * Displayed while the analytics components are being lazy loaded
 * Part of Phase 4 Performance Optimization - Code Splitting
 */

import { Skeleton } from "@/components/ui/skeleton"

export default function AnalyticsLoading() {
  return (
    <div className="space-y-6">
      {/* Header skeleton */}
      <div className="flex items-center justify-between">
        <div>
          <Skeleton className="h-9 w-32 mb-2" />
          <Skeleton className="h-4 w-64" />
        </div>
        <Skeleton className="h-10 w-44" />
      </div>
      
      {/* KPI Cards skeleton */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="border rounded-lg p-6">
            <div className="flex flex-row items-center justify-between space-y-0 pb-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-4" />
            </div>
            <Skeleton className="h-7 w-24 mt-2" />
            <Skeleton className="h-3 w-40 mt-2" />
          </div>
        ))}
      </div>
      
      {/* Charts skeleton */}
      <div className="space-y-4">
        <Skeleton className="h-10 w-80" />
        <div className="grid gap-4 md:grid-cols-7">
          <div className="col-span-4 border rounded-lg p-6">
            <Skeleton className="h-[300px] w-full" />
          </div>
          <div className="col-span-3 border rounded-lg p-6">
            <Skeleton className="h-[300px] w-full" />
          </div>
        </div>
      </div>
    </div>
  )
}