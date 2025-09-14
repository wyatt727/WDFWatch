/**
 * Scraping Settings Page
 * 
 * Provides comprehensive controls for tweet scraping:
 * - Configure scraping parameters (count, date range, engagement thresholds)
 * - Manage keywords via embedded KeywordManager
 * - Manually trigger scraping with custom parameters
 * - View scraping history and status
 * 
 * Related files:
 * - /web/app/api/settings/scraping/route.ts (Settings API)
 * - /web/app/api/scraping/trigger/route.ts (Manual trigger API)
 * - /web/components/keywords/KeywordManager.tsx (Keyword management)
 * - /src/wdf/tasks/scrape.py (Python scraping task)
 */

'use client'

import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useToast } from '@/components/ui/use-toast'
import { KeywordManager } from '@/components/keywords/KeywordManager'
import { 
  Settings, 
  Save, 
  Clock,
  Hash,
  Heart,
  Repeat2,
  MessageSquare,
  Globe,
  Search,
  Loader2,
} from 'lucide-react'

interface ScrapingSettings {
  maxTweets: number
  maxResultsPerKeyword: number  // New: Results per individual keyword search
  daysBack: number
  minLikes: number
  minRetweets: number
  minReplies: number
  excludeReplies: boolean
  excludeRetweets: boolean
  language: string
}

export default function ScrapingSettingsPage() {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [selectedEpisodeId, setSelectedEpisodeId] = useState<string>('all')
  
  // Local form state
  const [formSettings, setFormSettings] = useState<ScrapingSettings>({
    maxTweets: 100,
    maxResultsPerKeyword: 10,  // Conservative default (NOT 100!)
    daysBack: 7,
    minLikes: 0,
    minRetweets: 0,
    minReplies: 0,
    excludeReplies: false,
    excludeRetweets: false,
    language: 'en'
  })

  // Fetch current settings
  const { data: settings, isLoading: isLoadingSettings } = useQuery<ScrapingSettings>({
    queryKey: ['scraping-settings'],
    queryFn: async () => {
      const res = await fetch('/api/settings/scraping')
      if (!res.ok) throw new Error('Failed to fetch settings')
      return res.json()
    },
  })
  
  // Sync fetched settings with form state
  useEffect(() => {
    if (settings) {
      setFormSettings(settings)
    }
  }, [settings])

  // Fetch episodes for keyword filtering
  const { data: episodes = [] } = useQuery({
    queryKey: ['episodes'],
    queryFn: async () => {
      const res = await fetch('/api/episodes')
      if (!res.ok) throw new Error('Failed to fetch episodes')
      return res.json()
    },
  })

  // Update settings mutation
  const updateSettingsMutation = useMutation({
    mutationFn: async (newSettings: ScrapingSettings) => {
      const res = await fetch('/api/settings/scraping', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newSettings),
      })
      if (!res.ok) throw new Error('Failed to update settings')
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scraping-settings'] })
      toast({ title: 'Settings saved successfully' })
    },
    onError: () => {
      toast({ 
        title: 'Failed to save settings', 
        variant: 'destructive' 
      })
    },
  })

  if (isLoadingSettings) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    )
  }

  const handleSaveSettings = () => {
    updateSettingsMutation.mutate(formSettings)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Scraping Settings</h1>
        <p className="text-muted-foreground">
          Configure tweet scraping parameters and manage search keywords
        </p>
      </div>

      <Tabs defaultValue="settings" className="space-y-4">
        <TabsList>
          <TabsTrigger value="settings">Settings</TabsTrigger>
          <TabsTrigger value="keywords">Keywords</TabsTrigger>
        </TabsList>

        <TabsContent value="settings" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Scraping Configuration</CardTitle>
              <CardDescription>
                Set default parameters for tweet scraping
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Tweet Count and Date Range */}
              <div className="grid gap-6 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="maxTweets">
                    <Hash className="inline-block h-4 w-4 mr-2" />
                    Maximum Tweets Total: {formSettings.maxTweets}
                  </Label>
                  <Slider
                    id="maxTweets"
                    min={10}
                    max={1000}
                    step={10}
                    value={[formSettings.maxTweets]}
                    onValueChange={(v) => setFormSettings({...formSettings, maxTweets: v[0]})}
                  />
                  <p className="text-sm text-muted-foreground">
                    Total number of tweets to collect across ALL keywords. 
                    Search stops when this limit is reached, even if keywords remain.
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="daysBack">
                    <Clock className="inline-block h-4 w-4 mr-2" />
                    Days Back: {formSettings.daysBack}
                  </Label>
                  <Slider
                    id="daysBack"
                    min={1}
                    max={365}
                    step={1}
                    value={[formSettings.daysBack]}
                    onValueChange={(v) => setFormSettings({...formSettings, daysBack: v[0]})}
                  />
                  <p className="text-sm text-muted-foreground">
                    How far back to search for tweets
                  </p>
                </div>
              </div>

              {/* Results Per Keyword - Critical for API quota management */}
              <div className="space-y-2">
                <Label htmlFor="maxResultsPerKeyword">
                  <Search className="inline-block h-4 w-4 mr-2" />
                  Results Per Keyword: {formSettings.maxResultsPerKeyword}
                  {formSettings.maxResultsPerKeyword > 50 && (
                    <Badge variant="destructive" className="ml-2">High Quota Usage</Badge>
                  )}
                  {formSettings.maxResultsPerKeyword <= 10 && (
                    <Badge variant="default" className="ml-2">Conservative</Badge>
                  )}
                </Label>
                <Slider
                  id="maxResultsPerKeyword"
                  min={10}
                  max={100}
                  step={10}
                  value={[formSettings.maxResultsPerKeyword]}
                  onValueChange={(v) => setFormSettings({...formSettings, maxResultsPerKeyword: v[0]})}
                  className={formSettings.maxResultsPerKeyword > 50 ? 'accent-red-500' : ''}
                />
                <p className="text-sm text-muted-foreground">
                  How many results to fetch per individual keyword search.
                  <strong className="text-yellow-600"> ⚠️ Higher values consume API quota quickly!</strong>
                  {' '}With 10,000 monthly reads and 20 keywords: 10 results = 200 reads (2% quota), 
                  100 results = 2000 reads (20% quota).
                  <br />
                  <strong>Note:</strong> Keywords are searched by weight priority (highest first). 
                  If max tweets total is reached, lower-weight keywords won't be searched.
                </p>
              </div>

              <Separator />

              {/* Engagement Thresholds */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold">Engagement Thresholds</h3>
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="space-y-2">
                    <Label htmlFor="minLikes">
                      <Heart className="inline-block h-4 w-4 mr-2" />
                      Minimum Likes
                    </Label>
                    <Input
                      id="minLikes"
                      type="number"
                      min={0}
                      value={formSettings.minLikes}
                      onChange={(e) => setFormSettings({...formSettings, minLikes: parseInt(e.target.value) || 0})}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="minRetweets">
                      <Repeat2 className="inline-block h-4 w-4 mr-2" />
                      Minimum Retweets
                    </Label>
                    <Input
                      id="minRetweets"
                      type="number"
                      min={0}
                      value={formSettings.minRetweets}
                      onChange={(e) => setFormSettings({...formSettings, minRetweets: parseInt(e.target.value) || 0})}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="minReplies">
                      <MessageSquare className="inline-block h-4 w-4 mr-2" />
                      Minimum Replies
                    </Label>
                    <Input
                      id="minReplies"
                      type="number"
                      min={0}
                      value={formSettings.minReplies}
                      onChange={(e) => setFormSettings({...formSettings, minReplies: parseInt(e.target.value) || 0})}
                    />
                  </div>
                </div>
              </div>

              <Separator />

              {/* Filters */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold">Filters</h3>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label htmlFor="excludeReplies">Exclude Replies</Label>
                      <p className="text-sm text-muted-foreground">
                        Don&apos;t fetch tweets that are replies to other tweets
                      </p>
                    </div>
                    <Switch
                      id="excludeReplies"
                      checked={formSettings.excludeReplies}
                      onCheckedChange={(checked) => setFormSettings({...formSettings, excludeReplies: checked})}
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label htmlFor="excludeRetweets">Exclude Retweets</Label>
                      <p className="text-sm text-muted-foreground">
                        Don&apos;t fetch retweets
                      </p>
                    </div>
                    <Switch
                      id="excludeRetweets"
                      checked={formSettings.excludeRetweets}
                      onCheckedChange={(checked) => setFormSettings({...formSettings, excludeRetweets: checked})}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="language">
                      <Globe className="inline-block h-4 w-4 mr-2" />
                      Language
                    </Label>
                    <Select
                      value={formSettings.language}
                      onValueChange={(value) => setFormSettings({...formSettings, language: value})}
                    >
                      <SelectTrigger id="language">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="en">English</SelectItem>
                        <SelectItem value="es">Spanish</SelectItem>
                        <SelectItem value="fr">French</SelectItem>
                        <SelectItem value="de">German</SelectItem>
                        <SelectItem value="ja">Japanese</SelectItem>
                        <SelectItem value="all">All Languages</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>
            </CardContent>
            <CardFooter>
              <Button 
                onClick={handleSaveSettings} 
                disabled={updateSettingsMutation.isPending}
              >
                <Save className="mr-2 h-4 w-4" />
                Save Settings
              </Button>
            </CardFooter>
          </Card>
        </TabsContent>

        <TabsContent value="keywords" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Keyword Management</CardTitle>
              <CardDescription>
                Manage search keywords used for tweet scraping
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Episode Filter */}
              <div className="space-y-2">
                <Label>Filter by Episode</Label>
                <Select value={selectedEpisodeId} onValueChange={setSelectedEpisodeId}>
                  <SelectTrigger>
                    <SelectValue placeholder="All keywords" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All keywords</SelectItem>
                    {episodes.map((episode: any) => (
                      <SelectItem key={episode.id} value={episode.id.toString()}>
                        {episode.title}
                        {episode.keywordCount > 0 && (
                          <span className="ml-2 text-muted-foreground">
                            ({episode.keywordCount} keywords)
                          </span>
                        )}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              {/* Keyword Manager with episode filter */}
              <KeywordManager episodeId={selectedEpisodeId === 'all' ? undefined : selectedEpisodeId} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}