/**
 * PipelineMetricsChart Component
 * Displays pipeline stage performance and success rates
 * 
 * Connected files:
 * - /web/app/(dashboard)/analytics/page.tsx - Used in analytics dashboard
 * - /web/app/api/analytics/route.ts - Data source
 */

'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Bar, BarChart, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

interface PipelineMetricData {
  stage: string;
  total: number;
  completed: number;
  failed: number;
  running: number;
  successRate: string | number;
}

interface PipelineMetricsChartProps {
  data: PipelineMetricData[];
  loading?: boolean;
}

// Stage display names
const stageNames: Record<string, string> = {
  'fewshot': 'Few-shot Generation',
  'scrape': 'Tweet Scraping',
  'classify': 'Classification',
  'deepseek': 'Response Generation',
  'moderation': 'Human Moderation',
  'publish': 'Publishing'
};

// Stage colors based on typical performance
const getStageColor = (successRate: number): string => {
  if (successRate >= 95) return '#10b981'; // green
  if (successRate >= 80) return '#3b82f6'; // blue
  if (successRate >= 60) return '#f59e0b'; // yellow
  return '#ef4444'; // red
};

export function PipelineMetricsChart({ data, loading }: PipelineMetricsChartProps) {
  if (loading) {
    return (
      <Card className="col-span-4">
        <CardHeader>
          <CardTitle>Pipeline Performance</CardTitle>
          <CardDescription>Success rates by pipeline stage</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[300px] w-full bg-muted animate-pulse rounded" />
        </CardContent>
      </Card>
    );
  }
  
  if (!data || data.length === 0) {
    return (
      <Card className="col-span-4">
        <CardHeader>
          <CardTitle>Pipeline Performance</CardTitle>
          <CardDescription>Success rates by pipeline stage</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[300px] w-full flex items-center justify-center text-muted-foreground">
            No pipeline data available
          </div>
        </CardContent>
      </Card>
    );
  }
  
  const chartData = data.map(item => {
    const rate = typeof item.successRate === 'string' 
      ? parseFloat(item.successRate) 
      : (item.successRate || 0);
    
    return {
      ...item,
      stage: stageNames[item.stage] || item.stage,
      successRate: Number.isNaN(rate) ? 0 : rate,
      total: item.total || 0,
      completed: item.completed || 0,
      failed: item.failed || 0,
      running: item.running || 0
    };
  });
  
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length > 0 && payload[0]) {
      const data = payload[0].payload;
      if (!data) return null;
      
      return (
        <div className="bg-background border border-border rounded-lg p-3 shadow-lg">
          <p className="font-semibold text-sm mb-2">{data.stage}</p>
          <div className="space-y-1 text-xs">
            <p>Total Runs: {data.total || 0}</p>
            <p className="text-green-600">Completed: {data.completed || 0}</p>
            <p className="text-red-600">Failed: {data.failed || 0}</p>
            {(data.running || 0) > 0 && (
              <p className="text-blue-600">Running: {data.running}</p>
            )}
            <p className="font-semibold mt-2">
              Success Rate: {data.successRate || 0}%
            </p>
          </div>
        </div>
      );
    }
    return null;
  };
  
  return (
    <Card className="col-span-4">
      <CardHeader>
        <CardTitle>Pipeline Performance</CardTitle>
        <CardDescription>Success rates by pipeline stage</CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData} layout="horizontal">
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis 
              type="number"
              domain={[0, 100]}
              className="text-xs"
              tick={{ fill: 'hsl(var(--foreground))' }}
              tickFormatter={(value) => `${value}%`}
            />
            <YAxis 
              dataKey="stage"
              type="category"
              className="text-xs"
              tick={{ fill: 'hsl(var(--foreground))' }}
              width={120}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar 
              dataKey="successRate" 
              name="Success Rate"
              radius={[0, 4, 4, 0]}
            >
              {chartData.map((entry, index) => (
                <Cell 
                  key={`cell-${index}`} 
                  fill={getStageColor(entry.successRate)} 
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}