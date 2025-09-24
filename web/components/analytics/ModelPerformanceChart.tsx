/**
 * ModelPerformanceChart Component
 * Displays performance metrics for different AI models
 * 
 * Connected files:
 * - /web/app/(dashboard)/analytics/page.tsx - Used in analytics dashboard
 * - /web/app/api/analytics/route.ts - Data source
 */

'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Bar, BarChart, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface ModelPerformanceData {
  model: string;
  total: number;
  approved: number;
  rejected: number;
  pending: number;
  approvalRate: string | number;
}

interface ModelPerformanceChartProps {
  data: ModelPerformanceData[];
  loading?: boolean;
}

export function ModelPerformanceChart({ data, loading }: ModelPerformanceChartProps) {
  if (loading) {
    return (
      <Card className="col-span-3">
        <CardHeader>
          <CardTitle>Model Performance</CardTitle>
          <CardDescription>Approval rates by AI model</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[300px] w-full bg-muted animate-pulse rounded" />
        </CardContent>
      </Card>
    );
  }
  
  if (!data || data.length === 0) {
    return (
      <Card className="col-span-3">
        <CardHeader>
          <CardTitle>Model Performance</CardTitle>
          <CardDescription>Approval rates by AI model</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[300px] w-full flex items-center justify-center text-muted-foreground">
            No model performance data available
          </div>
        </CardContent>
      </Card>
    );
  }
  
  const chartData = data.map(item => {
    const rate = typeof item.approvalRate === 'string' 
      ? parseFloat(item.approvalRate) 
      : (item.approvalRate || 0);
    
    return {
      ...item,
      approvalRate: Number.isNaN(rate) ? 0 : rate,
      total: item.total || 0,
      approved: item.approved || 0,
      rejected: item.rejected || 0,
      pending: item.pending || 0
    };
  });
  
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length > 0 && payload[0]) {
      const data = payload[0].payload;
      if (!data) return null;
      
      return (
        <div className="bg-background border border-border rounded-lg p-3 shadow-lg">
          <p className="font-semibold text-sm mb-2">{label}</p>
          <div className="space-y-1 text-xs">
            <p className="text-green-600">Approved: {data.approved || 0}</p>
            <p className="text-red-600">Rejected: {data.rejected || 0}</p>
            <p className="text-yellow-600">Pending: {data.pending || 0}</p>
            <p className="font-semibold mt-2">
              Approval Rate: {data.approvalRate || 0}%
            </p>
          </div>
        </div>
      );
    }
    return null;
  };
  
  return (
    <Card className="col-span-3">
      <CardHeader>
        <CardTitle>Model Performance</CardTitle>
        <CardDescription>Approval rates by AI model</CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis 
              dataKey="model" 
              className="text-xs"
              tick={{ fill: 'hsl(var(--foreground))' }}
            />
            <YAxis 
              className="text-xs"
              tick={{ fill: 'hsl(var(--foreground))' }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend 
              wrapperStyle={{ paddingTop: '20px' }}
            />
            <Bar 
              dataKey="approved" 
              stackId="a"
              fill="#10b981" 
              name="Approved"
              radius={[0, 0, 0, 0]}
            />
            <Bar 
              dataKey="rejected" 
              stackId="a"
              fill="#ef4444" 
              name="Rejected"
              radius={[0, 0, 0, 0]}
            />
            <Bar 
              dataKey="pending" 
              stackId="a"
              fill="#f59e0b" 
              name="Pending"
              radius={[4, 4, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}