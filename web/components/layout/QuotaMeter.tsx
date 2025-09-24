/**
 * QuotaMeter component for displaying Twitter API quota usage
 * Shows current usage, remaining quota, and projected exhaustion date
 * Interacts with: useQuota hook, SSE events for real-time updates
 */

import { useEffect, useState } from "react"
import { QuotaStatus } from "@/lib/types"
import { cn } from "@/lib/utils"
import { formatDistanceToNow, format } from "date-fns"
import { AlertCircle, TrendingUp, Calendar } from "lucide-react"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface QuotaMeterProps {
  quota: QuotaStatus
  className?: string
  showDetails?: boolean
}

export function QuotaMeter({ quota, className, showDetails = true }: QuotaMeterProps) {
  const [animatedPercent, setAnimatedPercent] = useState(0)
  
  const used = quota?.used || 0
  const total = quota?.totalAllowed || 10000
  const utilizationPct = (used / total) * 100
  const isWarning = utilizationPct > 80
  const isDanger = utilizationPct > 95
  
  // Animate the progress bar
  useEffect(() => {
    const timer = setTimeout(() => {
      setAnimatedPercent(utilizationPct)
    }, 100)
    return () => clearTimeout(timer)
  }, [utilizationPct])

  // Calculate days until reset
  const daysUntilReset = quota?.periodEnd 
    ? Math.ceil((new Date(quota.periodEnd).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24))
    : 30

  return (
    <div className={cn("space-y-3", className)}>
      {/* Main quota meter */}
      <div
        className={cn(
          "p-4 rounded-lg border transition-colors",
          isDanger && "border-destructive bg-destructive/5",
          isWarning && !isDanger && "border-warning bg-warning/5"
        )}
      >
        {/* Header with usage info */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Twitter API Quota</span>
            {(isWarning || isDanger) && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger>
                    <AlertCircle
                      className={cn(
                        "h-4 w-4",
                        isDanger ? "text-destructive" : "text-warning"
                      )}
                    />
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>
                      {isDanger
                        ? "Critical: Less than 5% quota remaining!"
                        : "Warning: Less than 20% quota remaining"}
                    </p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>
          <span className="text-sm text-muted-foreground">
            {daysUntilReset} {daysUntilReset === 1 ? "day" : "days"} until reset
          </span>
        </div>

        {/* Progress bar */}
        <div className="relative h-3 bg-muted rounded-full overflow-hidden">
          <div
            className={cn(
              "absolute inset-y-0 left-0 transition-all duration-500 ease-out",
              isDanger ? "bg-destructive" : isWarning ? "bg-warning" : "bg-primary"
            )}
            style={{ width: `${animatedPercent}%` }}
          />
          {/* Milestone markers */}
          <div className="absolute inset-0 flex">
            <div className="absolute left-1/2 top-0 bottom-0 w-px bg-border opacity-50" />
            <div className="absolute left-[80%] top-0 bottom-0 w-px bg-warning opacity-50" />
            <div className="absolute left-[95%] top-0 bottom-0 w-px bg-destructive opacity-50" />
          </div>
        </div>

        {/* Usage numbers */}
        <div className="flex items-center justify-between mt-3">
          <span className="text-sm font-mono">
            {used.toLocaleString()} / {total.toLocaleString()} reads
          </span>
          <span
            className={cn(
              "text-sm font-medium",
              isDanger ? "text-destructive" : isWarning ? "text-warning" : "text-muted-foreground"
            )}
          >
            {Math.round(utilizationPct)}% used
          </span>
        </div>

        {/* Projected exhaustion warning */}
        {quota?.projectedExhaustDate && quota?.periodEnd && new Date(quota.projectedExhaustDate) < new Date(quota.periodEnd) && (
          <div className="mt-3 p-2 bg-destructive/10 rounded-md">
            <div className="flex items-center gap-2 text-sm text-destructive">
              <Calendar className="h-4 w-4" />
              <span>
                At current rate, quota will be exhausted{" "}
                {formatDistanceToNow(new Date(quota.projectedExhaustDate), { addSuffix: true })}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Detailed breakdown */}
      {showDetails && quota?.sourceBreakdown && (
        <div className="grid grid-cols-3 gap-3">
          <div className="p-3 rounded-lg border bg-card">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-muted-foreground">Stream API</span>
              <TrendingUp className="h-3 w-3 text-muted-foreground" />
            </div>
            <p className="text-sm font-medium">{(quota.sourceBreakdown?.stream || 0).toLocaleString()}</p>
          </div>
          
          <div className="p-3 rounded-lg border bg-card">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-muted-foreground">Search API</span>
              <TrendingUp className="h-3 w-3 text-muted-foreground" />
            </div>
            <p className="text-sm font-medium">{(quota.sourceBreakdown?.search || 0).toLocaleString()}</p>
          </div>
          
          <div className="p-3 rounded-lg border bg-card">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-muted-foreground">Thread Lookups</span>
              <TrendingUp className="h-3 w-3 text-muted-foreground" />
            </div>
            <p className="text-sm font-medium">{(quota.sourceBreakdown?.threadLookups || 0).toLocaleString()}</p>
          </div>
        </div>
      )}

      {/* Daily average usage */}
      {quota?.avgDailyUsage !== undefined && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>Daily average</span>
          <span className="font-mono">{Math.round(quota.avgDailyUsage || 0).toLocaleString()} reads/day</span>
        </div>
      )}

      {/* Last sync time */}
      {quota?.lastSync && (
        <div className="text-xs text-muted-foreground text-center">
          Last updated {formatDistanceToNow(new Date(quota.lastSync), { addSuffix: true })}
        </div>
      )}
    </div>
  )
}