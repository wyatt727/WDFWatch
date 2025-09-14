/**
 * ApprovalTrendChart Component
 * Displays daily approval/rejection trends over time
 * 
 * Connected files:
 * - /web/app/(dashboard)/analytics/page.tsx - Used in analytics dashboard
 * - /web/app/api/analytics/route.ts - Data source
 */

'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Line, LineChart, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { format } from 'date-fns';

interface ApprovalTrendData {
  date: string;
  approved: number;
  rejected: number;
  total: number;
  approvalRate: string | number;
}

interface ApprovalTrendChartProps {
  data: ApprovalTrendData[];
  loading?: boolean;
}

export function ApprovalTrendChart({ data, loading }: ApprovalTrendChartProps) {
  if (loading) {
    return (
      <Card className="col-span-4">
        <CardHeader>
          <CardTitle>Approval Trends</CardTitle>
          <CardDescription>Daily approval and rejection rates</CardDescription>
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
          <CardTitle>Approval Trends</CardTitle>
          <CardDescription>Daily approval and rejection rates</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[300px] w-full flex items-center justify-center text-muted-foreground">
            No data available for the selected period
          </div>
        </CardContent>
      </Card>
    );
  }
  
  // Format data for the chart and ensure all values are valid numbers
  const chartData = data.map(item => {
    const rate = typeof item.approvalRate === 'string' 
      ? parseFloat(item.approvalRate) 
      : (item.approvalRate || 0);
    
    return {
      ...item,
      date: format(new Date(item.date), 'MMM dd'),
      approvalRate: Number.isNaN(rate) ? 0 : rate,
      approved: item.approved || 0,
      rejected: item.rejected || 0,
      total: item.total || 0
    };
  });
  
  return (
    <Card className="col-span-4">
      <CardHeader>
        <CardTitle>Approval Trends</CardTitle>
        <CardDescription>Daily approval and rejection rates</CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis 
              dataKey="date" 
              className="text-xs"
              tick={{ fill: 'hsl(var(--foreground))' }}
            />
            <YAxis 
              className="text-xs"
              tick={{ fill: 'hsl(var(--foreground))' }}
            />
            <YAxis 
              yAxisId="right" 
              orientation="right"
              className="text-xs"
              tick={{ fill: 'hsl(var(--foreground))' }}
              domain={[0, 100]}
            />
            <Tooltip 
              contentStyle={{
                backgroundColor: 'hsl(var(--background))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '6px'
              }}
              labelStyle={{ color: 'hsl(var(--foreground))' }}
            />
            <Legend 
              wrapperStyle={{ paddingTop: '20px' }}
              iconType="line"
            />
            <Line 
              type="monotone" 
              dataKey="approved" 
              stroke="#10b981" 
              strokeWidth={2}
              dot={{ fill: '#10b981', r: 4 }}
              activeDot={{ r: 6 }}
              name="Approved"
            />
            <Line 
              type="monotone" 
              dataKey="rejected" 
              stroke="#ef4444" 
              strokeWidth={2}
              dot={{ fill: '#ef4444', r: 4 }}
              activeDot={{ r: 6 }}
              name="Rejected"
            />
            <Line 
              type="monotone" 
              dataKey="approvalRate" 
              stroke="#6366f1" 
              strokeWidth={2}
              strokeDasharray="5 5"
              dot={{ fill: '#6366f1', r: 4 }}
              activeDot={{ r: 6 }}
              name="Approval Rate %"
              yAxisId="right"
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}