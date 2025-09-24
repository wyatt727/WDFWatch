'use client';

/**
 * Audit Log Viewer Component
 * 
 * Displays a paginated list of audit log entries with filtering.
 * Integrates with: /api/audit-logs
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { 
  Clock, 
  User, 
  FileText, 
  Search,
  ChevronLeft,
  ChevronRight,
  Activity
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

interface AuditLog {
  id: string;
  action: string;
  entityType: string;
  entityId?: string;
  userId?: string;
  details: any;
  createdAt: string;
}

interface AuditLogResponse {
  items: AuditLog[];
  total: number;
  page: number;
  pageSize: number;
}

const ACTION_COLORS: Record<string, string> = {
  created: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  updated: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  deleted: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  approved: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
  rejected: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
  posted: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200',
};

function getActionColor(action: string): string {
  const actionType = action.split('_').pop() || '';
  return ACTION_COLORS[actionType] || 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200';
}

function formatAction(action: string): string {
  return action
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export function AuditLogViewer() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [entityType, setEntityType] = useState<string>('all');
  const [actionFilter, setActionFilter] = useState<string>('all');
  
  const { data, isLoading } = useQuery<AuditLogResponse>({
    queryKey: ['audit-logs', page, search, entityType, actionFilter],
    queryFn: async () => {
      const params = new URLSearchParams({
        page: page.toString(),
        pageSize: '20',
      });
      
      if (search) params.append('search', search);
      if (entityType !== 'all') params.append('entityType', entityType);
      if (actionFilter !== 'all') params.append('action', actionFilter);
      
      const response = await fetch(`/api/audit-logs?${params}`);
      if (!response.ok) throw new Error('Failed to fetch audit logs');
      return response.json();
    },
  });
  
  const totalPages = data ? Math.ceil(data.total / data.pageSize) : 0;
  
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="h-5 w-5" />
          Audit Log
        </CardTitle>
        <CardDescription>
          Track all actions performed in the system
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
              <Input
                placeholder="Search by entity ID or user..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10"
              />
            </div>
          </div>
          
          <Select value={entityType} onValueChange={setEntityType}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Entity Type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              <SelectItem value="tweet">Tweets</SelectItem>
              <SelectItem value="draft_reply">Drafts</SelectItem>
              <SelectItem value="episode">Episodes</SelectItem>
            </SelectContent>
          </Select>
          
          <Select value={actionFilter} onValueChange={setActionFilter}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Action" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Actions</SelectItem>
              <SelectItem value="created">Created</SelectItem>
              <SelectItem value="updated">Updated</SelectItem>
              <SelectItem value="deleted">Deleted</SelectItem>
              <SelectItem value="approved">Approved</SelectItem>
              <SelectItem value="rejected">Rejected</SelectItem>
              <SelectItem value="posted">Posted</SelectItem>
            </SelectContent>
          </Select>
        </div>
        
        {/* Audit Log List */}
        {isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="flex items-center space-x-4 py-3">
                <Skeleton className="h-12 w-12 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              </div>
            ))}
          </div>
        ) : data?.items.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-muted-foreground">No audit logs found</p>
          </div>
        ) : (
          <div className="space-y-3">
            {data?.items.map((log) => (
              <div
                key={log.id}
                className="flex items-start space-x-4 py-3 border-b last:border-0"
              >
                <div className="mt-1">
                  <div className="h-10 w-10 rounded-full bg-muted flex items-center justify-center">
                    {log.entityType === 'tweet' && <FileText className="h-5 w-5" />}
                    {log.entityType === 'draft_reply' && <FileText className="h-5 w-5" />}
                    {log.entityType === 'episode' && <Activity className="h-5 w-5" />}
                    {!['tweet', 'draft_reply', 'episode'].includes(log.entityType) && 
                      <Activity className="h-5 w-5" />
                    }
                  </div>
                </div>
                
                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge 
                      variant="secondary" 
                      className={getActionColor(log.action)}
                    >
                      {formatAction(log.action)}
                    </Badge>
                    <span className="text-sm text-muted-foreground">
                      {log.entityType}
                      {log.entityId && ` #${String(log.entityId).slice(0, 8)}`}
                    </span>
                  </div>
                  
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {formatDistanceToNow(new Date(log.createdAt), { addSuffix: true })}
                    </span>
                    {log.userId && (
                      <span className="flex items-center gap-1">
                        <User className="h-3 w-3" />
                        User #{log.userId.slice(0, 8)}
                      </span>
                    )}
                  </div>
                  
                  {log.details && Object.keys(log.details).length > 0 && (
                    <details className="mt-2">
                      <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                        View details
                      </summary>
                      <pre className="mt-2 text-xs bg-muted p-2 rounded overflow-x-auto">
                        {JSON.stringify(log.details, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
        
        {/* Pagination */}
        {data && totalPages > 1 && (
          <div className="flex items-center justify-between pt-4">
            <p className="text-sm text-muted-foreground">
              Showing {((page - 1) * data.pageSize) + 1} to{' '}
              {Math.min(page * data.pageSize, data.total)} of {data.total} entries
            </p>
            
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
              >
                <ChevronLeft className="h-4 w-4" />
                Previous
              </Button>
              
              <span className="text-sm">
                Page {page} of {totalPages}
              </span>
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page === totalPages}
              >
                Next
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}