/**
 * ChartErrorBoundary Component
 * Error boundary for catching and handling chart rendering errors
 * 
 * Connected files:
 * - All chart components that use recharts
 */

'use client';

import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertCircle } from 'lucide-react';

interface ChartErrorBoundaryProps {
  children: React.ReactNode;
  title?: string;
  description?: string;
}

interface ChartErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

export class ChartErrorBoundary extends React.Component<ChartErrorBoundaryProps, ChartErrorBoundaryState> {
  constructor(props: ChartErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ChartErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Chart rendering error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <Card className="col-span-4">
          <CardHeader>
            <CardTitle>{this.props.title || 'Chart'}</CardTitle>
            {this.props.description && (
              <CardDescription>{this.props.description}</CardDescription>
            )}
          </CardHeader>
          <CardContent>
            <div className="h-[300px] w-full flex flex-col items-center justify-center text-muted-foreground">
              <AlertCircle className="h-8 w-8 mb-2" />
              <p className="text-sm font-medium">Unable to display chart</p>
              <p className="text-xs mt-1">Please refresh the page or try again later</p>
              {process.env.NODE_ENV === 'development' && this.state.error && (
                <p className="text-xs mt-2 text-red-500 max-w-sm text-center">
                  {this.state.error.message}
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      );
    }

    return this.props.children;
  }
}