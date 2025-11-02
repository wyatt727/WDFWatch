/**
 * Unified Pipeline Controller Component
 * 
 * Main interface that integrates all pipeline functionality:
 * - Pre-flight validation
 * - Visual pipeline flow
 * - Progress tracking
 * - Error recovery
 * - Pipeline controls
 */

"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { 
  Play, 
  Pause, 
  Square, 
  RotateCcw, 
  CheckCircle2, 
  AlertTriangle, 
  XCircle,
  Settings,
  Activity,
  Clock
} from "lucide-react"
import { PipelineFlowDiagram } from "./PipelineFlowDiagram"
import { ValidationResults } from "./ValidationResults"
import { useToast } from "@/hooks/use-toast"

interface UnifiedPipelineControllerProps {
  episodeId: number
  initialStatus?: any
}

interface PipelineState {
  status: 'idle' | 'validating' | 'running' | 'paused' | 'completed' | 'failed'
  runId?: string
  progress?: any
  validation?: any
  isValidated: boolean
  canStart: boolean
}

const CLAUDE_STAGE_DEFINITIONS = [
  {
    id: 'validation',
    name: 'Pre-flight Validation',
    description: 'Validate all requirements and configuration',
    icon: Settings,
    estimatedDuration: 1,
    dependencies: [],
    category: 'preparation' as const,
  },
  {
    id: 'summarization',
    name: 'Episode Summarization',
    description: 'Generate episode summary and extract insights using Claude',
    icon: Activity,
    estimatedDuration: 3,
    dependencies: ['validation'],
    category: 'processing' as const,
  },
  {
    id: 'classification',
    name: 'Tweet Classification',
    description: 'Classify tweets for relevance using Claude',
    icon: CheckCircle2,
    estimatedDuration: 5,
    dependencies: ['summarization'],
    category: 'processing' as const,
  },
  {
    id: 'response',
    name: 'Response Generation',
    description: 'Generate thoughtful responses using Claude',
    icon: Activity,
    estimatedDuration: 8,
    dependencies: ['classification'],
    category: 'generation' as const,
  },
  {
    id: 'moderation',
    name: 'Human Review',
    description: 'Review and approve generated responses',
    icon: CheckCircle2,
    estimatedDuration: 0,
    dependencies: ['response'],
    category: 'review' as const,
  },
]

export function UnifiedPipelineController({
  episodeId,
  initialStatus,
}: UnifiedPipelineControllerProps) {
  const [state, setState] = useState<PipelineState>({
    status: 'idle',
    isValidated: false,
    canStart: false,
  })
  const [isLoading, setIsLoading] = useState(false)
  const { toast } = useToast()

  const stages = CLAUDE_STAGE_DEFINITIONS

  // Load initial status
  useEffect(() => {
    if (initialStatus) {
      setState(prev => ({
        ...prev,
        status: initialStatus.isRunning ? 'running' : 'idle',
        runId: initialStatus.latestRun?.runId,
        progress: initialStatus.progress,
        isValidated: Boolean(initialStatus.latestRun?.validation),
      }))
    }
  }, [initialStatus])

  // Handle validation
  const handleValidate = async () => {
    setIsLoading(true)
    setState(prev => ({ ...prev, status: 'validating' }))

    try {
      const response = await fetch(`/api/episodes/${episodeId}/pipeline/validate`, {
        method: 'POST',
      })

      if (!response.ok) throw new Error('Validation failed')

      const data = await response.json()
      
      setState(prev => ({
        ...prev,
        status: 'idle',
        validation: data.validation,
        isValidated: true,
        canStart: data.validation.isValid,
      }))

      if (data.validation.isValid) {
        toast({
          title: "Validation Successful",
          description: "Pipeline is ready to run!",
        })
      } else {
        toast({
          title: "Validation Issues Found",
          description: `${data.validation.errors.length} critical issues need attention.`,
          variant: "destructive",
        })
      }
    } catch (error) {
      setState(prev => ({ ...prev, status: 'idle' }))
      toast({
        title: "Validation Failed",
        description: "Could not validate pipeline requirements.",
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  // Handle pipeline start
  const handleStart = async (skipValidation = false) => {
    setIsLoading(true)

    try {
      const response = await fetch(`/api/episodes/${episodeId}/pipeline/orchestrator`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'start',
          options: {
            skipValidation,
            notifyOnCompletion: true,
            maxRetries: 3,
            concurrency: 'medium',
          },
        }),
      })

      if (!response.ok) throw new Error('Failed to start pipeline')

      const data = await response.json()
      
      setState(prev => ({
        ...prev,
        status: 'running',
        runId: data.runId,
      }))

      toast({
        title: "Pipeline Started",
        description: "Pipeline execution has begun.",
      })
    } catch (error) {
      toast({
        title: "Start Failed",
        description: error instanceof Error ? error.message : "Could not start pipeline.",
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  // Handle pipeline pause
  const handlePause = async () => {
    setIsLoading(true)

    try {
      const response = await fetch(`/api/episodes/${episodeId}/pipeline/orchestrator`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'pause' }),
      })

      if (!response.ok) throw new Error('Failed to pause pipeline')

      setState(prev => ({ ...prev, status: 'paused' }))
      
      toast({
        title: "Pipeline Paused",
        description: "Pipeline execution has been paused.",
      })
    } catch (error) {
      toast({
        title: "Pause Failed",
        description: "Could not pause pipeline.",
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  // Handle pipeline resume
  const handleResume = async () => {
    setIsLoading(true)

    try {
      const response = await fetch(`/api/episodes/${episodeId}/pipeline/orchestrator`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'resume' }),
      })

      if (!response.ok) throw new Error('Failed to resume pipeline')

      setState(prev => ({ ...prev, status: 'running' }))
      
      toast({
        title: "Pipeline Resumed",
        description: "Pipeline execution has resumed.",
      })
    } catch (error) {
      toast({
        title: "Resume Failed",
        description: "Could not resume pipeline.",
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  // Handle pipeline stop
  const handleStop = async () => {
    setIsLoading(true)

    try {
      const response = await fetch(`/api/episodes/${episodeId}/pipeline/orchestrator`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'stop' }),
      })

      if (!response.ok) throw new Error('Failed to stop pipeline')

      setState(prev => ({ ...prev, status: 'idle', runId: undefined }))
      
      toast({
        title: "Pipeline Stopped",
        description: "Pipeline execution has been stopped.",
      })
    } catch (error) {
      toast({
        title: "Stop Failed",
        description: "Could not stop pipeline.",
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  // Handle stage actions
  const handleStageAction = async (stageId: string, action: 'start' | 'retry' | 'skip') => {
    // Individual stage control would go here
    // This would call the existing stage-specific endpoints
    toast({
      title: "Stage Action",
      description: `${action} action for ${stageId} stage.`,
    })
  }

  // Get status indicator
  const getStatusIndicator = () => {
    switch (state.status) {
      case 'validating':
        return { icon: Clock, color: 'text-blue-600', label: 'Validating' }
      case 'running':
        return { icon: Activity, color: 'text-green-600 animate-pulse', label: 'Running' }
      case 'paused':
        return { icon: Pause, color: 'text-yellow-600', label: 'Paused' }
      case 'completed':
        return { icon: CheckCircle2, color: 'text-green-600', label: 'Completed' }
      case 'failed':
        return { icon: XCircle, color: 'text-red-600', label: 'Failed' }
      default:
        return { icon: Clock, color: 'text-gray-400', label: 'Ready' }
    }
  }

  const statusIndicator = getStatusIndicator()

  return (
    <div className="space-y-6">
      {/* Pipeline Status Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <statusIndicator.icon className={`w-6 h-6 ${statusIndicator.color}`} />
              <div>
                <CardTitle className="text-lg">
                  Claude Pipeline
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  Episode {episodeId} • {statusIndicator.label}
                  {state.runId && (
                    <Badge variant="outline" className="ml-2">
                      {state.runId}
                    </Badge>
                  )}
                </p>
              </div>
            </div>

            {/* Main Pipeline Controls */}
            <div className="flex items-center gap-2">
              {state.status === 'idle' && (
                <>
                  <Button
                    variant="outline"
                    onClick={handleValidate}
                    disabled={isLoading}
                  >
                    <Settings className="w-4 h-4 mr-2" />
                    {state.isValidated ? 'Re-validate' : 'Validate'}
                  </Button>
                  
                  <Button
                    onClick={() => handleStart()}
                    disabled={isLoading || (!state.canStart && state.isValidated)}
                  >
                    <Play className="w-4 h-4 mr-2" />
                    Start Pipeline
                  </Button>
                </>
              )}

              {state.status === 'running' && (
                <>
                  <Button
                    variant="outline"
                    onClick={handlePause}
                    disabled={isLoading}
                  >
                    <Pause className="w-4 h-4 mr-2" />
                    Pause
                  </Button>
                  
                  <Button
                    variant="destructive"
                    onClick={handleStop}
                    disabled={isLoading}
                  >
                    <Square className="w-4 h-4 mr-2" />
                    Stop
                  </Button>
                </>
              )}

              {state.status === 'paused' && (
                <>
                  <Button
                    onClick={handleResume}
                    disabled={isLoading}
                  >
                    <Play className="w-4 h-4 mr-2" />
                    Resume
                  </Button>
                  
                  <Button
                    variant="destructive"
                    onClick={handleStop}
                    disabled={isLoading}
                  >
                    <Square className="w-4 h-4 mr-2" />
                    Stop
                  </Button>
                </>
              )}

              {state.status === 'failed' && (
                <Button
                  onClick={() => handleStart(true)}
                  disabled={isLoading}
                >
                  <RotateCcw className="w-4 h-4 mr-2" />
                  Retry
                </Button>
              )}
            </div>
          </div>
        </CardHeader>

        {/* Validation Alert */}
        {!state.isValidated && state.status === 'idle' && (
          <CardContent className="pt-0">
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                Pipeline validation required before starting. Click "Validate" to check requirements.
              </AlertDescription>
            </Alert>
          </CardContent>
        )}
      </Card>

      {/* Main Interface Tabs */}
      <Tabs defaultValue="pipeline" className="space-y-4">
        <TabsList>
          <TabsTrigger value="pipeline">Pipeline Flow</TabsTrigger>
          <TabsTrigger value="validation">
            Validation
            {state.validation && !state.validation.isValid && (
              <Badge variant="destructive" className="ml-2 text-xs">
                {state.validation.errors.length}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="pipeline">
          <PipelineFlowDiagram
            episodeId={episodeId}
            stages={stages}
            progress={state.progress}
            onStageAction={handleStageAction}
            onPipelineAction={(action) => {
              switch (action) {
                case 'pause': return handlePause()
                case 'resume': return handleResume()
                case 'stop': return handleStop()
              }
            }}
            isInteractive={true}
          />
        </TabsContent>

        <TabsContent value="validation">
          {state.validation ? (
            <ValidationResults
              episodeId={episodeId}
              validation={state.validation}
              nextSteps={[]} // This would come from the validation API
              readinessStatus={{
                status: state.validation.isValid ? 'ready' : 'blocked',
                color: state.validation.isValid ? 'green' : 'red',
                message: state.validation.isValid 
                  ? 'Pipeline is ready to run'
                  : 'Critical issues must be resolved before starting',
              }}
              onRevalidate={handleValidate}
              onStartPipeline={() => handleStart()}
              isRevalidating={state.status === 'validating'}
              canStartPipeline={state.validation.isValid}
            />
          ) : (
            <Card>
              <CardContent className="p-6 text-center">
                <Settings className="w-12 h-12 text-muted-foreground mx-auto mb-3" />
                <h3 className="font-medium text-lg mb-2">Validation Required</h3>
                <p className="text-muted-foreground mb-4">
                  Run validation to check pipeline requirements and configuration.
                </p>
                <Button onClick={handleValidate} disabled={isLoading}>
                  <Settings className="w-4 h-4 mr-2" />
                  Run Validation
                </Button>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}