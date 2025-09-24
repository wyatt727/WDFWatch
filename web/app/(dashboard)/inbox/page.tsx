/**
 * Tweet inbox page - displays filtered list of tweets
 * Main entry point for operators to discover and triage tweets
 * Interacts with: TweetInboxList component, useTweets hook
 */

"use client"

import { useState } from "react"
import { useTweets } from "@/hooks/useTweets"
import { TweetStatus } from "@/lib/types"
import { TweetInboxList, FilterState } from "@/components/tweets/TweetInboxList"
import { TweetFilters } from "@/components/tweets/TweetFilters"
import { TweetDrawer } from "@/components/tweets/TweetDrawer"
import { Button } from "@/components/ui/button"
import { RefreshCw } from "lucide-react"

export default function InboxPage() {
  const [selectedStatus, setSelectedStatus] = useState<TweetStatus | undefined>()
  const [selectedTweetId, setSelectedTweetId] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState<string>("")
  
  const {
    tweets,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isFetching,
  } = useTweets({ status: selectedStatus })

  const filters: FilterState = {
    status: selectedStatus,
    searchTerm: searchTerm,
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Tweet Inbox</h2>
          <p className="text-muted-foreground">
            Discover and classify relevant tweets for engagement
          </p>
        </div>
        
        {/* Refresh button with cost warning */}
        <Button variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh (est. ~50 reads)
        </Button>
      </div>

      {/* Filters */}
      <TweetFilters
        selectedStatus={selectedStatus}
        onStatusChange={setSelectedStatus}
        searchTerm={searchTerm}
        onSearchChange={setSearchTerm}
      />

      {/* Tweet list with real-time updates */}
      <TweetInboxList
        tweets={tweets}
        onSelectTweet={setSelectedTweetId}
        filters={filters}
        onLoadMore={fetchNextPage}
        hasMore={hasNextPage}
        isLoading={isFetchingNextPage || isFetching}
      />

      {/* Tweet detail drawer */}
      <TweetDrawer
        tweetId={selectedTweetId}
        open={!!selectedTweetId}
        onClose={() => setSelectedTweetId(null)}
      />
    </div>
  )
}