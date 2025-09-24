/**
 * Manual Scrape Page
 * Allows users to manually trigger tweet scraping with custom parameters
 * 
 * Related files:
 * - /web/app/api/scraping/trigger/route.ts (API endpoint for triggering scraping)
 * - /web/app/api/settings/scraping/route.ts (Settings API)
 * - /web/app/api/episodes/route.ts (Episodes API)
 */

'use client'

import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Slider } from '@/components/ui/slider'
import { useToast } from '@/components/ui/use-toast'
import { useRouter } from 'next/navigation'
import { AlertCircle, Loader2, Search, Info, Zap } from 'lucide-react'
import { TwitterQuotaMonitor } from '@/components/quota/TwitterQuotaMonitor'

interface ScrapingSettings {
  maxTweets: number
  maxResultsPerKeyword: number
  daysBack: number
  minLikes: number
  minRetweets: number
  minReplies: number
  excludeReplies: boolean
  excludeRetweets: boolean
  language: string
}

export default function ManualScrapePage() {
  const queryClient = useQueryClient()
  const router = useRouter()
  const { toast } = useToast()
  const [isScraping, setIsScraping] = useState(false)
  const [scrapingProgress, setScrapingProgress] = useState<string | null>(null)
  const [keywords, setKeywords] = useState('')
  const [targetTweets, setTargetTweets] = useState(100)
  const [daysBack, setDaysBack] = useState(7)

  // Fetch current settings for defaults
  const { data: settings } = useQuery<ScrapingSettings>({
    queryKey: ['scraping-settings'],
    queryFn: async () => {
      const res = await fetch('/api/settings/scraping')
      if (!res.ok) throw new Error('Failed to fetch settings')
      return res.json()
    },
  })

  // Validate keywords input
  const keywordList = keywords.split(',').map(k => k.trim()).filter(k => k)
  const isValid = keywordList.length > 0 && keywordList.length <= 5
  const estimatedApiCalls = Math.ceil(targetTweets / 100) * keywordList.length


  // Trigger focused scraping mutation
  const triggerScrapingMutation = useMutation({
    mutationFn: async (params: any) => {
      // This now waits for scraping to complete on the backend
      const res = await fetch('/api/scraping/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.error || 'Failed to trigger scraping')
      }

      return data
    },
    onSuccess: (data) => {
      // Scraping is now complete, not just started
      toast({
        title: '✅ Scraping Complete!',
        description: `Successfully collected tweets for: ${keywordList.join(', ')}. Redirecting to episode...`
      })

      setIsScraping(false)
      setScrapingProgress(null)

      // Invalidate queries first
      queryClient.invalidateQueries({ queryKey: ['episodes'] })
      queryClient.invalidateQueries({ queryKey: ['tweets'] })

      // Redirect to the episode page after a short delay
      if (data.episodeId) {
        setTimeout(() => {
          router.push(`/episodes/${data.episodeId}`)
        }, 1500)
      }
    },
    onError: (error: any) => {
      toast({
        title: 'Scraping Failed',
        description: error.message || 'An error occurred during scraping',
        variant: 'destructive'
      })
      setIsScraping(false)
      setScrapingProgress(null)

      // If there's an episode ID, offer to go to it anyway
      if ((error as any).episodeId) {
        toast({
          title: 'Episode Created',
          description: 'The episode was created but scraping failed. You can retry from the episode page.',
          action: {
            label: 'Go to Episode',
            onClick: () => router.push(`/episodes/${(error as any).episodeId}`)
          }
        } as any)
      }
    },
  })

  const handleFocusedScrape = () => {
    if (!isValid) {
      toast({
        title: 'Invalid keywords',
        description: 'Please enter 1-5 keywords separated by commas',
        variant: 'destructive'
      })
      return
    }

    setIsScraping(true)
    setScrapingProgress('Creating episode and starting scrape...')

    const params = {
      keywords: keywordList,
      targetTweetsPerKeyword: targetTweets,
      daysBack: daysBack,
      createEpisode: true,
      focusedMode: true,
      // Include other settings from defaults
      minLikes: settings?.minLikes || 0,
      minRetweets: settings?.minRetweets || 0,
      excludeReplies: settings?.excludeReplies || false,
      excludeRetweets: settings?.excludeRetweets || false,
    }

    // Start progress updates
    let progressIndex = 0
    const progressMessages = [
      'Setting up episode directory...',
      `Searching for tweets with keyword: ${keywordList[0]}...`,
      'Collecting tweets from Twitter API...',
      'Processing and filtering results...',
      'Saving tweets to episode...',
      'Finalizing episode data...'
    ]

    const progressInterval = setInterval(() => {
      if (progressIndex < progressMessages.length) {
        setScrapingProgress(progressMessages[progressIndex])
        progressIndex++
      }
    }, 3000)

    // Clean up interval when mutation completes
    triggerScrapingMutation.mutate(params, {
      onSettled: () => {
        clearInterval(progressInterval)
      }
    })
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Focused Keyword Search</h1>
        <p className="text-muted-foreground">
          Deep-dive into specific topics by scraping comprehensively for targeted keywords
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main Configuration - 2 columns */}
        <div className="lg:col-span-2 space-y-6">
          {/* Keyword Input */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="h-5 w-5 text-yellow-500" />
                Target Keywords
              </CardTitle>
              <CardDescription>
                Enter 1-5 keywords to search for. We'll gather tweets deeply for each keyword.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="keywords">Keywords (comma-separated)</Label>
                <Input
                  id="keywords"
                  placeholder="e.g., federalism, state sovereignty, tenth amendment"
                  value={keywords}
                  onChange={(e) => setKeywords(e.target.value)}
                  className={!isValid && keywords ? 'border-red-500' : ''}
                />
                <div className="flex items-center justify-between">
                  <p className="text-sm text-muted-foreground">
                    {keywordList.length} keyword{keywordList.length !== 1 ? 's' : ''} entered
                  </p>
                  {!isValid && keywords && (
                    <p className="text-sm text-red-500">
                      {keywordList.length === 0 ? 'Enter at least one keyword' : 'Maximum 5 keywords allowed'}
                    </p>
                  )}
                </div>
              </div>

              {/* Display parsed keywords */}
              {keywordList.length > 0 && (
                <div className="space-y-2">
                  <Label>Will search for:</Label>
                  <div className="flex flex-wrap gap-2">
                    {keywordList.map((kw, idx) => (
                      <Badge key={idx} variant="default" className="px-3 py-1">
                        {kw}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Search Parameters */}
          <Card>
            <CardHeader>
              <CardTitle>Search Parameters</CardTitle>
              <CardDescription>
                Configure how many tweets to gather and search window
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Tweet Count Slider */}
              <div className="space-y-3">
                <div className="flex justify-between">
                  <Label>Tweets per keyword</Label>
                  <span className="text-sm font-semibold">{targetTweets}</span>
                </div>
                <Slider
                  value={[targetTweets]}
                  onValueChange={(value) => setTargetTweets(value[0])}
                  min={50}
                  max={500}
                  step={50}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>50</span>
                  <span>250</span>
                  <span>500</span>
                </div>
              </div>

              {/* Days Back Slider */}
              <div className="space-y-3">
                <div className="flex justify-between">
                  <Label>Search window (days back)</Label>
                  <span className="text-sm font-semibold">{daysBack} days</span>
                </div>
                <Slider
                  value={[daysBack]}
                  onValueChange={(value) => setDaysBack(value[0])}
                  min={1}
                  max={30}
                  step={1}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>1 day</span>
                  <span>15 days</span>
                  <span>30 days</span>
                </div>
              </div>

              {/* Estimated API Usage */}
              <Alert>
                <Info className="h-4 w-4" />
                <AlertTitle>Estimated API Usage</AlertTitle>
                <AlertDescription>
                  <div className="mt-2 space-y-1">
                    <div>Total tweets to fetch: <strong>{keywordList.length * targetTweets}</strong></div>
                    <div>Estimated API calls: <strong>{estimatedApiCalls}</strong></div>
                    <div className="text-xs mt-2">
                      Each keyword will be searched individually for better tracking
                    </div>
                  </div>
                </AlertDescription>
              </Alert>
            </CardContent>
          </Card>

          {/* What Will Happen */}
          <Card className="border-blue-200 bg-blue-50/50 dark:border-blue-900 dark:bg-blue-950/20">
            <CardHeader>
              <CardTitle>What This Will Do</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                <li className="flex items-start gap-2">
                  <span className="text-blue-600 dark:text-blue-400">1.</span>
                  <span className="text-sm">
                    Create a new episode named <strong>"Keyword: {keywordList[0] || '[your keyword]'}"</strong>
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-blue-600 dark:text-blue-400">2.</span>
                  <span className="text-sm">
                    Use the general WDF podcast summary as context (no need to re-summarize)
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-blue-600 dark:text-blue-400">3.</span>
                  <span className="text-sm">
                    Scrape {targetTweets} tweets for each keyword ({keywordList.length * targetTweets} total)
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-blue-600 dark:text-blue-400">4.</span>
                  <span className="text-sm">
                    Skip directly to classification stage (summary already exists)
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-blue-600 dark:text-blue-400">5.</span>
                  <span className="text-sm">
                    Redirect you to the new episode page to continue the pipeline
                  </span>
                </li>
              </ul>
            </CardContent>
          </Card>
        </div>

        {/* Right Sidebar - Status & Action */}
        <div className="space-y-6">
          {/* Quota Monitor */}
          <TwitterQuotaMonitor
            refreshInterval={30000}
            onQuotaExhausted={() => {
              toast({
                title: "Quota Exhausted",
                description: "Twitter API quota has been exhausted. Scraping is disabled.",
                variant: "destructive"
              })
            }}
          />

          {/* Action Button */}
          <Card>
            <CardHeader>
              <CardTitle>Ready to Search?</CardTitle>
              <CardDescription>
                This will create a new episode and start scraping
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {keywordList.length > 0 && !isScraping && (
                <Alert>
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>
                    <strong>Episode name:</strong><br />
                    "Keyword: {keywordList[0]}"
                  </AlertDescription>
                </Alert>
              )}

              {isScraping && scrapingProgress && (
                <Alert className="border-blue-200 bg-blue-50/50 dark:border-blue-900 dark:bg-blue-950/20">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <AlertDescription>
                    <strong>Progress:</strong><br />
                    {scrapingProgress}
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
            <CardFooter>
              <Button
                className="w-full"
                size="lg"
                onClick={handleFocusedScrape}
                disabled={!isValid || isScraping || triggerScrapingMutation.isPending}
              >
                {isScraping ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {scrapingProgress || 'Processing...'}
                  </>
                ) : (
                  <>
                    <Search className="mr-2 h-4 w-4" />
                    Start Focused Search
                  </>
                )}
              </Button>
            </CardFooter>
          </Card>

          {/* Help Text */}
          <Card className="border-muted">
            <CardHeader>
              <CardTitle className="text-sm">Tips for Best Results</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <p className="text-xs text-muted-foreground">
                • Use specific, targeted keywords for best results
              </p>
              <p className="text-xs text-muted-foreground">
                • Multi-word phrases work well (e.g., "state sovereignty")
              </p>
              <p className="text-xs text-muted-foreground">
                • Start with 100-200 tweets to test relevance
              </p>
              <p className="text-xs text-muted-foreground">
                • Recent tweets (1-7 days) tend to have more engagement
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}