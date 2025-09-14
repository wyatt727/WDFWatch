/**
 * React Query hook for fetching and managing tweets
 * Provides infinite scrolling and real-time updates via SSE
 * Interacts with: /api/tweets route, SSE event handler
 */

import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { TweetListItem, TweetStatus } from "@/lib/types"

interface TweetsResponse {
  items: TweetListItem[]
  nextCursor?: string
  hasMore: boolean
}

interface UseTweetsOptions {
  status?: TweetStatus
  limit?: number
}

export function useTweets({ status, limit = 20 }: UseTweetsOptions = {}) {
  const queryClient = useQueryClient()

  const queryKey = ["tweets", { status, limit }]

  const {
    data,
    error,
    fetchNextPage,
    hasNextPage,
    isFetching,
    isFetchingNextPage,
    status: queryStatus,
  } = useInfiniteQuery<TweetsResponse>({
    queryKey,
    queryFn: async ({ pageParam }) => {
      const params = new URLSearchParams()
      if (status) params.append("status", status)
      if (pageParam && typeof pageParam === 'string') {
        params.append("cursor", pageParam)
      }
      params.append("limit", limit.toString())

      const response = await fetch(`/api/tweets?${params}`)
      if (!response.ok) {
        throw new Error("Failed to fetch tweets")
      }
      return response.json() as Promise<TweetsResponse>
    },
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.nextCursor,
    staleTime: 2 * 60 * 1000, // 2 minutes as per spec
  })

  // Set up SSE for real-time updates
  useEffect(() => {
    const eventSource = new EventSource("/api/events")

    eventSource.addEventListener("tweet_status", (event) => {
      const data = JSON.parse(event.data)
      // Invalidate queries when tweet status changes
      queryClient.invalidateQueries({ queryKey: ["tweets"] })
    })

    eventSource.addEventListener("error", (error) => {
      console.error("SSE error:", error)
      eventSource.close()
    })

    return () => {
      eventSource.close()
    }
  }, [queryClient])

  const tweets = data?.pages.flatMap((page) => page.items) ?? []

  return {
    tweets,
    error,
    fetchNextPage,
    hasNextPage,
    isFetching,
    isFetchingNextPage,
    status: queryStatus,
  }
}