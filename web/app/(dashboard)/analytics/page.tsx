/**
 * Simplified Analytics Dashboard
 * Shows basic statistics and activity metrics
 */

'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { MessageSquare, CheckCircle, XCircle, Podcast, Clock } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

export default function AnalyticsPage() {
  const [timeRange, setTimeRange] = useState('30');
  
  // Fetch analytics data
  const { data: analytics, isLoading } = useQuery({
    queryKey: ['analytics', timeRange],
    queryFn: () => fetch(`/api/analytics?days=${timeRange}`)
      .then(res => res.json())
  });

  const overview = analytics?.overview || {};
  const recentEpisodes = analytics?.recentEpisodes || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Analytics</h1>
          <p className="text-muted-foreground">
            Basic statistics and metrics overview
          </p>
        </div>
        
        {/* Time range selector */}
        <Select value={timeRange} onValueChange={setTimeRange}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Select time range" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7">Last 7 days</SelectItem>
            <SelectItem value="30">Last 30 days</SelectItem>
            <SelectItem value="90">Last 90 days</SelectItem>
          </SelectContent>
        </Select>
      </div>
      
      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Tweets</CardTitle>
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{overview.totalTweets || 0}</div>
            <p className="text-xs text-muted-foreground">
              {overview.recentTweets || 0} in selected period
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Drafts</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{overview.totalDrafts || 0}</div>
            <p className="text-xs text-muted-foreground">
              {overview.pendingDrafts || 0} pending review
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Approval Rate</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{overview.draftApprovalRate || '0%'}</div>
            <p className="text-xs text-muted-foreground">
              {overview.approvedDrafts || 0} approved, {overview.rejectedDrafts || 0} rejected
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Episodes</CardTitle>
            <Podcast className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{overview.totalEpisodes || 0}</div>
            <p className="text-xs text-muted-foreground">
              Processed episodes
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Draft Status Breakdown */}
      <Card>
        <CardHeader>
          <CardTitle>Draft Status Distribution</CardTitle>
          <CardDescription>Breakdown of draft responses by status</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {Object.entries(analytics?.draftsByStatus || {}).map(([status, count]) => (
              <div key={status} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {status === 'approved' && <CheckCircle className="w-4 h-4 text-green-500" />}
                  {status === 'rejected' && <XCircle className="w-4 h-4 text-red-500" />}
                  {status === 'pending' && <Clock className="w-4 h-4 text-yellow-500" />}
                  <span className="capitalize">{status}</span>
                </div>
                <Badge variant="outline">{count as number}</Badge>
              </div>
            ))}
            {Object.keys(analytics?.draftsByStatus || {}).length === 0 && (
              <p className="text-sm text-muted-foreground">No draft data available</p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Recent Episodes */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Episodes</CardTitle>
          <CardDescription>Latest processed episodes with tweet counts</CardDescription>
        </CardHeader>
        <CardContent>
          {recentEpisodes.length > 0 ? (
            <div className="space-y-2">
              {recentEpisodes.map((episode: any) => (
                <div key={episode.id} className="flex items-center justify-between p-2 border rounded">
                  <div>
                    <p className="font-medium">{episode.title || `Episode ${episode.id}`}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatDistanceToNow(new Date(episode.createdAt), { addSuffix: true })}
                    </p>
                  </div>
                  <div className="text-right">
                    <Badge variant="outline">{episode.tweetCount} tweets</Badge>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No episodes found</p>
          )}
        </CardContent>
      </Card>

      {/* Info Card */}
      <Card>
        <CardHeader>
          <CardTitle>About These Analytics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm text-muted-foreground">
            <p>• These metrics are pulled from the actual database data</p>
            <p>• Claude Pipeline processes episodes and creates drafts</p>
            <p>• Complex charts have been removed in favor of simple, useful metrics</p>
            <p>• For detailed episode processing, check the Episodes tab</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}