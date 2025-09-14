/**
 * React Query hook for monitoring Twitter/X API quota usage
 * Provides real-time updates and projected exhaustion dates
 * Interacts with: /api/quota route, SSE event handler
 */

import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { QuotaStatus } from "@/lib/types"

export function useQuota() {
  const queryClient = useQueryClient()
  const queryKey = ["quota"]

  const { data, error, isLoading, refetch } = useQuery({
    queryKey,
    queryFn: async () => {
      const response = await fetch("/api/quota")
      if (!response.ok) {
        throw new Error("Failed to fetch quota status")
      }
      const data = await response.json()
      // Handle the nested structure from the API
      return data.quota || data
    },
    staleTime: 10 * 60 * 1000, // 10 minutes as per spec
    refetchInterval: 10 * 60 * 1000, // Auto-refresh every 10 minutes
  })

  // Set up SSE for real-time quota updates
  useEffect(() => {
    const eventSource = new EventSource("/api/events")

    eventSource.addEventListener("quota_update", (event) => {
      const update = JSON.parse(event.data)
      // Update quota in cache
      queryClient.setQueryData<QuotaStatus>(queryKey, (old) => {
        if (!old) return old
        return {
          ...old,
          used: update.used,
          projectedExhaustDate: calculateProjectedExhaustDate(
            update.used,
            old.totalAllowed,
            old.avgDailyUsage,
            old.periodEnd
          ),
        }
      })
    })

    return () => {
      eventSource.close()
    }
  }, [queryClient, queryKey])

  const remainingQuota = data ? data.totalAllowed - data.used : 0
  const usagePercentage = data ? (data.used / data.totalAllowed) * 100 : 0
  const isWarning = usagePercentage > 80
  const isDanger = usagePercentage > 95

  return {
    quota: data,
    remainingQuota,
    usagePercentage,
    isWarning,
    isDanger,
    error,
    isLoading,
    refetch,
  }
}

// Helper function to calculate projected exhaustion date
function calculateProjectedExhaustDate(
  used: number,
  total: number,
  avgDaily: number,
  periodEnd: string
): string | undefined {
  if (avgDaily === 0) return undefined
  
  const remaining = total - used
  const daysUntilExhaustion = remaining / avgDaily
  
  const exhaustionDate = new Date()
  exhaustionDate.setDate(exhaustionDate.getDate() + daysUntilExhaustion)
  
  const periodEndDate = new Date(periodEnd)
  
  // If exhaustion is after period end, quota will reset
  if (exhaustionDate > periodEndDate) {
    return undefined
  }
  
  return exhaustionDate.toISOString()
}