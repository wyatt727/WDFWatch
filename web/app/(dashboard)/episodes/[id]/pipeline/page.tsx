/**
 * Episode Pipeline Management Page
 * 
 * Integrates the new unified pipeline controller with the existing episode management system.
 * Features:
 * - Pre-flight validation
 * - Visual pipeline flow
 * - Real-time progress tracking
 * - Error recovery management
 * - Unified pipeline controls
 */

import { Suspense } from "react"
import { notFound } from "next/navigation"
import { prisma } from "@/lib/db"
import { UnifiedPipelineController } from "@/components/pipeline/UnifiedPipelineController"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ArrowLeft } from "lucide-react"
import Link from "next/link"

interface PipelinePageProps {
  params: {
    id: string
  }
}

async function getEpisodeWithPipelineStatus(episodeId: number) {
  try {
    const episode = await prisma.podcastEpisode.findUnique({
      where: { id: episodeId },
      include: {
        pipelineRuns: {
          orderBy: { startedAt: 'desc' },
          take: 1,
          include: {
            errors: {
              orderBy: { timestamp: 'desc' },
              take: 5,
            },
          },
        },
        pipelineValidations: {
          orderBy: { createdAt: 'desc' },
          take: 1,
        },
        _count: {
          select: {
            tweets: true,
            pipelineErrors: true,
            pipelineRuns: true,
          },
        },
      },
    })

    if (!episode) return null

    // Get current pipeline status
    const latestRun = episode.pipelineRuns[0]
    const isRunning = latestRun?.status === 'running' || latestRun?.status === 'validating'
    
    // Get validation status
    const latestValidation = episode.pipelineValidations[0]
    
    // Load progress if pipeline is running
    let progress = null
    if (isRunning && latestRun) {
      // This would typically load from the progress tracker
      // For now, we'll use the stored metadata
      progress = latestRun.metadata || null
    }

    return {
      episode,
      pipelineStatus: {
        isRunning,
        latestRun,
        validation: latestValidation,
        progress,
        errorCount: episode._count.pipelineErrors,
        totalRuns: episode._count.pipelineRuns,
        tweetCount: episode._count.tweets,
      },
    }
  } catch (error) {
    console.error('Error fetching episode pipeline status:', error)
    return null
  }
}

function PipelinePageSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-8 w-48 bg-gray-200 rounded animate-pulse" />
      <div className="h-32 bg-gray-200 rounded animate-pulse" />
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-24 bg-gray-200 rounded animate-pulse" />
        ))}
      </div>
    </div>
  )
}

export default async function PipelinePage({ params }: PipelinePageProps) {
  const episodeId = parseInt(params.id)
  
  if (isNaN(episodeId)) {
    notFound()
  }

  const data = await getEpisodeWithPipelineStatus(episodeId)
  
  if (!data) {
    notFound()
  }

  const { episode, pipelineStatus } = data

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link 
          href="/episodes" 
          className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Episodes
        </Link>
      </div>

      {/* Episode Info */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-xl">{episode.title}</CardTitle>
              <p className="text-muted-foreground mt-1">
                Episode {episode.id} • Created {episode.createdAt.toLocaleDateString()}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={episode.pipelineType === 'claude' ? 'default' : 'secondary'}>
                {episode.pipelineType === 'claude' ? 'Claude Pipeline' : 'Legacy Pipeline'}
              </Badge>
              {episode.status && (
                <Badge variant="outline">
                  {episode.status}
                </Badge>
              )}
            </div>
          </div>
        </CardHeader>
        
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <div className="font-medium">{pipelineStatus.tweetCount}</div>
              <div className="text-muted-foreground">Tweets Processed</div>
            </div>
            <div>
              <div className="font-medium">{pipelineStatus.totalRuns}</div>
              <div className="text-muted-foreground">Pipeline Runs</div>
            </div>
            <div>
              <div className="font-medium">{pipelineStatus.errorCount}</div>
              <div className="text-muted-foreground">Total Errors</div>
            </div>
            <div>
              <div className="font-medium">
                {episode.transcriptText ? `${Math.round(episode.transcriptText.length / 1000)}K` : 'N/A'}
              </div>
              <div className="text-muted-foreground">Transcript Size</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Pipeline Controller */}
      <Suspense fallback={<PipelinePageSkeleton />}>
        <UnifiedPipelineController
          episodeId={episodeId}
          pipelineType={episode.pipelineType as 'claude' | 'legacy'}
          initialStatus={pipelineStatus}
        />
      </Suspense>
    </div>
  )
}

export async function generateMetadata({ params }: PipelinePageProps) {
  const episodeId = parseInt(params.id)
  
  if (isNaN(episodeId)) {
    return {
      title: 'Episode Not Found',
    }
  }

  try {
    const episode = await prisma.podcastEpisode.findUnique({
      where: { id: episodeId },
      select: { title: true },
    })

    return {
      title: episode ? `Pipeline - ${episode.title}` : 'Episode Not Found',
      description: `Manage pipeline execution for episode ${episodeId}`,
    }
  } catch (error) {
    return {
      title: 'Episode Pipeline',
    }
  }
}