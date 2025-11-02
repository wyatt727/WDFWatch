import { Metadata } from 'next'
import { notFound } from 'next/navigation'
import { prisma } from '@/lib/prisma'
import { PipelineVisualizer } from '@/components/pipeline/PipelineVisualizer'
import { KeywordsEditor } from '@/components/episodes/KeywordsEditor'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ArrowLeft, Calendar, FileText } from 'lucide-react'
import Link from 'next/link'

interface EpisodePageProps {
  params: { id: string }
}

export async function generateMetadata({ params }: EpisodePageProps): Promise<Metadata> {
  const episode = await prisma.podcastEpisode.findUnique({
    where: { id: parseInt(params.id) }
  })
  
  return {
    title: episode ? `${episode.title} | Episodes` : 'Episode Not Found',
    description: episode ? `Manage pipeline for ${episode.title}` : 'Episode not found'
  }
}

export default async function EpisodePage({ params }: EpisodePageProps) {
  const episodeId = parseInt(params.id)
  
  const episode = await prisma.podcastEpisode.findUnique({
    where: { id: episodeId },
    select: {
      id: true,
      title: true,
      status: true,
      uploadedAt: true,
      videoUrl: true,
      pipelineType: true,
      pipelineConfiguration: true,
      keywords_entries: {
        where: { enabled: true },
        select: {
          keyword: true,
          weight: true
        },
        orderBy: [
          { weight: 'desc' },
          { keyword: 'asc' }
        ]
      },
      _count: {
        select: {
          tweets: true,
          keywords_entries: true
        }
      }
    }
  })
  
  if (!episode) {
    notFound()
  }
  
  const statusColors: Record<string, string> = {
    no_transcript: 'secondary',
    transcript_uploaded: 'default',
    processing: 'default',
    completed: 'success',
    error: 'destructive'
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/episodes">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold">{episode.title}</h1>
            <div className="flex items-center gap-4 mt-2 text-muted-foreground">
              <div className="flex items-center gap-1">
                <Calendar className="h-4 w-4" />
                <span className="text-sm">
                  Uploaded {new Date(episode.uploadedAt).toLocaleDateString()}
                </span>
              </div>
              <Badge variant={statusColors[episode.status] as any}>
                {episode.status.replace('_', ' ')}
              </Badge>
            </div>
          </div>
        </div>
      </div>
      
      {/* Episode Info */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Keywords</CardTitle>
          </CardHeader>
          <CardContent>
            <KeywordsEditor
              episodeId={episode.id}
              initialKeywords={episode.keywords_entries}
              episodeType={(episode.pipelineConfiguration as any)?.metadata?.episodeType}
            />
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Tweets</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{episode._count.tweets}</p>
            <p className="text-xs text-muted-foreground">Discovered</p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Episode Files</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <p className="text-sm">
                {episode.videoUrl ? 'Video URL configured' : 'No video URL'}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
      
      {/* Pipeline Visualizer */}
      <Card>
        <CardHeader>
          <CardTitle>Processing Pipeline</CardTitle>
          <CardDescription>
            Manage files and run pipeline stages for this episode
          </CardDescription>
        </CardHeader>
        <CardContent>
          <PipelineVisualizer 
            episodeId={episode.id} 
            episodeTitle={episode.title}
            pipelineType={(episode.pipelineType as 'claude' | 'legacy') || 'legacy'}
          />
        </CardContent>
      </Card>
    </div>
  )
}