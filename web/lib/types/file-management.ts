/**
 * File Management Types
 * 
 * Types for episode-based file organization and pipeline state tracking
 */

export interface FileReference {
  key: string                    // e.g., 'transcript', 'summary'
  path: string                   // relative to episode dir
  exists: boolean
  size?: number                  // in bytes
  lastModified?: Date
  hash?: string                  // SHA256 hash for cache detection
  preview?: string              // first 500 chars for UI preview
}

export interface PipelineStage {
  id: string                     // e.g., 'summarization', 'classification'
  name: string                   // Human-readable name
  description: string
  status: 'pending' | 'running' | 'completed' | 'skipped' | 'error'
  inputs: FileReference[]
  outputs: FileReference[]
  canSkip: boolean              // Can user skip this stage?
  canUseCached: boolean         // Can use cached output?
  lastRun?: Date
  outputHash?: string           // Hash of outputs for cache detection
  error?: string                // Error message if status is 'error'
  progress?: number             // 0-100 for running status
  logs?: string[]               // Recent log messages
}

export interface FileConfig {
  episodeDir: string
  files: {
    // Input files
    transcript: string
    overview: string
    videoUrl: string
    // Output files
    summary: string
    keywords: string
    fewshots: string
    tweets: string
    classified: string
    responses: string
    published: string
  }
}

export interface PipelineState {
  stages: {
    [stageId: string]: {
      status: PipelineStage['status']
      lastRun?: string              // ISO date
      outputHash?: string
      error?: string
      skippedReason?: string
      duration?: number             // milliseconds
    }
  }
  currentStage?: string
  startedAt?: string
  completedAt?: string
}

// Pipeline stage definitions - Legacy Pipeline
export const LEGACY_PIPELINE_STAGES = [
  {
    id: 'summarization',
    name: 'Summarization',
    description: 'Generate episode summary and extract keywords',
    inputs: ['transcript', 'overview'],
    outputs: ['summary', 'keywords'],
    canSkip: false,
    canUseCached: true
  },
  {
    id: 'fewshot',
    name: 'Few-shot Generation',
    description: 'Create classification training examples',
    inputs: ['summary', 'overview'],
    outputs: ['fewshots'],
    canSkip: true,
    canUseCached: true
  },
  {
    id: 'scraping',
    name: 'Tweet Discovery',
    description: 'Search for relevant tweets using keywords',
    inputs: ['keywords'],
    outputs: ['tweets'],
    canSkip: false,
    canUseCached: false  // Always want fresh tweets
  },
  {
    id: 'classification',
    name: 'Classification',
    description: 'Classify tweets as relevant or skip',
    inputs: ['tweets', 'fewshots', 'summary'],
    outputs: ['classified'],
    canSkip: false,
    canUseCached: true
  },
  {
    id: 'response',
    name: 'Response Generation',
    description: 'Generate responses for relevant tweets',
    inputs: ['classified', 'summary', 'videoUrl', 'overview'],
    outputs: ['responses'],
    canSkip: false,
    canUseCached: false  // Want fresh responses
  },
  {
    id: 'moderation',
    name: 'Human Review',
    description: 'Review and approve generated responses',
    inputs: ['responses'],
    outputs: ['published'],
    canSkip: true,
    canUseCached: false
  }
] as const

// Pipeline stage definitions - Claude Pipeline
export const CLAUDE_PIPELINE_STAGES = [
  {
    id: 'summarization',
    name: 'Summarization',
    description: 'Generate episode summary and extract keywords using Claude',
    inputs: ['transcript'], // No overview file needed - embedded in CLAUDE.md
    outputs: ['summary', 'keywords'],
    canSkip: false,
    canUseCached: true
  },
  {
    id: 'scraping',
    name: 'Tweet Discovery',
    description: 'Search for relevant tweets using keywords',
    inputs: ['keywords'],
    outputs: ['tweets'],
    canSkip: false,
    canUseCached: false  // Always want fresh tweets
  },
  {
    id: 'classification',
    name: 'Classification',
    description: 'Classify tweets as relevant using Claude (no few-shots needed)',
    inputs: ['tweets'], // Claude uses episode context from CLAUDE.md
    outputs: ['classified'],
    canSkip: false,
    canUseCached: true
  },
  {
    id: 'response',
    name: 'Response Generation',
    description: 'Generate responses for relevant tweets using Claude',
    inputs: ['classified'], // videoUrl comes from database, context from CLAUDE.md
    outputs: ['responses'],
    canSkip: false,
    canUseCached: false  // Want fresh responses
  },
  {
    id: 'moderation',
    name: 'Quality Review',
    description: 'Claude quality check with optional human review',
    inputs: ['responses'],
    outputs: ['published'],
    canSkip: true,
    canUseCached: false
  }
] as const

// Combined type for both pipelines - defaults to legacy for backwards compatibility
export const PIPELINE_STAGES = LEGACY_PIPELINE_STAGES

export type StageId = typeof PIPELINE_STAGES[number]['id']
export type ClaudeStageId = typeof CLAUDE_PIPELINE_STAGES[number]['id']
export type LegacyStageId = typeof LEGACY_PIPELINE_STAGES[number]['id']

// Helper functions
export function getStageById(id: StageId) {
  return PIPELINE_STAGES.find(stage => stage.id === id)
}

export function getStagesByPipelineType(pipelineType: 'claude' | 'legacy') {
  return pipelineType === 'claude' ? CLAUDE_PIPELINE_STAGES : LEGACY_PIPELINE_STAGES
}

export function getStageByIdAndType(id: string, pipelineType: 'claude' | 'legacy') {
  const stages = getStagesByPipelineType(pipelineType)
  return stages.find(stage => stage.id === id)
}

export function getStageInputs(id: string, pipelineType: 'claude' | 'legacy' = 'legacy'): string[] {
  const stage = getStageByIdAndType(id, pipelineType)
  return stage ? [...stage.inputs] : []
}

export function getStageOutputs(id: string, pipelineType: 'claude' | 'legacy' = 'legacy'): string[] {
  const stage = getStageByIdAndType(id, pipelineType)
  return stage ? [...stage.outputs] : []
}

export function canRunStage(
  stageId: string, 
  fileConfig: FileConfig,
  fileStatuses: Record<string, boolean>,
  pipelineType: 'claude' | 'legacy' = 'legacy'
): boolean {
  const stage = getStageByIdAndType(stageId, pipelineType)
  if (!stage) return false
  
  // Check if all input files exist
  return stage.inputs.every(inputKey => {
    const filePath = fileConfig.files[inputKey as keyof FileConfig['files']]
    return filePath && fileStatuses[filePath]
  })
}

export function shouldUseCachedOutput(
  stage: PipelineStage,
  inputHashes: Record<string, string>
): boolean {
  if (!stage.canUseCached || !stage.outputHash) return false
  
  // Check if any inputs have changed since last run
  return stage.inputs.every(input => 
    input.hash === inputHashes[input.key]
  )
}

// File path helpers
export function getEpisodeFilePath(
  episodeDir: string,
  fileKey: keyof FileConfig['files']
): string {
  const fileMap: Record<keyof FileConfig['files'], string> = {
    // Inputs
    transcript: 'inputs/transcript.txt',
    overview: 'inputs/podcast_overview.txt',
    videoUrl: 'inputs/video_url.txt',
    // Outputs
    summary: 'outputs/summary.md',
    keywords: 'outputs/keywords.json',
    fewshots: 'outputs/fewshots.json',
    tweets: 'outputs/tweets.json',
    classified: 'outputs/classified.json',
    responses: 'outputs/responses.json',
    published: 'outputs/published.json'
  }
  
  return `${episodeDir}/${fileMap[fileKey]}`
}