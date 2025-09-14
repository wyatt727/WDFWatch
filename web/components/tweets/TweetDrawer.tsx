/**
 * TweetDrawer component for displaying detailed tweet information
 * Shows full tweet content, thread context, and draft responses
 * Interacts with: InboxPage, API endpoints for tweet details
 */

import { useEffect, useState } from "react"
import { TweetDetail } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { formatDistanceToNow } from "date-fns"
import { MessageSquare, ExternalLink, Copy, CheckCircle2 } from "lucide-react"
import { cn } from "@/lib/utils"

interface TweetDrawerProps {
  tweetId: string | null
  open: boolean
  onClose: () => void
}

export function TweetDrawer({ tweetId, open, onClose }: TweetDrawerProps) {
  const [tweet, setTweet] = useState<TweetDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (tweetId && open) {
      setLoading(true)
      // TODO: Replace with actual API call
      fetch(`/api/tweets/${tweetId}`)
        .then((res) => res.json())
        .then((data) => {
          setTweet(data)
          setLoading(false)
        })
        .catch((err) => {
          console.error("Failed to fetch tweet:", err)
          setLoading(false)
        })
    }
  }, [tweetId, open])

  const handleCopyText = () => {
    if (tweet) {
      navigator.clipboard.writeText(tweet.fullText)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const statusColors = {
    unclassified: "bg-gray-100 text-gray-700",
    skipped: "bg-gray-100 text-gray-500",
    relevant: "bg-blue-100 text-blue-700",
    drafted: "bg-yellow-100 text-yellow-700",
    posted: "bg-green-100 text-green-700",
  }

  return (
    <Sheet open={open} onOpenChange={onClose}>
      <SheetContent className="w-full sm:max-w-xl overflow-y-auto">
        {loading && (
          <div className="flex items-center justify-center h-64">
            <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {tweet && !loading && (
          <>
            <SheetHeader>
              <SheetTitle className="flex items-center justify-between">
                <span>Tweet Details</span>
                <span
                  className={cn(
                    "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium",
                    statusColors[tweet.status]
                  )}
                >
                  {tweet.status}
                </span>
              </SheetTitle>
            </SheetHeader>

            <div className="mt-6 space-y-6">
              {/* Author info */}
              <div className="flex items-start gap-3">
                <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center">
                  <span className="text-lg font-medium text-muted-foreground">
                    {tweet.authorHandle.charAt(1).toUpperCase()}
                  </span>
                </div>
                <div>
                  <div className="font-semibold">{tweet.authorHandle}</div>
                  <div className="text-sm text-muted-foreground">
                    {formatDistanceToNow(new Date(tweet.createdAt), { addSuffix: true })}
                  </div>
                </div>
              </div>

              {/* Tweet content */}
              <div className="space-y-3">
                <p className="text-base whitespace-pre-wrap">{tweet.fullText}</p>
                
                {/* Action buttons */}
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCopyText}
                  >
                    {copied ? (
                      <>
                        <CheckCircle2 className="h-4 w-4 mr-2" />
                        Copied!
                      </>
                    ) : (
                      <>
                        <Copy className="h-4 w-4 mr-2" />
                        Copy text
                      </>
                    )}
                  </Button>
                  <Button variant="outline" size="sm" asChild>
                    <a
                      href={`https://twitter.com/${tweet.authorHandle.slice(1)}/status/${tweet.id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <ExternalLink className="h-4 w-4 mr-2" />
                      View on Twitter
                    </a>
                  </Button>
                </div>
              </div>

              {/* Tabs for additional info */}
              <Tabs defaultValue="context" className="w-full">
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="context">Context</TabsTrigger>
                  <TabsTrigger value="drafts">
                    Drafts ({tweet.drafts.length})
                  </TabsTrigger>
                  <TabsTrigger value="analysis">Analysis</TabsTrigger>
                </TabsList>

                <TabsContent value="context" className="space-y-4">
                  {tweet.thread && tweet.thread.length > 0 && (
                    <div className="space-y-3">
                      <h4 className="font-medium">Thread Context</h4>
                      {tweet.thread.map((item) => (
                        <div key={item.id} className="p-3 bg-muted rounded-lg">
                          <div className="text-sm font-medium mb-1">
                            {item.authorHandle}
                          </div>
                          <p className="text-sm">{item.text}</p>
                        </div>
                      ))}
                    </div>
                  )}
                  
                  {tweet.contextSnippets && tweet.contextSnippets.length > 0 && (
                    <div className="space-y-3">
                      <h4 className="font-medium">Related Context</h4>
                      {tweet.contextSnippets.map((snippet, idx) => (
                        <div key={idx} className="p-3 bg-muted rounded-lg">
                          <p className="text-sm">{snippet.text}</p>
                          <div className="text-xs text-muted-foreground mt-1">
                            Relevance: {Math.round(snippet.relevance * 100)}%
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="drafts" className="space-y-4">
                  {tweet.drafts.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      <MessageSquare className="h-12 w-12 mx-auto mb-3 opacity-50" />
                      <p>No drafts created yet</p>
                      <Button className="mt-4" size="sm">
                        Generate Draft Response
                      </Button>
                    </div>
                  ) : (
                    tweet.drafts.map((draft) => (
                      <div
                        key={draft.id}
                        className={cn(
                          "p-4 rounded-lg border",
                          draft.superseded && "opacity-60"
                        )}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium">
                            {draft.model} - v{draft.version}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {formatDistanceToNow(new Date(draft.createdAt), {
                              addSuffix: true,
                            })}
                          </span>
                        </div>
                        <p className="text-sm">{draft.text}</p>
                        {draft.styleScore !== undefined && (
                          <div className="flex gap-4 mt-2 text-xs text-muted-foreground">
                            <span>Style: {Math.round(draft.styleScore * 100)}%</span>
                            {draft.toxicityScore !== undefined && (
                              <span>Toxicity: {Math.round(draft.toxicityScore * 100)}%</span>
                            )}
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </TabsContent>

                <TabsContent value="analysis" className="space-y-4">
                  {tweet.relevanceScore !== undefined && (
                    <div>
                      <h4 className="font-medium mb-2">Relevance Analysis</h4>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-sm">Overall Score</span>
                          <span className="text-sm font-medium">
                            {Math.round(tweet.relevanceScore * 100)}%
                          </span>
                        </div>
                        <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
                          <div
                            className={cn(
                              "h-full transition-all",
                              tweet.relevanceScore > 0.7 ? "bg-green-500" : 
                              tweet.relevanceScore > 0.4 ? "bg-yellow-500" : "bg-red-500"
                            )}
                            style={{ width: `${tweet.relevanceScore * 100}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  )}
                  
                  {tweet.classificationRationale && (
                    <div>
                      <h4 className="font-medium mb-2">Classification Rationale</h4>
                      <p className="text-sm text-muted-foreground">
                        {tweet.classificationRationale}
                      </p>
                    </div>
                  )}
                </TabsContent>
              </Tabs>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}