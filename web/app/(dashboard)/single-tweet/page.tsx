/**
 * Single Tweet Response Interface
 * 
 * Allows users to respond to specific tweets outside the normal pipeline.
 * Features:
 * - Direct URL input with validation
 * - Tweet preview before generation
 * - Episode context selection
 * - Real-time response generation
 * - Character count with visual feedback
 * - Response history tracking
 * 
 * UX Optimizations:
 * - Auto-detect tweet URLs from clipboard
 * - Live character counting
 * - Response templates/suggestions
 * - Keyboard shortcuts (Cmd+Enter to submit)
 * - Visual feedback during generation
 * - Undo/redo in editor
 */

'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { formatDistanceToNow } from 'date-fns'
import {
  Link,
  Send,
  Loader2,
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  Copy,
  ExternalLink,
  Hash,
  User,
  MessageSquare,
  Zap,
  History,
  FileText,
  Sparkles,
  ChevronRight,
  Edit3,
  Save,
  X,
  Trash2,
  RefreshCw,
  Heart,
  Repeat,
  MessageCircle,
  Info
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Progress } from '@/components/ui/progress'
import { Separator } from '@/components/ui/separator'
import { useToast } from '@/components/ui/use-toast'
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
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'

// Types
interface TweetData {
  twitterId: string
  authorHandle: string
  authorName?: string
  fullText: string
  metrics?: {
    likes: number
    retweets: number
    replies: number
  }
  needsFetch: boolean
}

interface ResponseRequest {
  id: number
  tweetUrl: string
  tweetId: string
  tweetText?: string
  requestedBy?: string
  requestedAt: string
  responseGenerated?: string
  status: 'pending' | 'generated' | 'approved' | 'published' | 'failed'
  episodeTitle?: string
  approved: boolean
  published: boolean
  errorMessage?: string
}

interface Episode {
  id: number
  title: string
  publishedAt?: string
  summaryText?: string
}

// URL validation regex
const TWEET_URL_REGEX = /^https?:\/\/(twitter\.com|x\.com)\/[^\/]+\/status\/\d+/i

// Response templates
const responseTemplates = [
  {
    name: 'Thoughtful Agreement',
    template: "Great point! Rick Becker explores this exact issue in the WDF podcast. ",
    category: 'engagement'
  },
  {
    name: 'Educational',
    template: "This relates to what we discussed about [topic] in our latest episode. ",
    category: 'educational'
  },
  {
    name: 'Question Response',
    template: "That's a fascinating question. In the WDF podcast, we dive into ",
    category: 'question'
  },
  {
    name: 'Resource Share',
    template: "If you're interested in this topic, check out our episode on ",
    category: 'resource'
  }
]

export default function SingleTweetPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  
  // State
  const [tweetUrl, setTweetUrl] = useState('')
  const [isValidUrl, setIsValidUrl] = useState(false)
  const [tweetData, setTweetData] = useState<TweetData | null>(null)
  const [selectedEpisode, setSelectedEpisode] = useState<string>('latest')
  const [responseText, setResponseText] = useState('')
  const [isEditing, setIsEditing] = useState(false)
  const [showTemplates, setShowTemplates] = useState(false)
  const [currentRequestId, setCurrentRequestId] = useState<number | null>(null)
  
  // Character count and color
  const charCount = responseText.length
  const charCountColor = charCount > 280 ? 'text-red-600' : 
                         charCount > 250 ? 'text-yellow-600' : 
                         'text-muted-foreground'
  
  // SSE removed: FastAPI endpoint returns synchronous response for single tweet generation.

  // Validate URL on change
  useEffect(() => {
    setIsValidUrl(TWEET_URL_REGEX.test(tweetUrl))
  }, [tweetUrl])

  // Auto-detect URL from clipboard
  useEffect(() => {
    const checkClipboard = async () => {
      try {
        const text = await navigator.clipboard.readText()
        if (TWEET_URL_REGEX.test(text) && !tweetUrl) {
          setTweetUrl(text)
          toast({
            title: 'Tweet URL detected',
            description: 'Pasted from clipboard'
          })
        }
      } catch (err) {
        // Clipboard access denied or not available
      }
    }
    checkClipboard()
  }, [])

  // Fetch episodes
  const { data: episodes } = useQuery({
    queryKey: ['episodes'],
    queryFn: async () => {
      const response = await fetch('/api/episodes')
      if (!response.ok) throw new Error('Failed to fetch episodes')
      return response.json()
    }
  })

  // Fetch response history
  const { data: responseHistory } = useQuery({
    queryKey: ['response-requests'],
    queryFn: async () => {
      const response = await fetch('/api/single-tweet/requests')
      if (!response.ok) throw new Error('Failed to fetch history')
      return response.json()
    }
  })

  // Analyze tweet mutation
  const analyzeTweetMutation = useMutation({
    mutationFn: async (url: string) => {
      const response = await fetch('/api/single-tweet/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tweetUrl: url })
      })
      if (!response.ok) throw new Error('Failed to analyze tweet')
      return response.json()
    },
    onSuccess: (data) => {
      setTweetData(data.tweet)
      if (data.existingDrafts?.length > 0) {
        toast({
          title: 'Existing responses found',
          description: `${data.existingDrafts.length} draft(s) already exist for this tweet`
        })
      }
    },
    onError: () => {
      toast({
        title: 'Failed to analyze tweet',
        variant: 'destructive'
      })
    }
  })

  // Generate response mutation
  const generateResponseMutation = useMutation({
    mutationFn: async () => {
      const episodeId = selectedEpisode === 'latest' ? undefined : parseInt(selectedEpisode)
      const response = await fetch('/api/single-tweet/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tweetUrl,
          tweetText: tweetData?.fullText,
          episodeId,
          useLatestEpisode: selectedEpisode === 'latest'
        })
      })
      if (!response.ok) throw new Error('Failed to generate response')
      return response.json()
    },
    onSuccess: (data) => {
      setCurrentRequestId(data.requestId)
      toast({
        title: 'Generating response...',
        description: data.estimatedTime
      })
    },
    onError: () => {
      toast({
        title: 'Failed to generate response',
        variant: 'destructive'
      })
    }
  })

  // Approve response mutation
  const approveResponseMutation = useMutation({
    mutationFn: async ({ requestId, publishImmediately }: { requestId: number, publishImmediately: boolean }) => {
      const response = await fetch('/api/single-tweet/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requestId,
          editedResponse: isEditing ? responseText : undefined,
          publishImmediately
        })
      })
      if (!response.ok) throw new Error('Failed to approve response')
      return response.json()
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['response-requests'] })
      toast({
        title: data.status === 'published' ? 'Response published!' : 'Response approved!',
        description: `${data.response.length} characters`
      })
      // Reset form
      setTweetUrl('')
      setTweetData(null)
      setResponseText('')
      setIsEditing(false)
      setCurrentRequestId(null)
    },
    onError: () => {
      toast({
        title: 'Failed to approve response',
        variant: 'destructive'
      })
    }
  })

  // Handle analyze button click
  const handleAnalyze = () => {
    if (isValidUrl) {
      analyzeTweetMutation.mutate(tweetUrl)
    }
  }

  // Handle generate button click
  const handleGenerate = () => {
    if (tweetData) {
      generateResponseMutation.mutate()
    }
  }

  // Apply template
  const applyTemplate = (template: string) => {
    setResponseText(template)
    setShowTemplates(false)
    textareaRef.current?.focus()
  }

  // Copy response to clipboard
  const copyResponse = () => {
    navigator.clipboard.writeText(responseText)
    toast({
      title: 'Copied to clipboard'
    })
  }

  // Load previous response
  const loadPreviousResponse = (request: ResponseRequest) => {
    setTweetUrl(request.tweetUrl)
    if (request.responseGenerated) {
      setResponseText(request.responseGenerated)
    }
    setCurrentRequestId(request.id)
    analyzeTweetMutation.mutate(request.tweetUrl)
  }

  return (
    <TooltipProvider>
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold">Single Tweet Response</h1>
          <p className="text-muted-foreground">
            Generate targeted responses for specific tweets
          </p>
        </div>

        <div className="grid grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="col-span-2 space-y-6">
            {/* URL Input */}
            <Card>
              <CardHeader>
                <CardTitle>Tweet URL</CardTitle>
                <CardDescription>
                  Paste a Twitter/X URL to generate a response
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Link className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-4 h-4" />
                    <Input
                      placeholder="https://x.com/username/status/..."
                      value={tweetUrl}
                      onChange={(e) => setTweetUrl(e.target.value)}
                      className={cn(
                        "pl-9",
                        tweetUrl && !isValidUrl && "border-red-500"
                      )}
                    />
                  </div>
                  <Button
                    onClick={handleAnalyze}
                    disabled={!isValidUrl || analyzeTweetMutation.isPending}
                  >
                    {analyzeTweetMutation.isPending ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      'Analyze'
                    )}
                  </Button>
                </div>
                
                {tweetUrl && !isValidUrl && (
                  <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>
                      Please enter a valid Twitter/X URL
                    </AlertDescription>
                  </Alert>
                )}
              </CardContent>
            </Card>

            {/* Tweet Preview */}
            {tweetData && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle>Tweet Preview</CardTitle>
                      {tweetData.needsFetch && (
                        <Badge variant="outline">
                          <AlertCircle className="w-3 h-3 mr-1" />
                          Will fetch from API
                        </Badge>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
                        <User className="w-5 h-5" />
                      </div>
                      <div className="flex-1 space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold">{tweetData.authorName || 'User'}</span>
                          <span className="text-muted-foreground">@{tweetData.authorHandle}</span>
                        </div>
                        <p className="text-sm">{tweetData.fullText}</p>
                        {tweetData.metrics && (
                          <div className="flex items-center gap-4 pt-2 text-sm text-muted-foreground">
                            <span className="flex items-center gap-1">
                              <Heart className="w-4 h-4" />
                              {tweetData.metrics.likes}
                            </span>
                            <span className="flex items-center gap-1">
                              <Repeat className="w-4 h-4" />
                              {tweetData.metrics.retweets}
                            </span>
                            <span className="flex items-center gap-1">
                              <MessageCircle className="w-4 h-4" />
                              {tweetData.metrics.replies}
                            </span>
                          </div>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        asChild
                      >
                        <a
                          href={tweetUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* Response Generation */}
            {tweetData && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle>Generate Response</CardTitle>
                      <div className="flex items-center gap-2">
                        <Select value={selectedEpisode} onValueChange={setSelectedEpisode}>
                          <SelectTrigger className="w-[200px]">
                            <SelectValue placeholder="Select episode" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="latest">Latest Episode</SelectItem>
                            {episodes?.episodes?.map((episode: Episode) => (
                              <SelectItem key={episode.id} value={episode.id.toString()}>
                                {episode.title}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Button
                          onClick={handleGenerate}
                          disabled={generateResponseMutation.isPending || !!responseText}
                        >
                          {generateResponseMutation.isPending ? (
                            <>
                              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                              Generating...
                            </>
                          ) : (
                            <>
                              <Sparkles className="w-4 h-4 mr-2" />
                              Generate
                            </>
                          )}
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {responseText ? (
                      <>
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <label className="text-sm font-medium">Response</label>
                            <div className="flex items-center gap-2">
                              {!isEditing && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => setIsEditing(true)}
                                >
                                  <Edit3 className="w-4 h-4 mr-1" />
                                  Edit
                                </Button>
                              )}
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={copyResponse}
                              >
                                <Copy className="w-4 h-4 mr-1" />
                                Copy
                              </Button>
                            </div>
                          </div>
                          <Textarea
                            ref={textareaRef}
                            value={responseText}
                            onChange={(e) => setResponseText(e.target.value)}
                            readOnly={!isEditing}
                            className={cn(
                              "min-h-[100px] resize-none",
                              !isEditing && "bg-muted cursor-default"
                            )}
                            placeholder="Response will appear here..."
                          />
                          <div className="flex items-center justify-between">
                            <span className={cn("text-sm", charCountColor)}>
                              {charCount}/280 characters
                            </span>
                            {charCount > 280 && (
                              <Alert variant="destructive" className="py-2">
                                <AlertDescription>
                                  Response exceeds Twitter's character limit
                                </AlertDescription>
                              </Alert>
                            )}
                          </div>
                        </div>
                        
                        <Separator />
                        
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            {isEditing && (
                              <>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => setShowTemplates(!showTemplates)}
                                >
                                  <FileText className="w-4 h-4 mr-1" />
                                  Templates
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => {
                                    setIsEditing(false)
                                    // Reset to original if needed
                                  }}
                                >
                                  Cancel
                                </Button>
                              </>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            <Button
                              variant="outline"
                              onClick={() => {
                                if (currentRequestId) {
                                  approveResponseMutation.mutate({
                                    requestId: currentRequestId,
                                    publishImmediately: false
                                  })
                                }
                              }}
                              disabled={!currentRequestId || charCount > 280}
                            >
                              <Save className="w-4 h-4 mr-2" />
                              Save Draft
                            </Button>
                            <Button
                              onClick={() => {
                                if (currentRequestId) {
                                  approveResponseMutation.mutate({
                                    requestId: currentRequestId,
                                    publishImmediately: true
                                  })
                                }
                              }}
                              disabled={!currentRequestId || charCount > 280}
                            >
                              <Send className="w-4 h-4 mr-2" />
                              Publish
                            </Button>
                          </div>
                        </div>
                        
                        {showTemplates && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            className="space-y-2"
                          >
                            <Separator />
                            <div className="space-y-2">
                              <p className="text-sm font-medium">Response Templates</p>
                              <div className="grid grid-cols-2 gap-2">
                                {responseTemplates.map((template) => (
                                  <Button
                                    key={template.name}
                                    variant="outline"
                                    size="sm"
                                    className="justify-start"
                                    onClick={() => applyTemplate(template.template)}
                                  >
                                    <ChevronRight className="w-3 h-3 mr-1" />
                                    {template.name}
                                  </Button>
                                ))}
                              </div>
                            </div>
                          </motion.div>
                        )}
                      </>
                    ) : (
                      <div className="flex flex-col items-center justify-center h-32 text-muted-foreground">
                        <MessageSquare className="w-8 h-8 mb-2" />
                        <p className="text-sm">Click "Generate" to create a response</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </div>

          {/* Sidebar - Response History */}
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <History className="w-4 h-4" />
                  Recent Responses
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {responseHistory?.requests?.length > 0 ? (
                    responseHistory.requests.slice(0, 10).map((request: ResponseRequest) => (
                      <button
                        key={request.id}
                        onClick={() => loadPreviousResponse(request)}
                        className="w-full text-left p-3 rounded-lg border hover:bg-accent transition-colors"
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">
                              @{request.tweetId?.substring(0, 15)}...
                            </p>
                            {request.tweetText && (
                              <p className="text-xs text-muted-foreground truncate">
                                {request.tweetText.substring(0, 50)}...
                              </p>
                            )}
                            <p className="text-xs text-muted-foreground mt-1">
                              {formatDistanceToNow(new Date(request.requestedAt), { addSuffix: true })}
                            </p>
                          </div>
                          <Badge
                            variant={
                              request.status === 'published' ? 'default' :
                              request.status === 'approved' ? 'secondary' :
                              request.status === 'failed' ? 'destructive' :
                              'outline'
                            }
                            className="text-xs"
                          >
                            {request.status}
                          </Badge>
                        </div>
                      </button>
                    ))
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      <Clock className="w-8 h-8 mx-auto mb-2" />
                      <p className="text-sm">No response history</p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Tips */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Info className="w-4 h-4" />
                  Tips
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  <li className="flex items-start gap-2">
                    <span className="text-primary">•</span>
                    Keep responses under 280 characters
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-primary">•</span>
                    Use episode context for relevant responses
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-primary">•</span>
                    Edit generated responses for personal touch
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-primary">•</span>
                    Templates help maintain consistency
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-primary">•</span>
                    Preview before publishing
                  </li>
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </TooltipProvider>
  )
}