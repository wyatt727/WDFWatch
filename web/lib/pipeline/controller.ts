/**
 * Unified Pipeline Controller
 * 
 * Provides centralized control over pipeline execution with support for:
 * - Full pipeline orchestration
 * - Stage-by-stage execution
 * - Progress tracking and state management
 * - Error recovery and retry mechanisms
 * - Both Claude and legacy pipeline support
 */

import { spawn, ChildProcess } from 'child_process';
import { join } from 'path';
import { prisma } from '@/lib/db';
import { processTracker, ProcessInfo } from '@/lib/process-tracker';
import { PipelineValidator } from './validator';
import { ErrorRecoveryManager } from './error-recovery';
import { ProgressTracker } from './progress-tracker';

export interface PipelineStage {
  id: string;
  name: string;
  description: string;
  dependencies: string[];
  estimatedDuration: number; // seconds
  retryable: boolean;
  critical: boolean; // if true, failure stops entire pipeline
}

export interface PipelineOptions {
  force?: boolean;
  skipValidation?: boolean;
  retryFailedStages?: boolean;
  notifyOnCompletion?: boolean;
  maxRetries?: number;
  concurrency?: 'low' | 'medium' | 'high';
}

export interface PipelineState {
  episodeId: number;
  runId: string;
  status: 'pending' | 'validating' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  currentStage?: string;
  completedStages: string[];
  failedStages: string[];
  progress: number; // 0-100
  startedAt?: Date;
  completedAt?: Date;
  estimatedCompletion?: Date;
  errorMessage?: string;
  retryCount: number;
  validationResults?: any;
}

export class PipelineController {
  private validator: PipelineValidator;
  private errorRecovery: ErrorRecoveryManager;
  private progressTracker: ProgressTracker;
  private pipelineStates = new Map<number, PipelineState>();

  constructor() {
    this.validator = new PipelineValidator();
    this.errorRecovery = new ErrorRecoveryManager();
    this.progressTracker = new ProgressTracker();
  }

  /**
   * Define pipeline stages for different pipeline types
   */
  private getStageDefinitions(pipelineType: 'claude' | 'legacy'): PipelineStage[] {
    const baseStages: PipelineStage[] = [
      {
        id: 'validation',
        name: 'Pre-flight Validation',
        description: 'Validate requirements and configuration',
        dependencies: [],
        estimatedDuration: 30,
        retryable: true,
        critical: true,
      },
    ];

    if (pipelineType === 'claude') {
      return [
        ...baseStages,
        {
          id: 'summarization',
          name: 'Episode Summarization',
          description: 'Generate episode summary and extract insights',
          dependencies: ['validation'],
          estimatedDuration: 120,
          retryable: true,
          critical: true,
        },
        {
          id: 'classification',
          name: 'Tweet Classification',
          description: 'Classify tweets for relevance using Claude',
          dependencies: ['summarization'],
          estimatedDuration: 180,
          retryable: true,
          critical: false,
        },
        {
          id: 'response',
          name: 'Response Generation',
          description: 'Generate responses using Claude',
          dependencies: ['classification'],
          estimatedDuration: 240,
          retryable: true,
          critical: false,
        },
        {
          id: 'moderation',
          name: 'Human Moderation',
          description: 'Review and approve generated responses',
          dependencies: ['response'],
          estimatedDuration: 0, // User-dependent
          retryable: false,
          critical: false,
        },
      ];
    } else {
      return [
        ...baseStages,
        {
          id: 'summarization',
          name: 'Transcript Analysis',
          description: 'Analyze transcript and extract keywords',
          dependencies: ['validation'],
          estimatedDuration: 90,
          retryable: true,
          critical: true,
        },
        {
          id: 'fewshot',
          name: 'Few-shot Generation',
          description: 'Generate classification examples',
          dependencies: ['summarization'],
          estimatedDuration: 60,
          retryable: true,
          critical: true,
        },
        {
          id: 'scraping',
          name: 'Tweet Scraping',
          description: 'Collect relevant tweets from Twitter',
          dependencies: ['fewshot'],
          estimatedDuration: 45,
          retryable: true,
          critical: false,
        },
        {
          id: 'classification',
          name: 'Tweet Classification',
          description: 'Classify tweets using local models',
          dependencies: ['scraping'],
          estimatedDuration: 120,
          retryable: true,
          critical: false,
        },
        {
          id: 'response',
          name: 'Response Generation',
          description: 'Generate responses using DeepSeek',
          dependencies: ['classification'],
          estimatedDuration: 180,
          retryable: true,
          critical: false,
        },
        {
          id: 'moderation',
          name: 'Human Moderation',
          description: 'Review and approve generated responses',
          dependencies: ['response'],
          estimatedDuration: 0, // User-dependent
          retryable: false,
          critical: false,
        },
      ];
    }
  }

  /**
   * Start full pipeline execution
   */
  async startFullPipeline(
    episodeId: number,
    options: PipelineOptions = {}
  ): Promise<{ runId: string; state: PipelineState }> {
    // Check if pipeline is already running
    if (this.isPipelineRunning(episodeId)) {
      throw new Error('Pipeline is already running for this episode');
    }

    // Get episode info
    const episode = await prisma.podcastEpisode.findUnique({
      where: { id: episodeId },
      select: { id: true, title: true, pipelineType: true, claudeEpisodeDir: true },
    });

    if (!episode) {
      throw new Error('Episode not found');
    }

    const runId = `pipeline-${episodeId}-${Date.now()}`;
    const pipelineType = episode.pipelineType as 'claude' | 'legacy';
    const stages = this.getStageDefinitions(pipelineType);

    // Initialize pipeline state
    const state: PipelineState = {
      episodeId,
      runId,
      status: 'pending',
      completedStages: [],
      failedStages: [],
      progress: 0,
      retryCount: 0,
      startedAt: new Date(),
    };

    this.pipelineStates.set(episodeId, state);

    // Start validation if not skipped
    if (!options.skipValidation) {
      state.status = 'validating';
      state.currentStage = 'validation';
      await this.updateState(episodeId, state);

      try {
        const validationResults = await this.validator.validatePipeline(episodeId, pipelineType);
        state.validationResults = validationResults;

        if (!validationResults.isValid) {
          state.status = 'failed';
          state.errorMessage = 'Pipeline validation failed';
          await this.updateState(episodeId, state);
          throw new Error(`Validation failed: ${validationResults.errors.join(', ')}`);
        }

        state.completedStages.push('validation');
      } catch (error) {
        state.status = 'failed';
        state.errorMessage = error instanceof Error ? error.message : 'Validation failed';
        await this.updateState(episodeId, state);
        throw error;
      }
    }

    // Start pipeline execution
    state.status = 'running';
    await this.updateState(episodeId, state);

    // Execute stages sequentially
    this.executeStagesSequentially(episodeId, stages.slice(1), options); // Skip validation stage

    return { runId, state };
  }

  /**
   * Execute pipeline stages sequentially
   */
  private async executeStagesSequentially(
    episodeId: number,
    stages: PipelineStage[],
    options: PipelineOptions
  ): Promise<void> {
    const state = this.pipelineStates.get(episodeId);
    if (!state) return;

    try {
      for (const stage of stages) {
        // Check if pipeline was cancelled
        if (state.status === 'cancelled') {
          break;
        }

        // Skip if stage already completed (for resume functionality)
        if (state.completedStages.includes(stage.id)) {
          continue;
        }

        // Execute stage with retry logic
        await this.executeStageWithRetry(episodeId, stage, options);

        // Update progress
        const progressPercent = (state.completedStages.length / stages.length) * 100;
        state.progress = Math.round(progressPercent);
        await this.updateState(episodeId, state);
      }

      // Mark pipeline as completed if all stages succeeded
      if (state.status === 'running') {
        state.status = 'completed';
        state.completedAt = new Date();
        state.progress = 100;
        await this.updateState(episodeId, state);
      }

    } catch (error) {
      state.status = 'failed';
      state.errorMessage = error instanceof Error ? error.message : 'Pipeline execution failed';
      await this.updateState(episodeId, state);
    }
  }

  /**
   * Execute a single stage with retry logic
   */
  private async executeStageWithRetry(
    episodeId: number,
    stage: PipelineStage,
    options: PipelineOptions,
    attempt: number = 1
  ): Promise<void> {
    const state = this.pipelineStates.get(episodeId);
    if (!state) return;

    const maxRetries = options.maxRetries || 3;
    state.currentStage = stage.id;
    await this.updateState(episodeId, state);

    try {
      await this.executeSingleStage(episodeId, stage);
      state.completedStages.push(stage.id);
      state.retryCount = 0; // Reset retry count on success
      
    } catch (error) {
      state.failedStages.push(stage.id);
      
      // Check if stage is retryable and we haven't exceeded max retries
      if (stage.retryable && attempt < maxRetries) {
        console.log(`Stage ${stage.id} failed, retrying (attempt ${attempt + 1}/${maxRetries})`);
        
        // Wait before retry (exponential backoff)
        const backoffDelay = Math.min(1000 * Math.pow(2, attempt - 1), 30000);
        await new Promise(resolve => setTimeout(resolve, backoffDelay));
        
        state.retryCount = attempt;
        await this.updateState(episodeId, state);
        
        // Remove from failed stages for retry
        state.failedStages = state.failedStages.filter(s => s !== stage.id);
        
        return this.executeStageWithRetry(episodeId, stage, options, attempt + 1);
      }

      // If stage is critical or not retryable, fail the entire pipeline
      if (stage.critical) {
        throw error;
      }

      // For non-critical stages, log warning and continue
      console.warn(`Non-critical stage ${stage.id} failed, continuing pipeline:`, error);
    }
  }

  /**
   * Execute a single pipeline stage
   */
  private async executeSingleStage(episodeId: number, stage: PipelineStage): Promise<void> {
    // Emit SSE event for stage start
    await this.emitSSEEvent({
      type: 'pipeline_stage_started',
      episodeId: episodeId.toString(),
      stage: stage.id,
      stageName: stage.name,
      description: stage.description,
    });

    // Get episode info for pipeline type
    const episode = await prisma.podcastEpisode.findUnique({
      where: { id: episodeId },
      select: { pipelineType: true, claudeEpisodeDir: true },
    });

    if (!episode) {
      throw new Error('Episode not found');
    }

    return new Promise((resolve, reject) => {
      const pythonPath = process.env.PYTHON_PATH || 'python';
      let taskProcess: ChildProcess;

      if (episode.pipelineType === 'claude') {
        // Use Claude pipeline bridge
        const args = [
          'web/scripts/claude_pipeline_bridge.py',
          '--episode-id', episodeId.toString(),
          '--stage', stage.id
        ];

        taskProcess = spawn(pythonPath, args, {
          cwd: join(process.cwd(), '..'),
          env: {
            ...process.env,
            WDF_WEB_MODE: 'true',
            WDF_USE_CLAUDE_PIPELINE: 'true',
            WDF_EPISODE_ID: episodeId.toString(),
          },
        });
      } else {
        // Use legacy pipeline tasks
        const taskMap: Record<string, string> = {
          'summarization': 'scripts/transcript_summarizer.js',
          'fewshot': 'src/wdf/tasks/fewshot.py',
          'scraping': 'src/wdf/tasks/scrape.py',
          'classification': 'src/wdf/tasks/classify.py',
          'response': 'src/wdf/tasks/deepseek.py',
          'moderation': 'src/wdf/tasks/web_moderation.py',
        };

        const taskPath = taskMap[stage.id];
        if (!taskPath) {
          reject(new Error(`Unknown stage: ${stage.id}`));
          return;
        }

        if (stage.id === 'summarization') {
          // Node.js script
          taskProcess = spawn('node', [taskPath], {
            cwd: join(process.cwd(), '..'),
            env: {
              ...process.env,
              WDF_WEB_MODE: 'true',
              WDF_EPISODE_ID: episodeId.toString(),
            },
          });
        } else {
          // Python script
          taskProcess = spawn(pythonPath, [taskPath], {
            cwd: join(process.cwd(), '..'),
            env: {
              ...process.env,
              WDF_WEB_MODE: 'true',
              WDF_EPISODE_ID: episodeId.toString(),
            },
          });
        }
      }

      // Track process output
      taskProcess.stdout?.on('data', (data) => {
        this.emitSSEEvent({
          type: 'pipeline_stage_progress',
          episodeId: episodeId.toString(),
          stage: stage.id,
          output: data.toString(),
        });
      });

      taskProcess.stderr?.on('data', (data) => {
        this.emitSSEEvent({
          type: 'pipeline_stage_error',
          episodeId: episodeId.toString(),
          stage: stage.id,
          error: data.toString(),
        });
      });

      // Handle completion
      taskProcess.on('close', async (code) => {
        if (code === 0) {
          await this.emitSSEEvent({
            type: 'pipeline_stage_completed',
            episodeId: episodeId.toString(),
            stage: stage.id,
            stageName: stage.name,
            status: 'success',
          });
          resolve();
        } else {
          await this.emitSSEEvent({
            type: 'pipeline_stage_completed',
            episodeId: episodeId.toString(),
            stage: stage.id,
            stageName: stage.name,
            status: 'failed',
            exitCode: code,
          });
          reject(new Error(`Stage ${stage.id} failed with exit code ${code}`));
        }
      });

      taskProcess.on('error', (error) => {
        reject(error);
      });
    });
  }

  /**
   * Pause pipeline execution
   */
  async pausePipeline(episodeId: number): Promise<void> {
    const state = this.pipelineStates.get(episodeId);
    if (!state || state.status !== 'running') {
      throw new Error('No running pipeline found for this episode');
    }

    // Kill running processes
    await processTracker.killProcessesForEpisode(episodeId);
    
    state.status = 'paused';
    await this.updateState(episodeId, state);

    await this.emitSSEEvent({
      type: 'pipeline_paused',
      episodeId: episodeId.toString(),
    });
  }

  /**
   * Resume paused pipeline
   */
  async resumePipeline(episodeId: number, fromStage?: string): Promise<void> {
    const state = this.pipelineStates.get(episodeId);
    if (!state || state.status !== 'paused') {
      throw new Error('No paused pipeline found for this episode');
    }

    const episode = await prisma.podcastEpisode.findUnique({
      where: { id: episodeId },
      select: { pipelineType: true },
    });

    if (!episode) {
      throw new Error('Episode not found');
    }

    const pipelineType = episode.pipelineType as 'claude' | 'legacy';
    const stages = this.getStageDefinitions(pipelineType);
    
    // Find resume point
    let resumeIndex = 0;
    if (fromStage) {
      resumeIndex = stages.findIndex(s => s.id === fromStage);
      if (resumeIndex === -1) {
        throw new Error(`Invalid stage: ${fromStage}`);
      }
    } else {
      // Resume from next incomplete stage
      resumeIndex = stages.findIndex(s => !state.completedStages.includes(s.id));
    }

    if (resumeIndex === -1) {
      state.status = 'completed';
      await this.updateState(episodeId, state);
      return;
    }

    state.status = 'running';
    await this.updateState(episodeId, state);

    await this.emitSSEEvent({
      type: 'pipeline_resumed',
      episodeId: episodeId.toString(),
      fromStage: stages[resumeIndex].id,
    });

    // Continue execution from resume point
    this.executeStagesSequentially(episodeId, stages.slice(resumeIndex), {});
  }

  /**
   * Cancel pipeline execution
   */
  async cancelPipeline(episodeId: number): Promise<void> {
    const state = this.pipelineStates.get(episodeId);
    if (!state) {
      throw new Error('No pipeline found for this episode');
    }

    // Kill running processes
    await processTracker.killProcessesForEpisode(episodeId);
    
    state.status = 'cancelled';
    state.completedAt = new Date();
    await this.updateState(episodeId, state);

    await this.emitSSEEvent({
      type: 'pipeline_cancelled',
      episodeId: episodeId.toString(),
    });
  }

  /**
   * Get pipeline state
   */
  getPipelineState(episodeId: number): PipelineState | null {
    return this.pipelineStates.get(episodeId) || null;
  }

  /**
   * Check if pipeline is running
   */
  isPipelineRunning(episodeId: number): boolean {
    const state = this.pipelineStates.get(episodeId);
    return state?.status === 'running' || state?.status === 'validating';
  }

  /**
   * Get pipeline stages for episode
   */
  async getPipelineStages(episodeId: number): Promise<PipelineStage[]> {
    const episode = await prisma.podcastEpisode.findUnique({
      where: { id: episodeId },
      select: { pipelineType: true },
    });

    if (!episode) {
      throw new Error('Episode not found');
    }

    const pipelineType = episode.pipelineType as 'claude' | 'legacy';
    return this.getStageDefinitions(pipelineType);
  }

  /**
   * Update pipeline state in memory and database
   */
  private async updateState(episodeId: number, state: PipelineState): Promise<void> {
    this.pipelineStates.set(episodeId, state);

    // Update database
    await prisma.pipelineRun.upsert({
      where: { runId: state.runId },
      update: {
        status: state.status,
        currentStage: state.currentStage,
        progress: state.progress,
        errorMessage: state.errorMessage,
        completedAt: state.completedAt,
        metadata: {
          completedStages: state.completedStages,
          failedStages: state.failedStages,
          retryCount: state.retryCount,
          validationResults: state.validationResults,
        },
      },
      create: {
        runId: state.runId,
        episodeId: state.episodeId,
        stage: 'full_pipeline',
        status: state.status,
        currentStage: state.currentStage,
        progress: state.progress,
        startedAt: state.startedAt!,
        errorMessage: state.errorMessage,
        completedAt: state.completedAt,
        metadata: {
          completedStages: state.completedStages,
          failedStages: state.failedStages,
          retryCount: state.retryCount,
          validationResults: state.validationResults,
        },
      },
    });

    // Emit state update via SSE
    await this.emitSSEEvent({
      type: 'pipeline_state_updated',
      episodeId: episodeId.toString(),
      state: state,
    });
  }

  /**
   * Emit SSE event
   */
  private async emitSSEEvent(eventData: any): Promise<void> {
    try {
      await fetch(`${process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000'}/api/internal/events`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': process.env.WEB_API_KEY || 'development',
        },
        body: JSON.stringify(eventData),
      });
    } catch (error) {
      console.error('Failed to emit SSE event:', error);
    }
  }
}

// Export singleton instance
export const pipelineController = new PipelineController();