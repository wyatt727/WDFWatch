/**
 * Twitter API Quota Monitor Component
 * 
 * Displays real-time Twitter API quota usage and health status.
 * Integrates with: quota_manager.py, /api/twitter/quota endpoint
 */

'use client'

import React, { useEffect, useState } from 'react'
import { AlertCircle, CheckCircle, XCircle, TrendingUp, Clock } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'

interface QuotaStats {
  monthly_limit: number
  monthly_usage: number
  monthly_remaining: number
  monthly_percentage: number
  daily_usage: number
  daily_average: number
  projected_monthly: number
  days_until_exhausted: number
  exhaustion_date?: string
  days_remaining_in_month: number
  recommended_daily_limit: number
  health: 'healthy' | 'warning' | 'critical'
}

interface TwitterQuotaMonitorProps {
  refreshInterval?: number // Refresh interval in milliseconds
  onQuotaExhausted?: () => void
}

export function TwitterQuotaMonitor({ 
  refreshInterval = 30000, // Default 30 seconds
  onQuotaExhausted 
}: TwitterQuotaMonitorProps) {
  const [quotaStats, setQuotaStats] = useState<QuotaStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchQuotaStats = async () => {
    try {
      const response = await fetch('/api/twitter/quota')
      if (!response.ok) {
        throw new Error('Failed to fetch quota stats')
      }
      const data = await response.json()
      setQuotaStats(data)
      setError(null)

      // Notify if quota is exhausted
      if (data.monthly_remaining <= 0 && onQuotaExhausted) {
        onQuotaExhausted()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchQuotaStats()
    const interval = setInterval(fetchQuotaStats, refreshInterval)
    return () => clearInterval(interval)
  }, [refreshInterval])

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-64 mt-2" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-32 w-full" />
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <XCircle className="h-4 w-4" />
        <AlertTitle>Error Loading Quota</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    )
  }

  if (!quotaStats) {
    return null
  }

  const getHealthColor = (health: string) => {
    switch (health) {
      case 'healthy':
        return 'text-green-600'
      case 'warning':
        return 'text-yellow-600'
      case 'critical':
        return 'text-red-600'
      default:
        return 'text-gray-600'
    }
  }

  const getHealthIcon = (health: string) => {
    switch (health) {
      case 'healthy':
        return <CheckCircle className="h-4 w-4" />
      case 'warning':
        return <AlertCircle className="h-4 w-4" />
      case 'critical':
        return <XCircle className="h-4 w-4" />
      default:
        return null
    }
  }

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat().format(Math.round(num))
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric',
      year: 'numeric'
    })
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Twitter API Quota</CardTitle>
            <CardDescription>
              Monthly read limit tracking and projections
            </CardDescription>
          </div>
          <Badge 
            variant={quotaStats.health === 'healthy' ? 'default' : 
                    quotaStats.health === 'warning' ? 'secondary' : 'destructive'}
            className="flex items-center gap-1"
          >
            {getHealthIcon(quotaStats.health)}
            {quotaStats.health.toUpperCase()}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Main Progress Bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>Monthly Usage</span>
            <span className={getHealthColor(quotaStats.health)}>
              {formatNumber(quotaStats.monthly_usage)} / {formatNumber(quotaStats.monthly_limit)}
            </span>
          </div>
          <Progress 
            value={quotaStats.monthly_percentage} 
            className="h-3"
          />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>{quotaStats.monthly_percentage.toFixed(1)}% used</span>
            <span>{formatNumber(quotaStats.monthly_remaining)} remaining</span>
          </div>
        </div>

        {/* Daily Stats */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <p className="text-sm font-medium">Today's Usage</p>
            <p className="text-2xl font-bold">{formatNumber(quotaStats.daily_usage)}</p>
            <p className="text-xs text-muted-foreground">
              Avg: {formatNumber(quotaStats.daily_average)}/day
            </p>
          </div>
          <div className="space-y-1">
            <p className="text-sm font-medium">Recommended Daily</p>
            <p className="text-2xl font-bold">{formatNumber(quotaStats.recommended_daily_limit)}</p>
            <p className="text-xs text-muted-foreground">
              {quotaStats.days_remaining_in_month} days left
            </p>
          </div>
        </div>

        {/* Projections */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm font-medium">
            <TrendingUp className="h-4 w-4" />
            Projections
          </div>
          <div className="pl-6 space-y-1 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Monthly projection:</span>
              <span className={quotaStats.projected_monthly > quotaStats.monthly_limit ? 'text-red-600' : ''}>
                {formatNumber(quotaStats.projected_monthly)}
              </span>
            </div>
            {quotaStats.exhaustion_date && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Exhaustion date:</span>
                <span className={quotaStats.days_until_exhausted < 7 ? 'text-red-600' : ''}>
                  {formatDate(quotaStats.exhaustion_date)}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Warnings */}
        {quotaStats.health === 'warning' && (
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Quota Warning</AlertTitle>
            <AlertDescription>
              You've used {quotaStats.monthly_percentage.toFixed(0)}% of your monthly quota. 
              Consider reducing search frequency to avoid exhaustion.
            </AlertDescription>
          </Alert>
        )}

        {quotaStats.health === 'critical' && (
          <Alert variant="destructive">
            <XCircle className="h-4 w-4" />
            <AlertTitle>Critical Quota Level</AlertTitle>
            <AlertDescription>
              Only {formatNumber(quotaStats.monthly_remaining)} API calls remaining! 
              Searches will be restricted to preserve quota.
            </AlertDescription>
          </Alert>
        )}

        {quotaStats.days_until_exhausted < 7 && quotaStats.days_until_exhausted > 0 && (
          <Alert>
            <Clock className="h-4 w-4" />
            <AlertTitle>Quota Exhaustion Warning</AlertTitle>
            <AlertDescription>
              At current usage rate, quota will be exhausted in {Math.round(quotaStats.days_until_exhausted)} days.
              Reduce daily usage to {formatNumber(quotaStats.recommended_daily_limit)} calls.
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  )
}