/**
 * Optimized tweets hook with caching and performance improvements
 * Part of Phase 4 Performance Optimization
 * 
 * Connected files:
 * - /web/hooks/useTweets.ts - Original hook
 * - /web/app/api/tweets/optimized/route.ts - Optimized API endpoint
 * - /web/components/tweets/VirtualTweetInboxList.tsx - Consumer
 */

import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { TweetListItem, TweetStatus } from '@/lib/types'
import { useCallback, useMemo } from 'react'

interface UseOptimizedTweetsOptions {
  status?: TweetStatus
  search?: string
  limit?: number
  includeFullText?: boolean
  enabled?: boolean
}

interface TweetResponse {
  items: TweetListItem[]
  nextCursor?: string
  hasMore: boolean
  totalCount: number
  totalPages: number
  currentPage?: number
}

export function useOptimizedTweets(options: UseOptimizedTweetsOptions = {}) {
  const {
    status,
    search,
    limit = 50, // Higher default for virtual scrolling
    includeFullText = false,
    enabled = true
  } = options
  
  const queryClient = useQueryClient()
  
  // Build query key with all parameters
  const queryKey = useMemo(
    () => ['tweets', 'optimized', { status, search, limit, includeFullText }],
    [status, search, limit, includeFullText]
  )
  
  // Fetch function with optimized endpoint
  const fetchTweets = useCallback(
    async ({ pageParam }: { pageParam?: string }) => {
      const params = new URLSearchParams()
      if (status) params.append('status', status)
      if (search) params.append('search', search)
      if (pageParam) params.append('cursor', pageParam)
      params.append('limit', limit.toString())
      if (includeFullText) params.append('includeFullText', 'true')
      
      const response = await fetch(`/api/tweets/optimized?${params}`)
      if (!response.ok) {
        throw new Error('Failed to fetch tweets')
      }
      
      return response.json() as Promise<TweetResponse>
    },
    [status, search, limit, includeFullText]
  )
  
  // Use infinite query for virtual scrolling
  const query = useInfiniteQuery({
    queryKey,
    queryFn: fetchTweets,
    initialPageParam: undefined,
    getNextPageParam: (lastPage) => lastPage.nextCursor,
    enabled,
    staleTime: 30 * 1000, // Consider data stale after 30 seconds
    gcTime: 5 * 60 * 1000, // Keep in cache for 5 minutes
    refetchOnWindowFocus: false, // Disable automatic refetch on focus
    refetchInterval: false, // Disable periodic refetch
  })
  
  // Flatten pages into single array
  const tweets = useMemo(() => {
    return query.data?.pages.flatMap(page => page.items) ?? []
  }, [query.data])
  
  // Batch update mutation
  const batchUpdateMutation = useMutation({
    mutationFn: async ({ action, tweetIds }: { action: string; tweetIds: string[] }) => {
      const response = await fetch('/api/tweets/optimized', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, tweetIds })
      })
      
      if (!response.ok) {
        throw new Error('Failed to update tweets')
      }
      
      return response.json()
    },
    onSuccess: () => {
      // Invalidate and refetch tweets
      queryClient.invalidateQueries({ queryKey: ['tweets'] })
    }
  })
  
  // Optimistic update function
  const optimisticUpdate = useCallback(
    (tweetId: string, updates: Partial<TweetListItem>) => {
      queryClient.setQueryData(queryKey, (oldData: any) => {
        if (!oldData) return oldData
        
        return {
          ...oldData,
          pages: oldData.pages.map((page: TweetResponse) => ({
            ...page,
            items: page.items.map((tweet: TweetListItem) =>
              tweet.id === tweetId ? { ...tweet, ...updates } : tweet
            )
          }))
        }
      })
    },
    [queryClient, queryKey]
  )
  
  // Prefetch next page for smoother scrolling
  const prefetchNextPage = useCallback(() => {
    if (query.hasNextPage && !query.isFetchingNextPage) {
      query.fetchNextPage()
    }
  }, [query])
  
  return {
    tweets,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    fetchNextPage: query.fetchNextPage,
    hasNextPage: query.hasNextPage ?? false,
    isFetchingNextPage: query.isFetchingNextPage,
    refetch: query.refetch,
    batchUpdate: batchUpdateMutation.mutate,
    optimisticUpdate,
    prefetchNextPage,
    totalCount: query.data?.pages[0]?.totalCount ?? 0,
    isStale: query.isStale,
  }
}