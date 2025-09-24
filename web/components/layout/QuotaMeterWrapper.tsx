/**
 * QuotaMeterWrapper component that fetches and provides quota data
 * Wrapper for QuotaMeter that handles data fetching and loading states
 * Interacts with: useQuota hook, QuotaMeter component
 */

"use client"

import { useQuota } from "@/hooks/useQuota"
import { QuotaMeter } from "./QuotaMeter"
import { Skeleton } from "@/components/ui/skeleton"

export function QuotaMeterWrapper() {
  const { quota, isLoading, error } = useQuota()

  if (isLoading) {
    return (
      <div className="w-64">
        <Skeleton className="h-20 w-full" />
      </div>
    )
  }

  if (error || !quota) {
    return (
      <div className="text-sm text-muted-foreground">
        Unable to load quota information
      </div>
    )
  }

  return <QuotaMeter quota={quota} showDetails={false} />
}