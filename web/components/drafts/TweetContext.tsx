/**
 * TweetContext component for displaying tweet in draft review
 * Shows full tweet content with author info and metadata
 * Interacts with: DraftReviewPanel parent component
 */

import { TweetDetail } from "@/lib/types"
import { formatDistanceToNow } from "date-fns"
import { ExternalLink, MessageCircle, Heart, Repeat2 } from "lucide-react"
import { Button } from "@/components/ui/button"

interface TweetContextProps {
  tweet: Partial<TweetDetail>
}

export function TweetContext({ tweet }: TweetContextProps) {
  if (!tweet) {
    return (
      <div className="p-4 border rounded-lg bg-muted">
        <p className="text-muted-foreground">Loading tweet...</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Main tweet */}
      <div className="p-4 border rounded-lg bg-card">
        {/* Author info */}
        <div className="flex items-start gap-3 mb-3">
          <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center flex-shrink-0">
            <span className="text-lg font-medium text-muted-foreground">
              {tweet.authorHandle?.charAt(1).toUpperCase()}
            </span>
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="font-semibold">{tweet.authorHandle}</span>
              {tweet.createdAt && (
                <span className="text-sm text-muted-foreground">
                  · {formatDistanceToNow(new Date(tweet.createdAt), { addSuffix: true })}
                </span>
              )}
            </div>
          </div>
          {tweet.id && (
            <Button variant="ghost" size="sm" asChild>
              <a
                href={`https://twitter.com/${tweet.authorHandle?.slice(1)}/status/${tweet.id}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                <ExternalLink className="h-4 w-4" />
              </a>
            </Button>
          )}
        </div>

        {/* Tweet text */}
        <p className="text-base whitespace-pre-wrap mb-3">
          {tweet.fullText || tweet.textPreview}
        </p>

        {/* Engagement metrics */}
        <div className="flex items-center gap-6 text-sm text-muted-foreground">
          <span className="flex items-center gap-1">
            <MessageCircle className="w-4 h-4" />
            {tweet.replyCount || 0}
          </span>
          <span className="flex items-center gap-1">
            <Repeat2 className="w-4 h-4" />
            {tweet.retweetCount || 0}
          </span>
          <span className="flex items-center gap-1">
            <Heart className="w-4 h-4" />
            {tweet.likeCount || 0}
          </span>
        </div>
      </div>

      {/* Thread context if available */}
      {tweet.thread && tweet.thread.length > 0 && (
        <div className="space-y-3">
          <h4 className="font-medium text-sm">Thread Context</h4>
          {tweet.thread.map((item, index) => (
            <div key={item.id || index} className="p-3 border rounded-lg bg-muted/50">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-medium">{item.authorHandle}</span>
              </div>
              <p className="text-sm">{item.text}</p>
            </div>
          ))}
        </div>
      )}

      {/* Related context snippets */}
      {tweet.contextSnippets && tweet.contextSnippets.length > 0 && (
        <div className="space-y-3">
          <h4 className="font-medium text-sm">Related Episode Context</h4>
          {tweet.contextSnippets.map((snippet, idx) => (
            <div key={idx} className="p-3 border rounded-lg bg-muted/50">
              <p className="text-sm mb-1">{snippet.text}</p>
              <div className="text-xs text-muted-foreground">
                Relevance: {Math.round(snippet.relevance * 100)}%
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Classification info */}
      {tweet.classificationRationale && (
        <div className="p-3 border rounded-lg bg-muted/50">
          <h4 className="font-medium text-sm mb-1">Classification Rationale</h4>
          <p className="text-sm text-muted-foreground">
            {tweet.classificationRationale}
          </p>
        </div>
      )}
    </div>
  )
}