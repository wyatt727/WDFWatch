/**
 * Tweet Queue Dashboard
 * 
 * Comprehensive interface for managing the tweet processing queue.
 * Features:
 * - Real-time queue status with SSE updates
 * - Advanced filtering (status, episode, priority)
 * - Bulk actions (assign episode, change priority)
 * - Visual priority indicators
 * - Queue statistics and health metrics
 * 
 * UX Optimizations:
 * - Progressive disclosure (expandable details)
 * - Keyboard shortcuts for power users
 * - Responsive design for mobile access
 * - Undo capability for destructive actions
 * - Clear visual feedback for all actions
 */

'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { formatDistanceToNow } from 'date-fns'
import {
  ChevronDown,
  ChevronRight,
  Filter,
  AlertCircle,
  Clock,
  CheckCircle,
  XCircle,
  RefreshCw,
  Archive,
  Zap,
  TrendingUp,
  Users,
  Hash,
  MoreVertical,
  Search,
  Upload,
  Download,
  Play,
  Pause,
  SkipForward,
  Trash2,
  Edit,
  Link,
  MessageSquare,
  Info
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Checkbox } from '@/components/ui/checkbox'
import { Progress } from '@/components/ui/progress'
import { Separator } from '@/components/ui/separator'
import { useToast } from '@/components/ui/use-toast'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { useSSE } from '@/hooks/use-sse'
import { cn } from '@/lib/utils'

// Types
interface QueueItem {
  id: number
  tweetId: string
  twitterId: string
  source: 'manual' | 'scrape' | 'direct_url' | 'cache'
  priority: number
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled'
  episodeId?: number
  episodeTitle?: string
  addedBy?: string
  addedAt: string
  processedAt?: string
  tweetText?: string
  authorHandle?: string
  authorName?: string
  relevanceScore?: number
  metrics?: any
  metadata?: any
  retryCount: number
}

interface QueueStats {
  pending: { count: number; avgPriority: number }
  processing: { count: number; avgPriority: number }
  completed: { count: number; avgPriority: number }
  failed: { count: number; avgPriority: number }
  cancelled: { count: number; avgPriority: number }
}

// Status colors and icons
const statusConfig = {
  pending: { color: 'bg-yellow-500', icon: Clock, label: 'Pending' },
  processing: { color: 'bg-blue-500', icon: RefreshCw, label: 'Processing' },
  completed: { color: 'bg-green-500', icon: CheckCircle, label: 'Completed' },
  failed: { color: 'bg-red-500', icon: XCircle, label: 'Failed' },
  cancelled: { color: 'bg-gray-500', icon: Archive, label: 'Cancelled' }
}

// Priority colors
const getPriorityColor = (priority: number) => {
  if (priority >= 8) return 'text-red-600 bg-red-50'
  if (priority >= 6) return 'text-orange-600 bg-orange-50'
  if (priority >= 4) return 'text-yellow-600 bg-yellow-50'
  return 'text-gray-600 bg-gray-50'
}

export default function TweetQueuePage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  
  // State
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set())
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [episodeFilter, setEpisodeFilter] = useState<string>('all')
  const [showOrphaned, setShowOrphaned] = useState(false)
  const [sortBy, setSortBy] = useState<'priority' | 'date'>('priority')
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('list')
  
  // SSE for real-time updates
  const sseEvents = useSSE('/api/events', {
    onMessage: (event) => {
      if (event.type === 'tweet_queue_updated') {
        queryClient.invalidateQueries({ queryKey: ['tweet-queue'] })
      }
    }
  })

  // Fetch queue data
  const { data: queueData, isLoading, refetch } = useQuery({
    queryKey: ['tweet-queue', statusFilter, episodeFilter, showOrphaned],
    queryFn: async () => {
      const params = new URLSearchParams({
        status: statusFilter,
        includeOrphaned: showOrphaned.toString(),
        limit: '100'
      })
      if (episodeFilter !== 'all') {
        params.append('episodeId', episodeFilter)
      }
      
      const response = await fetch(`/api/tweet-queue?${params}`)
      if (!response.ok) throw new Error('Failed to fetch queue')
      return response.json()
    },
    refetchInterval: 30000 // Refresh every 30 seconds
  })

  // Fetch episodes for filter
  const { data: episodes } = useQuery({
    queryKey: ['episodes'],
    queryFn: async () => {
      const response = await fetch('/api/episodes')
      if (!response.ok) throw new Error('Failed to fetch episodes')
      return response.json()
    }
  })

  // Update queue items mutation
  const updateQueueMutation = useMutation({
    mutationFn: async ({ queueIds, updates }: { queueIds: string[], updates: any }) => {
      const response = await fetch('/api/tweet-queue', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ queueIds, updates })
      })
      if (!response.ok) throw new Error('Failed to update queue')
      return response.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tweet-queue'] })
      toast({ title: 'Queue updated successfully' })
      setSelectedItems(new Set())
    },
    onError: () => {
      toast({ title: 'Failed to update queue', variant: 'destructive' })
    }
  })

  // Process queue mutation - process ALL pending tweets
  const processQueueMutation = useMutation({
    mutationFn: async (batchSize: number = 1000) => {  // Process up to 1000 tweets (effectively all)
      const response = await fetch('/api/tweet-queue/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ batchSize })
      })
      if (!response.ok) throw new Error('Failed to start processing')
      return response.json()
    },
    onSuccess: () => {
      toast({ title: 'Processing started' })
    },
    onError: () => {
      toast({ title: 'Failed to start processing', variant: 'destructive' })
    }
  })

  // Filtered and sorted items
  const filteredItems = useMemo(() => {
    if (!queueData?.items) return []
    
    let items = [...queueData.items]
    
    // Search filter
    if (searchQuery) {
      items = items.filter(item => 
        item.tweetText?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.authorHandle?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.twitterId.includes(searchQuery)
      )
    }
    
    // Sort
    if (sortBy === 'priority') {
      items.sort((a, b) => {
        if (a.status === 'processing') return -1
        if (b.status === 'processing') return 1
        return b.priority - a.priority
      })
    } else {
      items.sort((a, b) => new Date(b.addedAt).getTime() - new Date(a.addedAt).getTime())
    }
    
    return items
  }, [queueData, searchQuery, sortBy])

  // Toggle item expansion
  const toggleExpanded = (id: string) => {
    setExpandedItems(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  // Toggle item selection
  const toggleSelected = (id: string) => {
    setSelectedItems(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  // Select all visible items
  const selectAll = () => {
    if (selectedItems.size === filteredItems.length) {
      setSelectedItems(new Set())
    } else {
      setSelectedItems(new Set(filteredItems.map(item => item.tweetId)))
    }
  }

  // Bulk actions
  const handleBulkAction = (action: string, value?: any) => {
    const queueIds = Array.from(selectedItems)
    
    switch (action) {
      case 'setPriority':
        updateQueueMutation.mutate({ queueIds, updates: { priority: value } })
        break
      case 'setStatus':
        updateQueueMutation.mutate({ queueIds, updates: { status: value } })
        break
      case 'assignEpisode':
        updateQueueMutation.mutate({ queueIds, updates: { episodeId: value } })
        break
      case 'retry':
        updateQueueMutation.mutate({ queueIds, updates: { status: 'pending', retryCount: 0 } })
        break
      case 'cancel':
        updateQueueMutation.mutate({ queueIds, updates: { status: 'cancelled' } })
        break
    }
  }

  // Queue health indicator
  const queueHealth = useMemo(() => {
    if (!queueData?.stats) return 'unknown'
    
    const failureRate = queueData.stats.failed?.count / 
      (queueData.stats.completed?.count + queueData.stats.failed?.count || 1)
    
    if (failureRate > 0.2) return 'poor'
    if (failureRate > 0.1) return 'fair'
    if (queueData.stats.pending?.count > 500) return 'busy'
    return 'healthy'
  }, [queueData])

  const healthColors = {
    healthy: 'text-green-600 bg-green-50',
    busy: 'text-yellow-600 bg-yellow-50',
    fair: 'text-orange-600 bg-orange-50',
    poor: 'text-red-600 bg-red-50',
    unknown: 'text-gray-600 bg-gray-50'
  }

  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* Header with stats */}
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold">Tweet Queue</h1>
              <p className="text-muted-foreground">
                Manage and monitor tweet processing pipeline
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge className={cn('px-3 py-1', healthColors[queueHealth])}>
                {queueHealth === 'healthy' && <CheckCircle className="w-3 h-3 mr-1" />}
                {queueHealth === 'busy' && <Clock className="w-3 h-3 mr-1" />}
                {queueHealth === 'poor' && <AlertCircle className="w-3 h-3 mr-1" />}
                Queue {queueHealth}
              </Badge>
              <Button
                onClick={() => refetch()}
                variant="outline"
                size="sm"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </Button>
              <Button
                onClick={() => processQueueMutation.mutate(1000)}  // Process all tweets
                disabled={processQueueMutation.isPending}
              >
                <Play className="w-4 h-4 mr-2" />
                Process Queue
              </Button>
            </div>
          </div>

          {/* Statistics Cards */}
          <div className="grid grid-cols-5 gap-4">
            {Object.entries(statusConfig).map(([status, config]) => {
              const stats = queueData?.stats?.[status] || { count: 0, avgPriority: 0 }
              return (
                <Card key={status} className="relative overflow-hidden">
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <config.icon className="w-4 h-4 text-muted-foreground" />
                      <Badge variant="secondary" className="text-xs">
                        Avg Priority: {stats.avgPriority.toFixed(1)}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{stats.count}</div>
                    <p className="text-xs text-muted-foreground">{config.label}</p>
                    <div className={cn('absolute bottom-0 left-0 right-0 h-1', config.color)} />
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </div>

        {/* Filters and Actions Bar */}
        <Card>
          <CardContent className="p-4">
            <div className="flex flex-col gap-4">
              {/* Search and filters */}
              <div className="flex items-center gap-4">
                <div className="relative flex-1 max-w-sm">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-4 h-4" />
                  <Input
                    placeholder="Search tweets..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9"
                  />
                </div>
                
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="w-[150px]">
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Status</SelectItem>
                    {Object.entries(statusConfig).map(([status, config]) => (
                      <SelectItem key={status} value={status}>
                        <div className="flex items-center gap-2">
                          <config.icon className="w-3 h-3" />
                          {config.label}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Select value={episodeFilter} onValueChange={setEpisodeFilter}>
                  <SelectTrigger className="w-[200px]">
                    <SelectValue placeholder="Episode" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Episodes</SelectItem>
                    {episodes?.episodes?.map((episode: any) => (
                      <SelectItem key={episode.id} value={episode.id.toString()}>
                        {episode.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <div className="flex items-center gap-2">
                  <Checkbox
                    id="orphaned"
                    checked={showOrphaned}
                    onCheckedChange={(checked) => setShowOrphaned(!!checked)}
                  />
                  <label
                    htmlFor="orphaned"
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                  >
                    Show orphaned
                  </label>
                </div>

                <Select value={sortBy} onValueChange={(value: any) => setSortBy(value)}>
                  <SelectTrigger className="w-[150px]">
                    <SelectValue placeholder="Sort by" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="priority">Priority</SelectItem>
                    <SelectItem value="date">Date Added</SelectItem>
                  </SelectContent>
                </Select>

                <div className="flex items-center gap-1 border rounded-md">
                  <Button
                    variant={viewMode === 'list' ? 'secondary' : 'ghost'}
                    size="sm"
                    onClick={() => setViewMode('list')}
                  >
                    List
                  </Button>
                  <Button
                    variant={viewMode === 'grid' ? 'secondary' : 'ghost'}
                    size="sm"
                    onClick={() => setViewMode('grid')}
                  >
                    Grid
                  </Button>
                </div>
              </div>

              {/* Bulk actions */}
              {selectedItems.size > 0 && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="flex items-center gap-4 p-3 bg-muted rounded-lg"
                >
                  <span className="text-sm font-medium">
                    {selectedItems.size} items selected
                  </span>
                  <Separator orientation="vertical" className="h-6" />
                  
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline" size="sm">
                        <TrendingUp className="w-4 h-4 mr-2" />
                        Set Priority
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent>
                      {[10, 8, 6, 4, 2, 0].map(priority => (
                        <DropdownMenuItem
                          key={priority}
                          onClick={() => handleBulkAction('setPriority', priority)}
                        >
                          <Badge className={cn('mr-2', getPriorityColor(priority))}>
                            {priority}
                          </Badge>
                          Priority {priority}
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>

                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline" size="sm">
                        <Hash className="w-4 h-4 mr-2" />
                        Assign Episode
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent>
                      {episodes?.episodes?.map((episode: any) => (
                        <DropdownMenuItem
                          key={episode.id}
                          onClick={() => handleBulkAction('assignEpisode', episode.id)}
                        >
                          {episode.title}
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleBulkAction('retry')}
                  >
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Retry
                  </Button>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleBulkAction('cancel')}
                  >
                    <XCircle className="w-4 h-4 mr-2" />
                    Cancel
                  </Button>

                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedItems(new Set())}
                  >
                    Clear Selection
                  </Button>
                </motion.div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Queue Items */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <Checkbox
                  checked={selectedItems.size === filteredItems.length && filteredItems.length > 0}
                  onCheckedChange={selectAll}
                />
                <span className="text-sm text-muted-foreground">
                  {filteredItems.length} items
                </span>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {isLoading ? (
              <div className="flex items-center justify-center h-64">
                <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : filteredItems.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
                <Archive className="w-12 h-12 mb-4" />
                <p>No items in queue</p>
              </div>
            ) : (
              <div className={cn(
                viewMode === 'grid' ? 'grid grid-cols-2 gap-4 p-4' : 'divide-y'
              )}>
                <AnimatePresence>
                  {filteredItems.map((item) => (
                    <QueueItemCard
                      key={item.tweetId}
                      item={item}
                      isExpanded={expandedItems.has(item.tweetId)}
                      isSelected={selectedItems.has(item.tweetId)}
                      onToggleExpanded={() => toggleExpanded(item.tweetId)}
                      onToggleSelected={() => toggleSelected(item.tweetId)}
                      viewMode={viewMode}
                    />
                  ))}
                </AnimatePresence>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </TooltipProvider>
  )
}

// Queue Item Component
function QueueItemCard({
  item,
  isExpanded,
  isSelected,
  onToggleExpanded,
  onToggleSelected,
  viewMode
}: {
  item: QueueItem
  isExpanded: boolean
  isSelected: boolean
  onToggleExpanded: () => void
  onToggleSelected: () => void
  viewMode: 'grid' | 'list'
}) {
  const statusInfo = statusConfig[item.status]
  const StatusIcon = statusInfo.icon
  
  if (viewMode === 'grid') {
    return (
      <motion.div
        layout
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.9 }}
        className={cn(
          "border rounded-lg p-4 space-y-3 cursor-pointer transition-colors",
          isSelected && "bg-accent"
        )}
        onClick={onToggleSelected}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <Checkbox checked={isSelected} />
            <StatusIcon className="w-4 h-4" />
            <Badge className={cn('text-xs', getPriorityColor(item.priority))}>
              P{item.priority}
            </Badge>
          </div>
          <Badge variant="outline" className="text-xs">
            {item.source}
          </Badge>
        </div>
        
        <div className="space-y-1">
          <p className="font-medium text-sm">{item.authorHandle?.startsWith('@') ? item.authorHandle : `@${item.authorHandle || ''}`}</p>
          <p className="text-xs text-muted-foreground line-clamp-2">
            {item.tweetText}
          </p>
        </div>
        
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{formatDistanceToNow(new Date(item.addedAt), { addSuffix: true })}</span>
          {item.episodeTitle && (
            <span className="truncate max-w-[150px]">{item.episodeTitle}</span>
          )}
        </div>
      </motion.div>
    )
  }
  
  return (
    <motion.div
      layout
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className={cn(
        "px-4 py-3 hover:bg-accent/50 transition-colors",
        isSelected && "bg-accent"
      )}
    >
      <div className="flex items-center gap-4">
        <Checkbox
          checked={isSelected}
          onCheckedChange={onToggleSelected}
          onClick={(e) => e.stopPropagation()}
        />
        
        <button
          onClick={onToggleExpanded}
          className="p-1 hover:bg-muted rounded"
        >
          {isExpanded ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
        </button>
        
        <div className="flex items-center gap-2">
          <StatusIcon className="w-4 h-4" />
          <Badge variant="outline" className="text-xs">
            {statusInfo.label}
          </Badge>
        </div>
        
        <Badge className={cn('text-xs', getPriorityColor(item.priority))}>
          Priority {item.priority}
        </Badge>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium">{item.authorHandle?.startsWith('@') ? item.authorHandle : `@${item.authorHandle || ''}`}</span>
            {item.authorName && (
              <span className="text-sm text-muted-foreground">({item.authorName})</span>
            )}
          </div>
          <p className="text-sm text-muted-foreground truncate">
            {item.tweetText}
          </p>
        </div>
        
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <Tooltip>
            <TooltipTrigger>
              <Badge variant="outline" className="text-xs">
                {item.source}
              </Badge>
            </TooltipTrigger>
            <TooltipContent>
              <p>Source: {item.source}</p>
              {item.addedBy && <p>Added by: {item.addedBy}</p>}
            </TooltipContent>
          </Tooltip>
          
          {item.episodeTitle ? (
            <Tooltip>
              <TooltipTrigger>
                <Badge variant="secondary" className="text-xs">
                  {item.episodeTitle.substring(0, 20)}...
                </Badge>
              </TooltipTrigger>
              <TooltipContent>
                <p>{item.episodeTitle}</p>
              </TooltipContent>
            </Tooltip>
          ) : (
            <Badge variant="destructive" className="text-xs">
              Orphaned
            </Badge>
          )}
          
          <span className="text-xs">
            {formatDistanceToNow(new Date(item.addedAt), { addSuffix: true })}
          </span>
        </div>
        
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm">
              <MoreVertical className="w-4 h-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Actions</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem>
              <Link className="w-4 h-4 mr-2" />
              View on Twitter
            </DropdownMenuItem>
            <DropdownMenuItem>
              <MessageSquare className="w-4 h-4 mr-2" />
              Generate Response
            </DropdownMenuItem>
            <DropdownMenuItem>
              <Edit className="w-4 h-4 mr-2" />
              Change Priority
            </DropdownMenuItem>
            <DropdownMenuItem>
              <RefreshCw className="w-4 h-4 mr-2" />
              Retry Processing
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="text-destructive">
              <Trash2 className="w-4 h-4 mr-2" />
              Remove from Queue
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      
      {isExpanded && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          className="mt-4 pl-12 space-y-3"
        >
          <div className="p-3 bg-muted rounded-lg">
            <p className="text-sm">{item.tweetText}</p>
          </div>
          
          {item.metrics && (
            <div className="flex items-center gap-4 text-sm">
              <span>❤️ {item.metrics.likes || 0}</span>
              <span>🔁 {item.metrics.retweets || 0}</span>
              <span>💬 {item.metrics.replies || 0}</span>
            </div>
          )}
          
          {item.relevanceScore !== undefined && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Relevance Score:</span>
              <Progress value={item.relevanceScore * 100} className="w-32 h-2" />
              <span className="text-sm font-medium">{(item.relevanceScore * 100).toFixed(0)}%</span>
            </div>
          )}
          
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Tweet ID:</span>
              <span className="ml-2 font-mono">{item.twitterId}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Queue ID:</span>
              <span className="ml-2 font-mono">{item.tweetId}</span>
            </div>
            {item.processedAt && (
              <div>
                <span className="text-muted-foreground">Processed:</span>
                <span className="ml-2">
                  {formatDistanceToNow(new Date(item.processedAt), { addSuffix: true })}
                </span>
              </div>
            )}
            {item.retryCount > 0 && (
              <div>
                <span className="text-muted-foreground">Retries:</span>
                <span className="ml-2">{item.retryCount}</span>
              </div>
            )}
          </div>
          
          {item.metadata && Object.keys(item.metadata).length > 0 && (
            <div className="p-2 bg-muted rounded text-xs font-mono">
              <pre>{JSON.stringify(item.metadata, null, 2)}</pre>
            </div>
          )}
        </motion.div>
      )}
    </motion.div>
  )
}