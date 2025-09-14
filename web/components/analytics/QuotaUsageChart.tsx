/**
 * QuotaUsageChart Component
 * Displays Twitter API quota usage with visual indicators
 * 
 * Connected files:
 * - /web/app/(dashboard)/analytics/page.tsx - Used in analytics dashboard
 * - /web/app/api/analytics/route.ts - Data source
 */

'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { AlertTriangle, TrendingUp, Calendar } from 'lucide-react';
import { format } from 'date-fns';
import { cn } from '@/lib/utils';

interface QuotaUsageData {
  used: number;
  totalAllowed: number;
  remaining: number;
  percentUsed: string;
  dailyAverage: number;
  projectedExhaustDate: string | null;
  sourceBreakdown?: Record<string, number>;
  message?: string;
}

interface QuotaUsageChartProps {
  data: QuotaUsageData | null;
  loading?: boolean;
}

export function QuotaUsageChart({ data, loading }: QuotaUsageChartProps) {
  if (loading || !data) {
    return (
      <Card className="col-span-3">
        <CardHeader>
          <CardTitle>API Quota Usage</CardTitle>
          <CardDescription>Twitter API read budget consumption</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="h-8 w-full bg-muted animate-pulse rounded" />
            <div className="h-20 w-full bg-muted animate-pulse rounded" />
          </div>
        </CardContent>
      </Card>
    );
  }
  
  const percentUsed = parseFloat(data.percentUsed);
  const isWarning = percentUsed > 80;
  const isDanger = percentUsed > 95;
  
  return (
    <Card className="col-span-3">
      <CardHeader>
        <CardTitle>API Quota Usage</CardTitle>
        <CardDescription>Twitter API read budget consumption</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Show message if no API usage */}
        {data.message && data.used === 0 ? (
          <div className="text-center py-8">
            <p className="text-muted-foreground">{data.message}</p>
            <p className="text-sm text-muted-foreground mt-2">
              Quota will be tracked when Twitter API is enabled and used.
            </p>
          </div>
        ) : (
          <>
            {/* Main progress bar */}
            <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span>Used: {data.used.toLocaleString()}</span>
            <span>Limit: {data.totalAllowed.toLocaleString()}</span>
          </div>
          <Progress 
            value={percentUsed} 
            className={cn(
              "h-3",
              isDanger && "[&>div]:bg-red-500",
              isWarning && !isDanger && "[&>div]:bg-yellow-500"
            )}
          />
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">
              {data.remaining.toLocaleString()} remaining
            </span>
            <span className={cn(
              "text-sm font-semibold",
              isDanger && "text-red-500",
              isWarning && !isDanger && "text-yellow-500"
            )}>
              {data.percentUsed}%
            </span>
          </div>
        </div>
        
        {/* Statistics */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <div className="flex items-center text-xs text-muted-foreground">
              <TrendingUp className="h-3 w-3 mr-1" />
              Daily Average
            </div>
            <p className="text-lg font-semibold">
              {data.dailyAverage.toLocaleString()}
            </p>
          </div>
          
          <div className="space-y-1">
            <div className="flex items-center text-xs text-muted-foreground">
              <Calendar className="h-3 w-3 mr-1" />
              Projected Exhaustion
            </div>
            <p className="text-lg font-semibold">
              {data.projectedExhaustDate 
                ? format(new Date(data.projectedExhaustDate), 'MMM dd')
                : 'N/A'
              }
            </p>
          </div>
        </div>
        
        {/* Warning message */}
        {isWarning && (
          <div className={cn(
            "flex items-start space-x-2 p-3 rounded-lg text-sm",
            isDanger ? "bg-red-50 text-red-800" : "bg-yellow-50 text-yellow-800"
          )}>
            <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-semibold">
                {isDanger ? 'Critical quota level!' : 'High quota usage'}
              </p>
              <p className="text-xs mt-1">
                {isDanger 
                  ? 'Consider pausing operations to avoid hitting the limit.'
                  : 'Monitor usage closely to avoid exhausting the quota.'
                }
              </p>
            </div>
          </div>
        )}
        
            {/* Source breakdown if available */}
            {data.sourceBreakdown && Object.keys(data.sourceBreakdown).length > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium">Usage by Endpoint</p>
                <div className="space-y-1">
                  {Object.entries(data.sourceBreakdown).map(([source, count]) => (
                    <div key={source} className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">{source}</span>
                      <span>{count.toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}