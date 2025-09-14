/**
 * Unified Pipeline Orchestrator API
 * 
 * Centralized control for full pipeline execution with:
 * - Start/stop/pause/resume operations
 * - Pre-flight validation
 * - Progress tracking
 * - Error recovery
 * - State management
 */

import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';
import { z } from 'zod';
import { pipelineController } from '@/lib/pipeline/controller';

export const dynamic = 'force-dynamic';

// Schema for pipeline control requests
const pipelineControlSchema = z.object({
  action: z.enum(['start', 'stop', 'pause', 'resume', 'validate', 'status']),
  options: z.object({
    force: z.boolean().optional(),
    skipValidation: z.boolean().optional(),
    retryFailedStages: z.boolean().optional(),
    notifyOnCompletion: z.boolean().optional(),
    maxRetries: z.number().min(1).max(10).optional(),
    concurrency: z.enum(['low', 'medium', 'high']).optional(),
    fromStage: z.string().optional(), // For resume action
  }).optional().default({}),
});

/**
 * POST - Control pipeline execution
 */
export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const episodeId = parseInt(params.id);
    const body = await request.json();
    const { action, options } = pipelineControlSchema.parse(body);

    // Validate episode exists
    const episode = await prisma.podcastEpisode.findUnique({
      where: { id: episodeId },
      select: {
        id: true,
        title: true,
        pipelineType: true,
        status: true,
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

    switch (action) {
      case 'start':
        return await handleStartPipeline(episodeId, episode, options);
      
      case 'stop':
        return await handleStopPipeline(episodeId);
      
      case 'pause':
        return await handlePausePipeline(episodeId);
      
      case 'resume':
        return await handleResumePipeline(episodeId, options.fromStage);
      
      case 'validate':
        return await handleValidatePipeline(episodeId, episode);
      
      case 'status':
        return await handleGetStatus(episodeId);
      
      default:
        return NextResponse.json(
          { error: `Unknown action: ${action}` },
          { status: 400 }
        );
    }

  } catch (error) {
    console.error('Pipeline orchestrator error:', error);
    
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid request', details: error.errors },
        { status: 400 }
      );
    }
    
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

/**
 * GET - Get pipeline status and progress
 */
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const episodeId = parseInt(params.id);
    return await handleGetStatus(episodeId);
  } catch (error) {
    console.error('Failed to get pipeline status:', error);
    return NextResponse.json(
      { error: 'Failed to get pipeline status' },
      { status: 500 }
    );
  }
}

/**
 * Handle start pipeline request
 */
async function handleStartPipeline(
  episodeId: number,
  episode: any,
  options: any
): Promise<NextResponse> {
  try {
    // Check if pipeline is already running
    if (pipelineController.isPipelineRunning(episodeId)) {
      return NextResponse.json(
        { error: 'Pipeline is already running for this episode' },
        { status: 400 }
      );
    }

    // Start the pipeline
    const result = await pipelineController.startFullPipeline(episodeId, options);

    // Create audit log
    await prisma.auditLog.create({
      data: {
        action: 'pipeline_started',
        resourceType: 'episode',
        resourceId: episodeId,
        metadata: {
          runId: result.runId,
          options: options,
          pipelineType: episode.pipelineType,
        },
      },
    });

    return NextResponse.json({
      success: true,
      message: 'Pipeline started successfully',
      runId: result.runId,
      state: result.state,
    });

  } catch (error) {
    console.error('Failed to start pipeline:', error);
    
    // Create error audit log
    await prisma.auditLog.create({
      data: {
        action: 'pipeline_start_failed',
        resourceType: 'episode',
        resourceId: episodeId,
        metadata: {
          error: error instanceof Error ? error.message : 'Unknown error',
          options: options,
        },
      },
    });

    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to start pipeline' },
      { status: 500 }
    );
  }
}

/**
 * Handle stop pipeline request
 */
async function handleStopPipeline(episodeId: number): Promise<NextResponse> {
  try {
    await pipelineController.cancelPipeline(episodeId);

    await prisma.auditLog.create({
      data: {
        action: 'pipeline_stopped',
        resourceType: 'episode',
        resourceId: episodeId,
        metadata: {
          triggeredBy: 'user_request',
        },
      },
    });

    return NextResponse.json({
      success: true,
      message: 'Pipeline stopped successfully',
    });

  } catch (error) {
    console.error('Failed to stop pipeline:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to stop pipeline' },
      { status: 500 }
    );
  }
}

/**
 * Handle pause pipeline request
 */
async function handlePausePipeline(episodeId: number): Promise<NextResponse> {
  try {
    await pipelineController.pausePipeline(episodeId);

    await prisma.auditLog.create({
      data: {
        action: 'pipeline_paused',
        resourceType: 'episode',
        resourceId: episodeId,
        metadata: {
          triggeredBy: 'user_request',
        },
      },
    });

    return NextResponse.json({
      success: true,
      message: 'Pipeline paused successfully',
    });

  } catch (error) {
    console.error('Failed to pause pipeline:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to pause pipeline' },
      { status: 500 }
    );
  }
}

/**
 * Handle resume pipeline request
 */
async function handleResumePipeline(
  episodeId: number, 
  fromStage?: string
): Promise<NextResponse> {
  try {
    await pipelineController.resumePipeline(episodeId, fromStage);

    await prisma.auditLog.create({
      data: {
        action: 'pipeline_resumed',
        resourceType: 'episode',
        resourceId: episodeId,
        metadata: {
          triggeredBy: 'user_request',
          fromStage: fromStage,
        },
      },
    });

    return NextResponse.json({
      success: true,
      message: 'Pipeline resumed successfully',
      fromStage: fromStage,
    });

  } catch (error) {
    console.error('Failed to resume pipeline:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to resume pipeline' },
      { status: 500 }
    );
  }
}

/**
 * Handle validate pipeline request
 */
async function handleValidatePipeline(
  episodeId: number,
  episode: any
): Promise<NextResponse> {
  try {
    const { validator } = await import('@/lib/pipeline/validator');
    const pipelineType = episode.pipelineType as 'claude' | 'legacy';
    
    const validationResults = await validator.validatePipeline(episodeId, pipelineType);

    // Store validation results
    await prisma.auditLog.create({
      data: {
        action: 'pipeline_validated',
        resourceType: 'episode',
        resourceId: episodeId,
        metadata: {
          validationResults: validationResults,
          isValid: validationResults.isValid,
          score: validationResults.score,
        },
      },
    });

    return NextResponse.json({
      success: true,
      validation: validationResults,
    });

  } catch (error) {
    console.error('Failed to validate pipeline:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to validate pipeline' },
      { status: 500 }
    );
  }
}

/**
 * Handle get status request
 */
async function handleGetStatus(episodeId: number): Promise<NextResponse> {
  try {
    // Get current pipeline state
    const pipelineState = pipelineController.getPipelineState(episodeId);
    
    // Get available stages
    const stages = await pipelineController.getPipelineStages(episodeId);
    
    // Get progress from progress tracker
    const { ProgressTracker } = await import('@/lib/pipeline/progress-tracker');
    const progressTracker = new ProgressTracker();
    const progress = await progressTracker.loadProgress(episodeId);
    
    // Get recent errors from error recovery manager
    const { ErrorRecoveryManager } = await import('@/lib/pipeline/error-recovery');
    const errorRecovery = new ErrorRecoveryManager();
    const recentErrors = await errorRecovery.getRecoveryHistory(episodeId, 5);
    
    // Get latest pipeline run from database
    const latestRun = await prisma.pipelineRun.findFirst({
      where: { episodeId },
      orderBy: { startedAt: 'desc' },
      include: {
        _count: {
          select: {
            errors: true,
          },
        },
      },
    });

    const status = {
      episodeId,
      isRunning: pipelineController.isPipelineRunning(episodeId),
      pipelineState: pipelineState,
      progress: progress,
      stages: stages,
      latestRun: latestRun ? {
        runId: latestRun.runId,
        status: latestRun.status,
        stage: latestRun.stage,
        currentStage: latestRun.currentStage,
        progress: latestRun.progress,
        startedAt: latestRun.startedAt,
        completedAt: latestRun.completedAt,
        errorMessage: latestRun.errorMessage,
        errorCount: latestRun._count.errors,
        metadata: latestRun.metadata,
      } : null,
      recentErrors: recentErrors,
      systemHealth: {
        activeProcesses: pipelineController.isPipelineRunning(episodeId),
        timestamp: new Date().toISOString(),
      },
    };

    return NextResponse.json(status);

  } catch (error) {
    console.error('Failed to get pipeline status:', error);
    return NextResponse.json(
      { error: 'Failed to get pipeline status' },
      { status: 500 }
    );
  }
}