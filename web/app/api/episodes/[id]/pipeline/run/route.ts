/**
 * Individual Pipeline Stage Execution API Route
 * 
 * Runs individual pipeline stages for an episode with real-time updates.
 * Integrates with: Python task modules via subprocess, SSE for progress updates
 */

import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';
import { z } from 'zod';
import { spawn, ChildProcess } from 'child_process';
import { join } from 'path';
import { processTracker } from '@/lib/process-tracker';
import { ProcessTracker } from '@/lib/process-tracker';
import { apiClient } from '@/lib/api-client';
import { eventEmitter } from '@/lib/event-emitter';

// Schema for stage execution request
const legacyStageSchema = z.object({
  stageId: z.enum(['summarization', 'fewshot', 'scraping', 'classification', 'response', 'moderation']),
  useCached: z.boolean().optional().default(false),
  force: z.boolean().optional().default(false),
  forceRefresh: z.boolean().optional().default(false), // For scraping: ignore cache
});

const claudeStageSchema = z.object({
  stageId: z.enum(['summarization', 'scraping', 'classification', 'response', 'moderation', 'full']),
  useCached: z.boolean().optional().default(false),
  force: z.boolean().optional().default(false),
  forceRefresh: z.boolean().optional().default(false), // For scraping: ignore cache
});

// Stage to Python task mapping for legacy pipeline
const LEGACY_STAGE_TO_TASK: Record<string, string> = {
  'summarization': 'src/wdf/tasks/summarise.py',
  'fewshot': 'src/wdf/tasks/fewshot.py',
  'scraping': 'src/wdf/tasks/scrape.py',
  'classification': 'src/wdf/tasks/classify.py',
  'response': 'src/wdf/tasks/deepseek.py',
  'moderation': 'src/wdf/tasks/web_moderation.py',
};

// Stage to Claude pipeline mapping
const CLAUDE_STAGE_TO_TASK: Record<string, string> = {
  'summarization': 'web/scripts/claude_pipeline_bridge.py --stage summarize',
  'classification': 'web/scripts/claude_pipeline_bridge.py --stage classify',
  'response': 'web/scripts/claude_pipeline_bridge.py --stage respond',
  'moderation': 'web/scripts/claude_pipeline_bridge.py --stage moderate',
  'full': 'web/scripts/claude_pipeline_bridge.py --stage full',
};

// Map web UI stage names to Claude pipeline stage names
const WEB_TO_CLAUDE_STAGE_MAP: Record<string, string> = {
  'summarization': 'summarize',
  'classification': 'classify',
  'response': 'respond',
  'moderation': 'moderate',
  'full': 'full',
};

// Process tracking is now handled by the shared processTracker

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const episodeId = parseInt(params.id);
    const body = await request.json();
    
    // Check if episode exists and get pipeline type
    const episode = await prisma.podcastEpisode.findUnique({
      where: { id: episodeId },
      select: {
        id: true,
        title: true,
        pipelineType: true,
        claudeEpisodeDir: true,
        episodeDir: true,
      },
    });
    
    if (!episode) {
      return NextResponse.json(
        { error: 'Episode not found' },
        { status: 404 }
      );
    }

    // Validate input based on pipeline type
    const isClaudePipeline = episode.pipelineType === 'claude';
    let stageId: string, useCached: boolean, force: boolean, forceRefresh: boolean;
    
    if (isClaudePipeline) {
      const { stageId: claudeStageId, useCached: claudeUseCached, force: claudeForce, forceRefresh: claudeForceRefresh } = claudeStageSchema.parse(body);
      stageId = claudeStageId;
      useCached = claudeUseCached;
      force = claudeForce;
      forceRefresh = claudeForceRefresh;
    } else {
      const { stageId: legacyStageId, useCached: legacyUseCached, force: legacyForce, forceRefresh: legacyForceRefresh } = legacyStageSchema.parse(body);
      stageId = legacyStageId;
      useCached = legacyUseCached;
      force = legacyForce;
      forceRefresh = legacyForceRefresh;
    }
    
    // Check if stage is already running
    if (processTracker.isStageRunning(episodeId, stageId)) {
      return NextResponse.json(
        { error: 'Stage is already running for this episode' },
        { status: 400 }
      );
    }
    
    // Generate run ID
    const runId = `episode-${episodeId}-${stageId}-${Date.now()}`;
    
    // Create pipeline run record
    await prisma.pipelineRun.create({
      data: {
        runId,
        episodeId,
        stage: stageId,
        status: 'running',
        startedAt: new Date(),
      },
    });
    
    // Create audit log entry
    await prisma.auditLog.create({
      data: {
        action: 'pipeline_stage_started',
        resourceType: 'episode',
        resourceId: episodeId,
        metadata: {
          runId,
          stage: stageId,
          useCached,
          force,
        },
      },
    });
    
    // Emit SSE event for stage start
    await emitSSEEvent({
      type: 'pipeline_stage_started',
      episodeId: episodeId.toString(),
      stage: stageId,
      runId,
    });
    
    // Spawn appropriate pipeline process
    const pythonPath = process.env.PYTHON_PATH || 'python';
    let taskProcess;
    
    // Special case: For scraping, always use the legacy scraping task even for Claude pipeline
    // episodes, because the Claude pipeline doesn't implement real Twitter API scraping
    if (stageId === 'scraping') {
      // Always use legacy scraping task for real Twitter API calls
      // Run as a module to fix relative imports
      const args = ['-m', 'src.wdf.tasks.scrape'];
      if (force) args.push('--force');
      
      // Add force-refresh flag to ignore cache if checked
      if (forceRefresh) args.push('--force-refresh');
      
      // Add manual_trigger flag to actually call Twitter API
      args.push('--manual-trigger');
      args.push('--episode-id', episodeId.toString());
      console.log('Using legacy scraping task for real Twitter API calls', episodeId, { forceRefresh });
      
      taskProcess = spawn(pythonPath, args, {
        cwd: join(process.cwd(), '..'),
        env: {
          ...process.env,
          WDF_WEB_MODE: 'true',
          WDF_EPISODE_ID: episodeId.toString(),
          WDF_RUN_ID: runId,
          // Strip Prisma-specific query parameters that psycopg2 doesn't understand
          DATABASE_URL: (process.env.DATABASE_URL || '').split('?')[0],
          WEB_URL: process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000',
        },
      });
    } else if (isClaudePipeline) {
      // Use FastAPI backend for Claude pipeline stages
      const claudeStage = WEB_TO_CLAUDE_STAGE_MAP[stageId] || stageId;
      
      // Map stage names to backend stage names
      const backendStages: Record<string, string[]> = {
        'summarize': ['summarize'],
        'classify': ['classify'],
        'respond': ['respond'],
        'moderate': ['moderate'],
        'full': ['summarize', 'classify', 'respond'],
      };
      
      const stagesToRun = backendStages[claudeStage] || [claudeStage];
      
      try {
        // Call FastAPI backend to run pipeline stages
        const response = await apiClient.runPipeline(
          episode.claudeEpisodeDir || episodeId.toString(),
          {
            stages: stagesToRun as any,
            force: force || false,
            skip_scraping: !forceRefresh, // If forceRefresh, don't skip scraping
            skip_moderation: false,
          }
        );
        
        // Get job status for tracking
        const jobStatus = await apiClient.getPipelineStatus(
          episode.claudeEpisodeDir || episodeId.toString(),
          response.job_id
        );
        
        // Store job ID for tracking
        await prisma.pipelineRun.update({
          where: { id: (await prisma.pipelineRun.findFirst({ where: { runId } }))?.id || 0 },
          data: {
            metadata: {
              ...((await prisma.pipelineRun.findFirst({ where: { runId } }))?.metadata as any || {}),
              backendJobId: response.job_id,
            },
          },
        });
        
        // Emit success event
        await eventEmitter.broadcast({
          type: 'pipeline_stage_started',
          episodeId: episodeId.toString(),
          stage: stageId,
          runId,
          backendJobId: response.job_id,
        });
        
        return NextResponse.json({
          message: `Started ${stageId} stage for episode ${episodeId}`,
          episodeId,
          runId,
          stage: stageId,
          backendJobId: response.job_id,
        });
        
      } catch (apiError: any) {
        console.error('Failed to start pipeline via FastAPI:', apiError);
        
        // Update pipeline run record with error
        await prisma.pipelineRun.update({
          where: { id: (await prisma.pipelineRun.findFirst({ where: { runId } }))?.id || 0 },
          data: {
            status: 'failed',
            errorMessage: apiError.message || 'Failed to start pipeline',
            completedAt: new Date(),
          },
        });
        
        // Emit error event
        await eventEmitter.broadcast({
          type: 'pipeline_stage_error',
          episodeId: episodeId.toString(),
          stage: stageId,
          runId,
          error: apiError.message || 'Failed to start pipeline',
        });
        
        return NextResponse.json(
          { error: apiError.message || 'Failed to start pipeline stage' },
          { status: 500 }
        );
      }
    } else {
      // Use legacy pipeline tasks
      const stageToTaskMap = LEGACY_STAGE_TO_TASK;
      const taskPath = join(process.cwd(), '..', stageToTaskMap[stageId]);
      
      const args = [taskPath];
      if (force) args.push('--force');
      
      // For scraping stage, add manual_trigger flag to actually call Twitter API
      // and pass episode-id to ensure we use episode-specific keywords
      if (stageId === 'scraping') {
        args.push('--manual-trigger');
        args.push('--episode-id', episodeId.toString());
        console.log('Adding manual trigger flag and episode ID for scraping stage', episodeId);
      }
      
      taskProcess = spawn(pythonPath, args, {
        cwd: join(process.cwd(), '..'),
        env: {
          ...process.env,
          WDF_WEB_MODE: 'true',
          WDF_EPISODE_ID: episodeId.toString(),
          WDF_RUN_ID: runId,
          // Strip Prisma-specific query parameters that psycopg2 doesn't understand
          DATABASE_URL: (process.env.DATABASE_URL || '').split('?')[0],
          WEB_URL: process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000',
        },
      });
    }
    
    // Register the process with the tracker
    const processKey = ProcessTracker.getStageKey(episodeId, stageId);
    processTracker.register(processKey, {
      process: taskProcess,
      episodeId,
      type: 'stage',
      stage: stageId,
      runId,
      startedAt: new Date(),
    });
    
    // Log task output
    taskProcess.stdout.on('data', (data) => {
      console.log(`[${stageId}] stdout:`, data.toString());
      
      // Emit progress updates via SSE
      emitSSEEvent({
        type: 'pipeline_stage_progress',
        episodeId: episodeId.toString(),
        stage: stageId,
        runId,
        output: data.toString(),
      });
    });
    
    taskProcess.stderr.on('data', (data) => {
      console.error(`[${stageId}] stderr:`, data.toString());
      
      // Emit error updates via SSE
      emitSSEEvent({
        type: 'pipeline_stage_error',
        episodeId: episodeId.toString(),
        stage: stageId,
        runId,
        error: data.toString(),
      });
    });
    
    // Handle task completion
    taskProcess.on('close', async (code) => {
      // Unregister the process from tracker
      processTracker.unregister(processKey);
      
      const status = code === 0 ? 'completed' : 'failed';
      const completedAt = new Date();
      
      try {
        // Update pipeline run record
        const pipelineRun = await prisma.pipelineRun.findFirst({
          where: { runId },
        });
        
        if (pipelineRun) {
          const duration = completedAt.getTime() - pipelineRun.startedAt.getTime();
          
          await prisma.pipelineRun.update({
            where: { id: pipelineRun.id },
            data: {
              status,
              completedAt,
              errorMessage: code !== 0 ? `Process exited with code ${code}` : null,
              metrics: {
                duration,
                exitCode: code,
              },
            },
          });
        }
        
        // Create audit log entry
        await prisma.auditLog.create({
          data: {
            action: `pipeline_stage_${status}`,
            resourceType: 'episode',
            resourceId: episodeId,
            metadata: {
              runId,
              stage: stageId,
              exitCode: code,
            },
          },
        });
        
        // Emit SSE event for completion
        await emitSSEEvent({
          type: 'pipeline_stage_completed',
          episodeId: episodeId.toString(),
          stage: stageId,
          runId,
          status,
          exitCode: code,
        });
        
      } catch (error) {
        console.error('Failed to update pipeline run status:', error);
      }
    });
    
    return NextResponse.json({
      message: `Started ${stageId} stage for episode ${episodeId}`,
      episodeId,
      runId,
      stage: stageId,
    });
    
  } catch (error) {
    console.error('Failed to start pipeline stage:', error);
    
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid input', details: error.errors },
        { status: 400 }
      );
    }
    
    return NextResponse.json(
      { error: 'Failed to start pipeline stage' },
      { status: 500 }
    );
  }
}

// Helper function to emit SSE events
async function emitSSEEvent(eventData: any) {
  try {
    const sseResponse = await fetch(`${process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000'}/api/internal/events`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': process.env.WEB_API_KEY || 'development-internal-api-key',
      },
      body: JSON.stringify(eventData),
    });
    
    if (!sseResponse.ok) {
      console.error('Failed to emit SSE event:', eventData);
    }
  } catch (error) {
    console.error('Error emitting SSE event:', error);
  }
}