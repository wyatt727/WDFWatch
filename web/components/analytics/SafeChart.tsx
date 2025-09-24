/**
 * SafeChart Wrapper Component
 * Wraps chart components with error boundary for safe rendering
 * 
 * Connected files:
 * - All analytics chart components
 */

'use client';

import { ChartErrorBoundary } from './ChartErrorBoundary';

interface SafeChartProps {
  children: React.ReactNode;
  title?: string;
  description?: string;
}

export function SafeChart({ children, title, description }: SafeChartProps) {
  return (
    <ChartErrorBoundary title={title} description={description}>
      {children}
    </ChartErrorBoundary>
  );
}