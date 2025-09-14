/**
 * TweetRow component for displaying individual tweet in list
 * Implements status indicators, relevance scoring, and click handling
 * Interacts with: TweetInboxList parent component
 */

import { TweetListItem } from "@/lib/types"
import { cn } from "@/lib/utils"
import { formatDistanceToNow } from "date-fns"
import { CheckCircle2, AlertCircle, MessageSquare, Zap } from "lucide-react"

interface TweetRowProps {
  tweet: TweetListItem
  onClick?: () => void
  isSelected?: boolean
}

export function TweetRow({ tweet, onClick, isSelected = false }: TweetRowProps) {
  // Status color mapping
  const statusColors = {
    unclassified: "bg-gray-100 text-gray-700",
    skipped: "bg-gray-100 text-gray-500",
    relevant: "bg-blue-100 text-blue-700",
    drafted: "bg-yellow-100 text-yellow-700",
    posted: "bg-green-100 text-green-700",
  }

  // Status icons
  const statusIcons = {
    unclassified: null,
    skipped: null,
    relevant: <Zap className="w-3 h-3" />,
    drafted: <MessageSquare className="w-3 h-3" />,
    posted: <CheckCircle2 className="w-3 h-3" />,
  }

  return (
    <div
      onClick={onClick}
      className={cn(
        "group relative p-4 bg-card rounded-lg border transition-all cursor-pointer",
        "hover:shadow-md hover:border-primary/50",
        isSelected && "border-primary shadow-md",
        tweet.flags?.toxicity && "border-red-200 bg-red-50/50"
      )}
    >
      {/* Tweet content */}
      <div className="flex gap-3">
        {/* Avatar placeholder */}
        <div className="flex-shrink-0">
          <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
            <span className="text-sm font-medium text-muted-foreground">
              {tweet.authorHandle.charAt(1).toUpperCase()}
            </span>
          </div>
        </div>

        {/* Main content */}
        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-start justify-between gap-2 mb-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-semibold text-sm">{tweet.authorHandle}</span>
              <span className="text-xs text-muted-foreground">
                {formatDistanceToNow(new Date(tweet.createdAt), { addSuffix: true })}
              </span>
              
              {/* Status badge */}
              <span
                className={cn(
                  "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium",
                  statusColors[tweet.status]
                )}
              >
                {statusIcons[tweet.status]}
                {tweet.status}
              </span>
            </div>

            {/* Relevance score */}
            {tweet.relevanceScore !== undefined && (
              <div className="flex items-center gap-1">
                <div className="w-12 h-1.5 bg-muted rounded-full overflow-hidden">
                  <div
                    className={cn(
                      "h-full transition-all",
                      tweet.relevanceScore > 0.7 ? "bg-green-500" : 
                      tweet.relevanceScore > 0.4 ? "bg-yellow-500" : "bg-red-500"
                    )}
                    style={{ width: `${tweet.relevanceScore * 100}%` }}
                  />
                </div>
                <span className="text-xs text-muted-foreground">
                  {Math.round(tweet.relevanceScore * 100)}%
                </span>
              </div>
            )}
          </div>

          {/* Tweet text preview */}
          <p className="text-sm text-foreground line-clamp-2">{tweet.textPreview}</p>

          {/* Flags and indicators */}
          <div className="flex items-center gap-3 mt-2">
            {tweet.hasDraft && (
              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                <MessageSquare className="w-3 h-3" />
                Has draft
              </span>
            )}
            
            {tweet.flags?.toxicity && (
              <span className="inline-flex items-center gap-1 text-xs text-red-600">
                <AlertCircle className="w-3 h-3" />
                Potentially toxic
              </span>
            )}
            
            {tweet.flags?.duplicate && (
              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                <AlertCircle className="w-3 h-3" />
                Duplicate
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}