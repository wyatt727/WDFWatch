/**
 * TweetInboxList component for displaying tweets with real-time updates
 * Part of Phase 2 Web UI Migration implementation
 * Interacts with: useTweets hook, TweetRow component, SSE events
 */

import { useEffect, useRef } from "react"
import { TweetListItem, TweetStatus } from "@/lib/types"
import { TweetRow } from "./TweetRow"
import { useInView } from "react-intersection-observer"

export interface FilterState {
  status?: TweetStatus
  searchTerm?: string
  dateRange?: {
    start: Date
    end: Date
  }
}

interface TweetInboxListProps {
  tweets: TweetListItem[]
  onSelectTweet: (id: string) => void
  filters: FilterState
  onLoadMore?: () => void
  hasMore?: boolean
  isLoading?: boolean
}

export function TweetInboxList({
  tweets,
  onSelectTweet,
  filters,
  onLoadMore,
  hasMore = false,
  isLoading = false,
}: TweetInboxListProps) {
  // Intersection observer for infinite scroll
  const { ref: loadMoreRef, inView } = useInView({
    threshold: 0,
    rootMargin: "100px",
  })

  // Trigger load more when scrolling to bottom
  useEffect(() => {
    if (inView && hasMore && !isLoading && onLoadMore) {
      onLoadMore()
    }
  }, [inView, hasMore, isLoading, onLoadMore])

  // Filter tweets based on local filters
  const filteredTweets = tweets.filter((tweet) => {
    if (filters.searchTerm) {
      const searchLower = filters.searchTerm.toLowerCase()
      if (
        !tweet.textPreview.toLowerCase().includes(searchLower) &&
        !tweet.authorHandle.toLowerCase().includes(searchLower)
      ) {
        return false
      }
    }
    return true
  })

  if (filteredTweets.length === 0 && !isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
        <p className="text-lg font-medium">No tweets found</p>
        <p className="text-sm mt-2">
          {filters.searchTerm
            ? "Try adjusting your search terms"
            : "New tweets will appear here automatically"}
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {filteredTweets.map((tweet) => (
        <TweetRow
          key={tweet.id}
          tweet={tweet}
          onClick={() => onSelectTweet(tweet.id)}
        />
      ))}
      
      {/* Loading indicator for infinite scroll */}
      {hasMore && (
        <div
          ref={loadMoreRef}
          className="flex justify-center py-4"
        >
          {isLoading && (
            <div className="flex items-center space-x-2 text-muted-foreground">
              <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              <span className="text-sm">Loading more tweets...</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}