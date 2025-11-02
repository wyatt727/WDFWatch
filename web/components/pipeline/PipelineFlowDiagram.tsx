/**
 * Visual Pipeline Flow Diagram Component
 * 
 * Interactive visual representation of pipeline execution with:
 * - Real-time progress visualization
 * - Stage status indicators
 * - Time estimates and metrics
 * - Error states and recovery indicators
 * - Interactive controls for each stage
 */

"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { 
  CheckCircle2, 
  Clock, 
  AlertTriangle, 
  XCircle, 
  Play, 
  Pause, 
  RotateCcw,
  Zap,
  Database,
  Search,
  MessageSquare,
  CheckSquare,
  Settings,
  ChevronRight,
  Timer,
  TrendingUp,
  Activity,
  Cpu,
  HardDrive
} from "lucide-react"
import { cn } from "@/lib/utils"

export interface StageDefinition {
  id: string
  name: string
  description: string
  icon: React.ComponentType<{ className?: string }>
  estimatedDuration: number
  dependencies: string[]
  category: 'preparation' | 'processing' | 'generation' | 'review'
}

export interface StageProgress {
  id: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped' | 'paused'
  progress: number
  startedAt?: Date
  completedAt?: Date
  duration?: number
  remainingTime?: number
  retryCount: number
  errorMessage?: string
  metrics?: {
    itemsProcessed: number
    totalItems: number
    processingRate: number
    apiCallsUsed: number
    tokensUsed: number
    costIncurred: number
  }
}

export interface PipelineProgress {
  overallProgress: number
  currentStage?: StageProgress
  completedStages: StageProgress[]
  upcomingStages: StageProgress[]
  estimatedTimeRemaining: number
  estimatedCompletion: Date
  startedAt: Date
  elapsedTime: number
  throughputMetrics: {
    tweetsProcessed: number
    responsesGenerated: number
    averageProcessingTime: number
    apiCallsPerMinute: number
    tokensPerMinute: number
    costPerHour: number
  }
  resourceUsage: {
    memoryUsage: number
    cpuUsage: number
    diskIO: number
    networkIO: number
    activeConnections: number
  }
}

interface PipelineFlowDiagramProps {
  episodeId: number
  stages: StageDefinition[]
  progress?: PipelineProgress
  onStageAction?: (stageId: string, action: 'start' | 'retry' | 'skip') => void
  onPipelineAction?: (action: 'pause' | 'resume' | 'stop') => void
  isInteractive?: boolean
}

// Stage icons mapping
const STAGE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  validation: Settings,
  summarization: Database,
  fewshot: Zap,
  scraping: Search,
  classification: CheckSquare,
  response: MessageSquare,
  moderation: CheckCircle2,
}

// Stage categories for grouping
const STAGE_CATEGORIES = {
  preparation: { label: 'Preparation', color: 'bg-blue-100 border-blue-200' },
  processing: { label: 'Processing', color: 'bg-purple-100 border-purple-200' },
  generation: { label: 'Generation', color: 'bg-green-100 border-green-200' },
  review: { label: 'Review', color: 'bg-orange-100 border-orange-200' },
}

export function PipelineFlowDiagram({
  episodeId,
  stages,
  progress,
  onStageAction,
  onPipelineAction,
  isInteractive = true,
}: PipelineFlowDiagramProps) {
  const [selectedStage, setSelectedStage] = useState<string | null>(null)

  // Get stage status from progress
  const getStageStatus = (stageId: string): StageProgress | undefined => {
    if (progress?.currentStage?.id === stageId) return progress.currentStage
    return progress?.completedStages.find(s => s.id === stageId) ||
           progress?.upcomingStages.find(s => s.id === stageId)
  }

  // Format time duration
  const formatDuration = (minutes: number): string => {
    if (minutes < 1) return '<1m'
    if (minutes < 60) return `${Math.round(minutes)}m`
    const hours = Math.floor(minutes / 60)
    const mins = Math.round(minutes % 60)
    return `${hours}h ${mins}m`
  }

  // Format processing rate
  const formatRate = (rate: number): string => {
    if (rate < 1) return `${(rate * 60).toFixed(1)}/min`
    return `${rate.toFixed(1)}/min`
  }

  // Get status badge configuration
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return { variant: 'default' as const, className: 'bg-green-100 text-green-800 border-green-200' }
      case 'running':
        return { variant: 'default' as const, className: 'bg-blue-100 text-blue-800 border-blue-200 animate-pulse' }
      case 'failed':
        return { variant: 'destructive' as const, className: '' }
      case 'paused':
        return { variant: 'secondary' as const, className: 'bg-yellow-100 text-yellow-800 border-yellow-200' }
      case 'skipped':
        return { variant: 'outline' as const, className: 'text-gray-500' }
      default:
        return { variant: 'outline' as const, className: '' }
    }
  }

  // Get status icon
  const getStatusIcon = (status: string, className: string = "w-4 h-4") => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className={cn(className, "text-green-600")} />
      case 'running':
        return <Activity className={cn(className, "text-blue-600 animate-pulse")} />
      case 'failed':
        return <XCircle className={cn(className, "text-red-600")} />
      case 'paused':
        return <Pause className={cn(className, "text-yellow-600")} />
      case 'pending':
        return <Clock className={cn(className, "text-gray-400")} />
      default:
        return <Clock className={cn(className, "text-gray-400")} />
    }
  }

  // Group stages by category
  const stagesByCategory = stages.reduce((acc, stage) => {
    const category = stage.category
    if (!acc[category]) acc[category] = []
    acc[category].push(stage)
    return acc
  }, {} as Record<string, StageDefinition[]>)

  return (
    <div className="space-y-6">
      {/* Overall Progress Header */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">Pipeline Progress</CardTitle>
              <p className="text-sm text-muted-foreground">
                Claude Pipeline • Episode {episodeId}
              </p>
            </div>
            {progress && (
              <div className="text-right">
                <div className="text-2xl font-bold">{progress.overallProgress}%</div>
                <div className="text-sm text-muted-foreground">
                  {formatDuration(progress.estimatedTimeRemaining)} remaining
                </div>
              </div>
            )}
          </div>
          {progress && (
            <Progress value={progress.overallProgress} className="h-2 mt-2" />
          )}
        </CardHeader>

        {/* Real-time Metrics */}
        {progress && (
          <CardContent className="pt-0">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-blue-600" />
                <div>
                  <div className="font-medium">{progress.throughputMetrics.tweetsProcessed}</div>
                  <div className="text-muted-foreground">Tweets Processed</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-green-600" />
                <div>
                  <div className="font-medium">{progress.throughputMetrics.responsesGenerated}</div>
                  <div className="text-muted-foreground">Responses Generated</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-purple-600" />
                <div>
                  <div className="font-medium">{progress.resourceUsage.cpuUsage.toFixed(1)}%</div>
                  <div className="text-muted-foreground">CPU Usage</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <HardDrive className="w-4 h-4 text-orange-600" />
                <div>
                  <div className="font-medium">{(progress.resourceUsage.memoryUsage / 1024).toFixed(1)}GB</div>
                  <div className="text-muted-foreground">Memory Usage</div>
                </div>
              </div>
            </div>
          </CardContent>
        )}
      </Card>

      {/* Pipeline Flow Visualization */}
      <div className="space-y-6">
        {Object.entries(stagesByCategory).map(([category, categoryStages]) => (
          <Card key={category} className={cn(
            "relative",
            STAGE_CATEGORIES[category as keyof typeof STAGE_CATEGORIES]?.color
          )}>
            <CardHeader className="pb-4">
              <CardTitle className="text-base">
                {STAGE_CATEGORIES[category as keyof typeof STAGE_CATEGORIES]?.label}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {categoryStages.map((stage, index) => {
                  const stageProgress = getStageStatus(stage.id)
                  const status = stageProgress?.status || 'pending'
                  const statusBadge = getStatusBadge(status)
                  const StageIcon = STAGE_ICONS[stage.id] || stage.icon

                  return (
                    <div key={stage.id} className="relative">
                      {/* Connection line to next stage */}
                      {index < categoryStages.length - 1 && (
                        <div className="absolute left-8 top-16 w-0.5 h-8 bg-gray-200" />
                      )}
                      
                      <Card className={cn(
                        "transition-all duration-200 hover:shadow-md cursor-pointer",
                        selectedStage === stage.id && "ring-2 ring-blue-500",
                        status === 'running' && "border-blue-300 shadow-md",
                        status === 'completed' && "border-green-300",
                        status === 'failed' && "border-red-300"
                      )} onClick={() => setSelectedStage(selectedStage === stage.id ? null : stage.id)}>
                        <CardContent className="p-4">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <div className={cn(
                                "w-12 h-12 rounded-full flex items-center justify-center",
                                status === 'completed' && "bg-green-100",
                                status === 'running' && "bg-blue-100",
                                status === 'failed' && "bg-red-100",
                                status === 'pending' && "bg-gray-100"
                              )}>
                                <StageIcon className="w-6 h-6" />
                              </div>
                              <div>
                                <div className="flex items-center gap-2">
                                  <h3 className="font-medium">{stage.name}</h3>
                                  <Badge {...statusBadge}>
                                    {status}
                                  </Badge>
                                  {stageProgress?.retryCount > 0 && (
                                    <Badge variant="outline" className="text-xs">
                                      Retry {stageProgress.retryCount}
                                    </Badge>
                                  )}
                                </div>
                                <p className="text-sm text-muted-foreground mt-1">
                                  {stage.description}
                                </p>
                                
                                {/* Progress bar for running stages */}
                                {status === 'running' && stageProgress && (
                                  <div className="mt-2">
                                    <Progress value={stageProgress.progress} className="h-1" />
                                    <div className="flex justify-between text-xs text-muted-foreground mt-1">
                                      <span>{stageProgress.progress}%</span>
                                      {stageProgress.remainingTime && (
                                        <span>{formatDuration(stageProgress.remainingTime)} remaining</span>
                                      )}
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>

                            <div className="flex items-center gap-2">
                              {/* Time information */}
                              <div className="text-right text-sm">
                                {stageProgress?.duration ? (
                                  <div className="text-muted-foreground">
                                    {formatDuration(stageProgress.duration)}
                                  </div>
                                ) : (
                                  <div className="text-muted-foreground">
                                    ~{formatDuration(stage.estimatedDuration)}
                                  </div>
                                )}
                              </div>

                              {/* Status icon */}
                              {getStatusIcon(status)}

                              {/* Action buttons */}
                              {isInteractive && onStageAction && (
                                <div className="flex gap-1">
                                  {status === 'failed' && (
                                    <TooltipProvider>
                                      <Tooltip>
                                        <TooltipTrigger asChild>
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={(e) => {
                                              e.stopPropagation()
                                              onStageAction(stage.id, 'retry')
                                            }}
                                          >
                                            <RotateCcw className="w-3 h-3" />
                                          </Button>
                                        </TooltipTrigger>
                                        <TooltipContent>Retry Stage</TooltipContent>
                                      </Tooltip>
                                    </TooltipProvider>
                                  )}
                                  
                                  {status === 'pending' && (
                                    <TooltipProvider>
                                      <Tooltip>
                                        <TooltipTrigger asChild>
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={(e) => {
                                              e.stopPropagation()
                                              onStageAction(stage.id, 'start')
                                            }}
                                          >
                                            <Play className="w-3 h-3" />
                                          </Button>
                                        </TooltipTrigger>
                                        <TooltipContent>Start Stage</TooltipContent>
                                      </Tooltip>
                                    </TooltipProvider>
                                  )}
                                </div>
                              )}
                            </div>
                          </div>

                          {/* Expanded details */}
                          {selectedStage === stage.id && stageProgress && (
                            <div className="mt-4 pt-4 border-t border-gray-200">
                              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                                {stageProgress.metrics && (
                                  <>
                                    <div>
                                      <div className="font-medium">
                                        {stageProgress.metrics.itemsProcessed}/{stageProgress.metrics.totalItems}
                                      </div>
                                      <div className="text-muted-foreground">Items Processed</div>
                                    </div>
                                    
                                    <div>
                                      <div className="font-medium">
                                        {formatRate(stageProgress.metrics.processingRate)}
                                      </div>
                                      <div className="text-muted-foreground">Processing Rate</div>
                                    </div>
                                    
                                    <div>
                                      <div className="font-medium">
                                        {stageProgress.metrics.apiCallsUsed}
                                      </div>
                                      <div className="text-muted-foreground">API Calls</div>
                                    </div>
                                    
                                    <div>
                                      <div className="font-medium">
                                        ${stageProgress.metrics.costIncurred.toFixed(4)}
                                      </div>
                                      <div className="text-muted-foreground">Cost</div>
                                    </div>
                                  </>
                                )}
                                
                                {stageProgress.errorMessage && (
                                  <div className="col-span-full">
                                    <div className="p-2 bg-red-50 border border-red-200 rounded text-sm">
                                      <div className="flex items-center gap-2 text-red-800 font-medium">
                                        <AlertTriangle className="w-4 h-4" />
                                        Error
                                      </div>
                                      <div className="text-red-700 mt-1">
                                        {stageProgress.errorMessage}
                                      </div>
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Pipeline Controls */}
      {isInteractive && onPipelineAction && progress && (
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="text-sm text-muted-foreground">
                Pipeline Controls
              </div>
              <div className="flex gap-2">
                {progress.currentStage && (
                  <>
                    <Button 
                      size="sm" 
                      variant="outline"
                      onClick={() => onPipelineAction('pause')}
                    >
                      <Pause className="w-4 h-4 mr-1" />
                      Pause
                    </Button>
                    <Button 
                      size="sm" 
                      variant="destructive"
                      onClick={() => onPipelineAction('stop')}
                    >
                      Stop
                    </Button>
                  </>
                )}
                
                {!progress.currentStage && progress.overallProgress < 100 && (
                  <Button 
                    size="sm"
                    onClick={() => onPipelineAction('resume')}
                  >
                    <Play className="w-4 h-4 mr-1" />
                    Resume
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}