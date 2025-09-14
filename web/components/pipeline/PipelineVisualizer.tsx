'use client'

import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Checkbox } from '@/components/ui/checkbox'
import { 
  Play, 
  SkipForward, 
  RefreshCw, 
  CheckCircle2, 
  XCircle, 
  AlertCircle,
  FileText,
  Upload,
  Eye,
  Download,
  Loader2,
  FolderOpen
} from 'lucide-react'
import { 
  PIPELINE_STAGES,
  CLAUDE_PIPELINE_STAGES,
  LEGACY_PIPELINE_STAGES, 
  PipelineStage as PipelineStageType,
  FileReference
} from '@/lib/types/file-management'
import { toast } from '@/components/ui/use-toast'
import { cn } from '@/lib/utils'
import { FilePreviewDialog } from './FilePreviewDialog'
import { FileUploadDialog } from './FileUploadDialog'

interface PipelineVisualizerProps {
  episodeId: number
  episodeTitle: string
  pipelineType: 'claude' | 'legacy'
}

interface FileData {
  [key: string]: FileReference
}

interface FileConfig {
  episodeDir: string
  files: { [key: string]: string }
}

interface StageState {
  status: 'pending' | 'running' | 'completed' | 'skipped' | 'error'
  lastRun?: string
  outputHash?: string
  error?: string
  progress?: number
  duration?: number
}

export function PipelineVisualizer({ episodeId, episodeTitle, pipelineType }: PipelineVisualizerProps) {
  const [files, setFiles] = useState<FileData>({})
  const [pipelineState, setPipelineState] = useState<Record<string, StageState>>({})
  const [fileConfig, setFileConfig] = useState<FileConfig | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [uploadingFile, setUploadingFile] = useState<string | null>(null)
  const [runningStage, setRunningStage] = useState<string | null>(null)

  // Get stages based on pipeline type
  const getStages = () => {
    return pipelineType === 'claude' ? CLAUDE_PIPELINE_STAGES : LEGACY_PIPELINE_STAGES
  }

  const fetchFiles = useCallback(async () => {
    try {
      const res = await fetch(`/api/episodes/${episodeId}/files`)
      if (!res.ok) throw new Error('Failed to fetch files')
      
      const data = await res.json()
      setFiles(data.files || {})
      setPipelineState(data.pipelineState?.stages || {})
      setFileConfig(data.fileConfig || null)
      
      // Check if any stage is running
      const running = Object.entries(data.pipelineState?.stages || {}).find(
        ([_, state]: [string, any]) => state.status === 'running'
      )
      setRunningStage(running ? running[0] : null)
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to load pipeline data',
        variant: 'destructive'
      })
    } finally {
      setIsLoading(false)
    }
  }, [episodeId])

  useEffect(() => {
    fetchFiles()
    
    // Set up SSE for real-time updates
    const eventSource = new EventSource("/api/events")

    eventSource.addEventListener("pipeline_stage_started", (event) => {
      const data = JSON.parse(event.data)
      if (data.episodeId === episodeId.toString()) {
        setRunningStage(data.stage)
        // Refresh files to update stage status
        fetchFiles()
        toast({
          title: 'Stage Started',
          description: `${data.stage} stage has started`,
        })
      }
    })

    eventSource.addEventListener("pipeline_stage_progress", (event) => {
      const data = JSON.parse(event.data)
      if (data.episodeId === episodeId.toString()) {
        // Progress updates could be used to show logs in real-time
        console.log(`[${data.stage}] ${data.output}`)
      }
    })

    eventSource.addEventListener("pipeline_stage_error", (event) => {
      const data = JSON.parse(event.data)
      if (data.episodeId === episodeId.toString()) {
        console.error(`[${data.stage}] ${data.error}`)
        toast({
          title: 'Stage Error',
          description: `Error in ${data.stage} stage`,
          variant: 'destructive'
        })
      }
    })

    eventSource.addEventListener("pipeline_stage_completed", (event) => {
      const data = JSON.parse(event.data)
      if (data.episodeId === episodeId.toString()) {
        setRunningStage(null)
        // Refresh files to update stage status and outputs
        fetchFiles()
        const success = data.status === 'completed'
        toast({
          title: success ? 'Stage Completed' : 'Stage Failed',
          description: `${data.stage} stage ${success ? 'completed successfully' : 'failed'}`,
          variant: success ? 'default' : 'destructive'
        })
      }
    })

    eventSource.addEventListener("error", (error) => {
      console.error("SSE error:", error)
    })

    // Poll for updates while any stage is running (fallback)
    const interval = setInterval(() => {
      if (runningStage) {
        fetchFiles()
      }
    }, 5000) // Reduced frequency since SSE provides real-time updates

    return () => {
      eventSource.close()
      clearInterval(interval)
    }
  }, [episodeId, runningStage, fetchFiles])

  const runStage = async (stageId: string, useCached: boolean = false, forceRefresh: boolean = false) => {
    try {
      setRunningStage(stageId)
      
      const res = await fetch(`/api/episodes/${episodeId}/pipeline/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stageId, useCached, forceRefresh })
      })
      
      if (!res.ok) throw new Error('Failed to start stage')
      
      const data = await res.json()
      
      toast({
        title: 'Pipeline Started',
        description: `${data.message}. Run ID: ${data.runId}`
      })
      
      // Start polling for updates
      fetchFiles()
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to start pipeline stage',
        variant: 'destructive'
      })
      setRunningStage(null)
    }
  }

  const resetStage = async (stageId: string) => {
    try {
      const res = await fetch(`/api/episodes/${episodeId}/files/reset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stageId })
      })
      
      if (!res.ok) throw new Error('Failed to reset stage')
      
      const data = await res.json()
      
      toast({
        title: 'Stage Reset',
        description: `Cleared outputs for ${data.affectedStages.length} stage(s)`
      })
      
      fetchFiles()
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to reset stage',
        variant: 'destructive'
      })
    }
  }

  const handleFileUpload = async (fileKey: string, file: File) => {
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('fileKey', fileKey)
      
      const res = await fetch(`/api/episodes/${episodeId}/files/upload`, {
        method: 'POST',
        body: formData
      })
      
      if (!res.ok) throw new Error('Failed to upload file')
      
      const data = await res.json()
      
      toast({
        title: 'File Uploaded',
        description: `${data.fileName} uploaded successfully`
      })
      
      setUploadingFile(null)
      fetchFiles()
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to upload file',
        variant: 'destructive'
      })
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-32 w-full" />
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Alert>
        <FolderOpen className="h-4 w-4" />
        <AlertDescription>
          Episode files are stored in: <code className="font-mono text-sm">
            {fileConfig ? fileConfig.episodeDir.split('/').slice(-1)[0] : episodeTitle.toLowerCase().replace(/\s+/g, '-')}
          </code>
        </AlertDescription>
      </Alert>

      {getStages().map((stage, index) => {
        const stageState = pipelineState[stage.id] || { status: 'pending' }
        
        // Simple canRun logic based on stage requirements
        let canRun = false
        if (stage.id === 'summarization') {
          // Summarization needs transcript file
          canRun = files.transcript?.exists && stageState.status !== 'running'
        } else if (stage.id === 'classification') {
          // Classification needs summary (output of summarization)
          canRun = files.summary?.exists && stageState.status !== 'running'
        } else if (stage.id === 'response') {
          // Response needs classified tweets
          canRun = files.classified?.exists && stageState.status !== 'running'
        } else {
          // For other stages, just check if not running
          canRun = stageState.status !== 'running'
        }
        
        return (
          <PipelineStage
            key={stage.id}
            stage={stage}
            stageState={stageState}
            files={files}
            canRun={canRun}
            isRunning={runningStage === stage.id}
            onRun={(useCached, forceRefresh) => runStage(stage.id, useCached, forceRefresh)}
            onReset={() => resetStage(stage.id)}
            onFilePreview={setSelectedFile}
            onFileUpload={setUploadingFile}
          />
        )
      })}

      {selectedFile && (
        <FilePreviewDialog
          episodeId={episodeId}
          fileKey={selectedFile}
          fileName={files[selectedFile]?.path || selectedFile}
          onClose={() => setSelectedFile(null)}
        />
      )}

      {uploadingFile && (
        <FileUploadDialog
          fileKey={uploadingFile}
          fileName={files[uploadingFile]?.path || uploadingFile}
          onUpload={(file) => handleFileUpload(uploadingFile, file)}
          onClose={() => setUploadingFile(null)}
        />
      )}
    </div>
  )
}

interface PipelineStageProps {
  stage: any // Simplified for now
  stageState: StageState
  files: FileData
  canRun: boolean
  isRunning: boolean
  onRun: (useCached: boolean, forceRefresh: boolean) => void
  onReset: () => void
  onFilePreview: (fileKey: string) => void
  onFileUpload: (fileKey: string) => void
}

function PipelineStage({
  stage,
  stageState,
  files,
  canRun,
  isRunning,
  onRun,
  onReset,
  onFilePreview,
  onFileUpload
}: PipelineStageProps) {
  const [forceRefresh, setForceRefresh] = useState(false)
  
  const statusIcon = {
    pending: <AlertCircle className="h-5 w-5 text-muted-foreground" />,
    running: <Loader2 className="h-5 w-5 animate-spin text-blue-500" />,
    completed: <CheckCircle2 className="h-5 w-5 text-green-500" />,
    skipped: <SkipForward className="h-5 w-5 text-yellow-500" />,
    error: <XCircle className="h-5 w-5 text-destructive" />
  }

  const statusColor = {
    pending: 'bg-muted',
    running: 'bg-blue-50 border-blue-200',
    completed: 'bg-green-50 border-green-200',
    skipped: 'bg-yellow-50 border-yellow-200',
    error: 'bg-red-50 border-red-200'
  }

  return (
    <Card className={cn('transition-all', statusColor[stageState.status])}>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-3">
            {statusIcon[stageState.status]}
            <div>
              <CardTitle className="text-lg">{stage.name}</CardTitle>
              <CardDescription>{stage.description}</CardDescription>
              {stageState.error && (
                <p className="text-sm text-destructive mt-1">{stageState.error}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {stageState.lastRun && (
              <Badge variant="outline" className="text-xs">
                {new Date(stageState.lastRun).toLocaleString()}
              </Badge>
            )}
            {stageState.duration && (
              <Badge variant="secondary" className="text-xs">
                {(stageState.duration / 1000).toFixed(1)}s
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Progress bar for running stage */}
        {isRunning && (
          <Progress value={stageState.progress || 0} className="h-2" />
        )}

        {/* Input/Output Files */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Inputs */}
          <div>
            <h4 className="text-sm font-medium mb-2">Input Files</h4>
            <div className="space-y-1">
              {stage.inputs.map((inputKey: string) => (
                <FileItem
                  key={inputKey}
                  fileKey={inputKey}
                  file={files[inputKey]}
                  onPreview={() => onFilePreview(inputKey)}
                  onUpload={() => onFileUpload(inputKey)}
                  canUpload={inputKey === 'transcript'}
                />
              ))}
              {stage.inputs.length === 0 && (
                <p className="text-sm text-muted-foreground">No input files</p>
              )}
            </div>
          </div>

          {/* Outputs */}
          <div>
            <h4 className="text-sm font-medium mb-2">Output Files</h4>
            <div className="space-y-1">
              {stage.outputs.map((outputKey: string) => (
                <FileItem
                  key={outputKey}
                  fileKey={outputKey}
                  file={files[outputKey]}
                  onPreview={() => onFilePreview(outputKey)}
                  onUpload={() => onFileUpload(outputKey)}
                  canUpload={false}
                />
              ))}
              {stage.outputs.length === 0 && (
                <p className="text-sm text-muted-foreground">No output files</p>
              )}
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col gap-3">
          {/* Force refresh checkbox for scraping stage */}
          {stage.id === 'scraping' && (
            <div className="flex items-center space-x-2">
              <Checkbox 
                id={`force-refresh-${stage.id}`}
                checked={forceRefresh}
                onCheckedChange={(checked) => setForceRefresh(checked as boolean)}
                disabled={isRunning}
              />
              <label 
                htmlFor={`force-refresh-${stage.id}`}
                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
              >
                Force refresh (ignore 4-day cache and fetch fresh tweets)
              </label>
            </div>
          )}
          
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              onClick={() => onRun(false, forceRefresh)}
              disabled={!canRun || isRunning}
            >
              {isRunning ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Running...
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 mr-2" />
                  Run
                </>
              )}
            </Button>

            {stageState.status !== 'pending' && (
              <Button
                size="sm"
                variant="ghost"
                onClick={onReset}
                disabled={isRunning}
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Reset
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

interface FileItemProps {
  fileKey: string
  file?: FileReference
  onPreview: () => void
  onUpload: () => void
  canUpload: boolean
}

function FileItem({ fileKey, file, onPreview, onUpload, canUpload }: FileItemProps) {
  return (
    <div className="flex items-center justify-between p-2 rounded-md hover:bg-accent/50 transition-colors">
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <FileText className={cn(
          "h-4 w-4 flex-shrink-0",
          file?.exists ? "text-green-600" : "text-muted-foreground"
        )} />
        <span className="text-sm truncate">{fileKey}</span>
        {file?.exists && file.size && (
          <Badge variant="outline" className="text-xs">
            {(file.size / 1024).toFixed(1)}KB
          </Badge>
        )}
      </div>
      <div className="flex items-center gap-1">
        {file?.exists && (
          <Button
            size="icon"
            variant="ghost"
            className="h-6 w-6"
            onClick={onPreview}
          >
            <Eye className="h-3 w-3" />
          </Button>
        )}
        {canUpload && (
          <Button
            size="icon"
            variant="ghost"
            className="h-6 w-6"
            onClick={onUpload}
          >
            <Upload className="h-3 w-3" />
          </Button>
        )}
      </div>
    </div>
  )
}