/**
 * KPICard Component for Analytics Dashboard
 * Displays key performance indicators with optional trends
 * 
 * Connected files:
 * - /web/app/(dashboard)/analytics/page.tsx - Used in analytics dashboard
 */

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ArrowDownIcon, ArrowUpIcon, MinusIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

interface KPICardProps {
  title: string;
  value: string | number;
  description?: string;
  trend?: {
    value: number;
    direction: 'up' | 'down' | 'neutral';
    isPositive: boolean;
  };
  icon?: React.ReactNode;
  loading?: boolean;
}

export function KPICard({ title, value, description, trend, icon, loading }: KPICardProps) {
  if (loading) {
    return (
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">{title}</CardTitle>
          {icon && <div className="h-4 w-4 text-muted-foreground">{icon}</div>}
        </CardHeader>
        <CardContent>
          <div className="h-7 w-24 bg-muted animate-pulse rounded" />
          {description && (
            <div className="h-4 w-32 bg-muted animate-pulse rounded mt-1" />
          )}
        </CardContent>
      </Card>
    );
  }
  
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {icon && <div className="h-4 w-4 text-muted-foreground">{icon}</div>}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {description && (
          <p className="text-xs text-muted-foreground mt-1">{description}</p>
        )}
        {trend && (
          <div className={cn(
            "flex items-center text-xs mt-2",
            trend.isPositive ? "text-green-600" : "text-red-600"
          )}>
            {trend.direction === 'up' && <ArrowUpIcon className="h-3 w-3 mr-1" />}
            {trend.direction === 'down' && <ArrowDownIcon className="h-3 w-3 mr-1" />}
            {trend.direction === 'neutral' && <MinusIcon className="h-3 w-3 mr-1" />}
            <span>{Math.abs(trend.value)}%</span>
            <span className="text-muted-foreground ml-1">vs last period</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}