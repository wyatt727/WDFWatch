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
import { Switch } from '@/components/ui/switch'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useToast } from '@/components/ui/use-toast'
import { AlertCircle, Loader2, Play, RefreshCw, Search } from 'lucide-react'
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

interface Episode {
  id: number
  title: string
  episodeNumber?: number
  _count?: {
    keywords_entries: number
  }
}

export default function ManualScrapePage() {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [isScraping, setIsScraping] = useState(false)
  const [manualKeywords, setManualKeywords] = useState('')
  const [useManualKeywords, setUseManualKeywords] = useState(false)
  const [selectedEpisodeId, setSelectedEpisodeId] = useState<string>('none')

  // Fetch current settings
  const { data: settings } = useQuery<ScrapingSettings>({
    queryKey: ['scraping-settings'],
    queryFn: async () => {
      const res = await fetch('/api/settings/scraping')
      if (!res.ok) throw new Error('Failed to fetch settings')
      return res.json()
    },
  })

  // Fetch episodes for manual scraping
  const { data: episodes = [], isLoading: isLoadingEpisodes } = useQuery<Episode[]>({
    queryKey: ['episodes'],
    queryFn: async () => {
      const res = await fetch('/api/episodes')
      if (!res.ok) throw new Error('Failed to fetch episodes')
      return res.json()
    },
  })

  // Fetch keywords for selected episode
  const { data: episodeKeywords = [] } = useQuery({
    queryKey: ['keywords', selectedEpisodeId],
    queryFn: async () => {
      if (!selectedEpisodeId || selectedEpisodeId === 'none') return []
      const res = await fetch(`/api/keywords?episodeId=${selectedEpisodeId}`)
      if (!res.ok) throw new Error('Failed to fetch keywords')
      const data = await res.json()
      return data.map((k: any) => k.keyword)
    },
    enabled: !!selectedEpisodeId && selectedEpisodeId !== 'none',
  })


  // Trigger manual scraping mutation
  const triggerScrapingMutation = useMutation({
    mutationFn: async (params: any) => {
      const res = await fetch('/api/scraping/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      })
      if (!res.ok) throw new Error('Failed to trigger scraping')
      return res.json()
    },
    onSuccess: (data) => {
      toast({ 
        title: 'Scraping started',
        description: `Run ID: ${data.runId}. Processing ${data.keywords} keywords.`
      })
      setIsScraping(false)
      // Invalidate tweets query to refresh the inbox
      queryClient.invalidateQueries({ queryKey: ['tweets'] })
    },
    onError: () => {
      toast({ 
        title: 'Failed to start scraping', 
        variant: 'destructive' 
      })
      setIsScraping(false)
    },
  })

  const handleManualScrape = () => {
    setIsScraping(true)
    
    const params: any = {
      episodeId: selectedEpisodeId === 'none' ? undefined : selectedEpisodeId,
      useEpisodeKeywords: !useManualKeywords,
    }

    if (useManualKeywords && manualKeywords) {
      params.keywords = manualKeywords.split(',').map(k => k.trim()).filter(k => k)
    }

    // Add scraping settings to params
    if (settings) {
      params.maxTweets = settings.maxTweets
      params.maxResultsPerKeyword = settings.maxResultsPerKeyword || 10
      params.daysBack = settings.daysBack
      params.minLikes = settings.minLikes
      params.minRetweets = settings.minRetweets
      params.excludeReplies = settings.excludeReplies
      params.excludeRetweets = settings.excludeRetweets
    }

    triggerScrapingMutation.mutate(params)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Manual Scrape</h1>
        <p className="text-muted-foreground">
          Trigger tweet scraping manually with custom parameters
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Left Column - Configuration */}
        <div className="space-y-6">
          {/* Episode Selection */}
          <Card>
            <CardHeader>
              <CardTitle>Episode Context</CardTitle>
              <CardDescription>
                Select an episode to use its keywords for scraping
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Select Episode</Label>
                <Select value={selectedEpisodeId} onValueChange={setSelectedEpisodeId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select an episode to use its keywords" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">No episode (use all keywords)</SelectItem>
                    {episodes.map((episode) => (
                      <SelectItem key={episode.id} value={episode.id.toString()}>
                        {episode.title}
                        {episode._count?.keywords_entries && (
                          <span className="ml-2 text-muted-foreground">
                            ({episode._count.keywords_entries} keywords)
                          </span>
                        )}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Display episode keywords */}
              {selectedEpisodeId && selectedEpisodeId !== 'none' && episodeKeywords.length > 0 && (
                <div className="space-y-2">
                  <Label>Episode Keywords</Label>
                  <div className="flex flex-wrap gap-2">
                    {episodeKeywords.slice(0, 10).map((keyword) => (
                      <Badge key={keyword} variant="secondary">
                        {keyword}
                      </Badge>
                    ))}
                    {episodeKeywords.length > 10 && (
                      <Badge variant="outline">
                        +{episodeKeywords.length - 10} more
                      </Badge>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Custom Keywords */}
          <Card>
            <CardHeader>
              <CardTitle>Custom Keywords</CardTitle>
              <CardDescription>
                Override episode keywords with custom search terms
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center space-x-2">
                <Switch
                  id="useManual"
                  checked={useManualKeywords}
                  onCheckedChange={setUseManualKeywords}
                />
                <Label htmlFor="useManual">Use custom keywords for this run</Label>
              </div>
              {useManualKeywords && (
                <div className="space-y-2">
                  <Label htmlFor="manualKeywords">Keywords</Label>
                  <Input
                    id="manualKeywords"
                    placeholder="keyword1, keyword2, keyword3"
                    value={manualKeywords}
                    onChange={(e) => setManualKeywords(e.target.value)}
                  />
                  <p className="text-sm text-muted-foreground">
                    Comma-separated list of keywords to search for
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column - Settings Summary & Action */}
        <div className="space-y-6">
          {/* Current Settings Summary */}
          <Card>
            <CardHeader>
              <CardTitle>Current Settings</CardTitle>
              <CardDescription>
                These settings will be used for the scraping run
              </CardDescription>
            </CardHeader>
            <CardContent>
              {settings ? (
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <div className="text-sm">
                      <span className="text-muted-foreground">Max Tweets Total:</span>{' '}
                      <Badge variant="secondary">{settings.maxTweets}</Badge>
                    </div>
                    <div className="text-sm">
                      <span className="text-muted-foreground">Per Keyword:</span>{' '}
                      <Badge variant={settings.maxResultsPerKeyword > 50 ? "destructive" : "secondary"}>
                        {settings.maxResultsPerKeyword || 10}
                      </Badge>
                    </div>
                    <div className="text-sm">
                      <span className="text-muted-foreground">Days Back:</span>{' '}
                      <Badge variant="secondary">{settings.daysBack}</Badge>
                    </div>
                    <div className="text-sm">
                      <span className="text-muted-foreground">Min Likes:</span>{' '}
                      <Badge variant="secondary">{settings.minLikes}</Badge>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <div className="text-sm">
                      <span className="text-muted-foreground">Min Retweets:</span>{' '}
                      <Badge variant="secondary">{settings.minRetweets}</Badge>
                    </div>
                    <div className="text-sm">
                      <span className="text-muted-foreground">Exclude Replies:</span>{' '}
                      <Badge variant="secondary">{settings.excludeReplies ? 'Yes' : 'No'}</Badge>
                    </div>
                    <div className="text-sm">
                      <span className="text-muted-foreground">Exclude Retweets:</span>{' '}
                      <Badge variant="secondary">{settings.excludeRetweets ? 'Yes' : 'No'}</Badge>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-center p-4">
                  <Loader2 className="h-6 w-6 animate-spin" />
                </div>
              )}
            </CardContent>
          </Card>

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

          {/* Scraping Action */}
          <Card>
            <CardHeader>
              <CardTitle>Start Scraping</CardTitle>
              <CardDescription>
                Begin scraping tweets with the configured parameters
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Manual Scraping</AlertTitle>
                <AlertDescription>
                  This will immediately start scraping tweets using the current settings.
                  The process will run in the background and you'll be notified when complete.
                </AlertDescription>
              </Alert>
            </CardContent>
            <CardFooter>
              <Button 
                className="w-full"
                size="lg"
                onClick={handleManualScrape} 
                disabled={isScraping || triggerScrapingMutation.isPending || isLoadingEpisodes}
              >
                {isScraping ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Starting Scrape...
                  </>
                ) : (
                  <>
                    <Search className="mr-2 h-4 w-4" />
                    Start Scraping
                  </>
                )}
              </Button>
            </CardFooter>
          </Card>
        </div>
      </div>
    </div>
  )
}