/**
 * VirtualTweetInboxList component - Performance-optimized tweet list with virtual scrolling
 * Part of Phase 4 Performance Optimization
 * 
 * Connected files:
 * - /web/components/tweets/TweetInboxList.tsx - Original non-virtualized version
 * - /web/app/(dashboard)/inbox/page.tsx - Used in inbox page
 * - /web/hooks/useTweets.ts - Data source
 */

import { useEffect, useRef, useCallback, forwardRef } from "react"
import { VariableSizeList as List } from "react-window"
import { TweetListItem, TweetStatus } from "@/lib/types"
import { TweetRow } from "./TweetRow"
import { useInView } from "react-intersection-observer"
import { cn } from "@/lib/utils"

export interface FilterState {
  status?: TweetStatus
  searchTerm?: string
  dateRange?: {
    start: Date
    end: Date
  }
}

interface VirtualTweetInboxListProps {
  tweets: TweetListItem[]
  onSelectTweet: (id: string) => void
  filters: FilterState
  onLoadMore?: () => void
  hasMore?: boolean
  isLoading?: boolean
  height?: number
}

// Height cache for variable size list
const itemHeightCache = new Map<string, number>()
const ESTIMATED_ITEM_HEIGHT = 120 // Estimated height for tweets

// Custom inner element to handle load more trigger
const InnerElement = forwardRef<HTMLDivElement, any>(
  ({ style, children, ...rest }, ref) => {
    return (
      <div
        ref={ref}
        style={{
          ...style,
          height: `${parseFloat(style.height) + 100}px`, // Add extra space for load more trigger
        }}
        {...rest}
      >
        {children}
      </div>
    )
  }
)
InnerElement.displayName = "InnerElement"

export function VirtualTweetInboxList({
  tweets,
  onSelectTweet,
  filters,
  onLoadMore,
  hasMore = false,
  isLoading = false,
  height = 600,
}: VirtualTweetInboxListProps) {
  const listRef = useRef<List>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  
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
  
  // Get item size with caching
  const getItemSize = useCallback((index: number) => {
    const tweet = filteredTweets[index]
    if (!tweet) return ESTIMATED_ITEM_HEIGHT
    
    const cachedHeight = itemHeightCache.get(tweet.id)
    if (cachedHeight) return cachedHeight
    
    // Estimate based on text length
    const textLength = tweet.textPreview.length
    const estimatedLines = Math.ceil(textLength / 80) // ~80 chars per line
    const estimatedHeight = 80 + (estimatedLines * 20) // Base height + line height
    
    return Math.max(estimatedHeight, ESTIMATED_ITEM_HEIGHT)
  }, [filteredTweets])
  
  // Update cache when item is rendered
  const setItemSize = useCallback((tweetId: string, size: number) => {
    const currentSize = itemHeightCache.get(tweetId)
    if (currentSize !== size && listRef.current) {
      itemHeightCache.set(tweetId, size)
      listRef.current.resetAfterIndex(0) // Recalculate positions
    }
  }, [])
  
  // Row renderer with load more trigger
  const Row = useCallback(({ index, style }: { index: number; style: React.CSSProperties }) => {
    const tweet = filteredTweets[index]
    const isLastItem = index === filteredTweets.length - 1
    
    if (!tweet) return null
    
    return (
      <div style={style}>
        <div
          ref={(el) => {
            if (el && el.offsetHeight) {
              setItemSize(tweet.id, el.offsetHeight)
            }
          }}
        >
          <TweetRow
            tweet={tweet}
            onClick={() => onSelectTweet(tweet.id)}
          />
        </div>
        
        {/* Load more trigger */}
        {isLastItem && hasMore && (
          <LoadMoreTrigger
            onLoadMore={onLoadMore}
            isLoading={isLoading}
          />
        )}
      </div>
    )
  }, [filteredTweets, onSelectTweet, hasMore, isLoading, onLoadMore, setItemSize])
  
  // Reset scroll position when filters change
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollToItem(0, "start")
    }
  }, [filters])
  
  // Empty state
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
    <div ref={containerRef} className="relative">
      <List
        ref={listRef}
        height={height}
        itemCount={filteredTweets.length}
        itemSize={getItemSize}
        width="100%"
        innerElementType={InnerElement}
        className="scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100"
        overscanCount={5} // Render 5 items outside visible area
      >
        {Row}
      </List>
    </div>
  )
}

// Separate component for load more trigger to avoid re-renders
function LoadMoreTrigger({ 
  onLoadMore, 
  isLoading 
}: { 
  onLoadMore?: () => void
  isLoading: boolean 
}) {
  const { ref, inView } = useInView({
    threshold: 0,
    rootMargin: "100px",
  })
  
  useEffect(() => {
    if (inView && !isLoading && onLoadMore) {
      onLoadMore()
    }
  }, [inView, isLoading, onLoadMore])
  
  return (
    <div
      ref={ref}
      className="flex justify-center py-4"
    >
      {isLoading && (
        <div className="flex items-center space-x-2 text-muted-foreground">
          <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">Loading more tweets...</span>
        </div>
      )}
    </div>
  )
}