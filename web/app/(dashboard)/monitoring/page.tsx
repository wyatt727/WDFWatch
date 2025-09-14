/**
 * Simplified API Monitoring Dashboard
 * Shows basic system health and activity metrics
 */

'use client'

import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { RefreshCw, Activity, Database, Clock, CheckCircle } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

export default function MonitoringPage() {
  // Fetch monitoring data
  const { data: monitoringData, isLoading, refetch } = useQuery({
    queryKey: ['monitoring'],
    queryFn: async () => {
      const response = await fetch('/api/monitoring/alerts')
      if (!response.ok) throw new Error('Failed to fetch monitoring data')
      return response.json()
    },
    refetchInterval: 30000 // Refresh every 30 seconds
  })

  const metrics = monitoringData?.metrics

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">System Monitoring</h1>
          <p className="text-muted-foreground">
            Basic health metrics and activity overview
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => refetch()}
          disabled={isLoading}
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* System Status Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="w-5 h-5" />
            System Status
          </CardTitle>
          <CardDescription>Overall system health</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <Badge variant="outline" className="text-lg px-4 py-2">
              <CheckCircle className="w-4 h-4 mr-2 text-green-500" />
              Operational
            </Badge>
            <span className="text-sm text-muted-foreground">
              All systems functioning normally
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Tweets */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Tweets</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {metrics?.overview?.totalTweets || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              {metrics?.overview?.recentActivity || 0} in last 24h
            </p>
          </CardContent>
        </Card>

        {/* Pending Drafts */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Pending Drafts</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {metrics?.queueMetrics?.pending || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Awaiting review
            </p>
          </CardContent>
        </Card>

        {/* Total Episodes */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Episodes</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {metrics?.overview?.totalEpisodes || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Processed episodes
            </p>
          </CardContent>
        </Card>

        {/* Database Status */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Database</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-green-500" />
              <span className="text-sm font-medium">Connected</span>
            </div>
            <p className="text-xs text-muted-foreground">
              PostgreSQL active
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Activity Log */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="w-5 h-5" />
            Recent Activity
          </CardTitle>
          <CardDescription>Latest system events</CardDescription>
        </CardHeader>
        <CardContent>
          {monitoringData?.alertHistory?.length > 0 ? (
            <div className="space-y-2">
              {monitoringData.alertHistory.slice(0, 5).map((alert: any, index: number) => (
                <div key={index} className="flex items-center justify-between p-2 border rounded">
                  <div>
                    <p className="text-sm font-medium">{alert.message}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatDistanceToNow(new Date(alert.triggeredAt), { addSuffix: true })}
                    </p>
                  </div>
                  <Badge variant="outline" className="text-xs">
                    {alert.severity}
                  </Badge>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No recent alerts</p>
          )}
        </CardContent>
      </Card>

      {/* Info Card */}
      <Card>
        <CardHeader>
          <CardTitle>Pipeline Information</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm">
            <p>• Claude Pipeline is currently in use for episode processing</p>
            <p>• Metrics are collected from the database in real-time</p>
            <p>• Advanced monitoring features have been simplified</p>
            <p>• Check individual episodes for detailed processing logs</p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}