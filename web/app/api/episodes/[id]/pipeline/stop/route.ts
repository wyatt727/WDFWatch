/**
 * Stop Running Pipeline Processes API Route
 * 
 * Stops all running pipeline processes for an episode without deleting the episode.
 * Useful for canceling long-running tasks or freeing up resources.
 * Integrates with: processTracker for process management, database for audit logging
 */

import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';
import { z } from 'zod';
import { processTracker } from '@/lib/process-tracker';

// Schema for route params
const routeParamsSchema = z.object({
  id: z.string().transform((val) => parseInt(val, 10)),
});

export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    // Validate and parse episode ID
    const { id: episodeId } = routeParamsSchema.parse(params);
    
    // Check if episode exists
    const episode = await prisma.podcastEpisode.findUnique({
      where: { id: episodeId },
      select: { id: true, title: true, status: true },
    });
    
    if (!episode) {
      return NextResponse.json(
        { error: 'Episode not found' },
        { status: 404 }
      );
    }
    
    // Get list of running processes before killing them
    const runningProcesses = processTracker.getProcessesForEpisode(episodeId);
    
    if (runningProcesses.length === 0) {
      return NextResponse.json({
        message: 'No running processes found for this episode',
        episodeId,
        processesKilled: 0,
      });
    }
    
    console.log(`[Pipeline Stop] Stopping ${runningProcesses.length} processes for episode ${episodeId}`);
    
    // Create audit log entry for stop attempt
    await prisma.auditLog.create({
      data: {
        action: 'pipeline_stop_requested',
        resourceType: 'episode',
        resourceId: episodeId,
        metadata: {
          processCount: runningProcesses.length,
          processTypes: runningProcesses.map(p => ({
            type: p.type,
            stage: p.stage,
            runId: p.runId,
            startedAt: p.startedAt,
          })),
        },
      },
    });
    
    // Stop all running processes for this episode
    const killResult = await processTracker.killProcessesForEpisode(episodeId);
    
    console.log(`[Pipeline Stop] Kill result: ${killResult.killed} killed, ${killResult.failed.length} failed`);
    
    // Update episode status if it was processing
    if (episode.status === 'processing') {
      await prisma.podcastEpisode.update({
        where: { id: episodeId },
        data: { status: 'ready' },
      });
    }
    
    // Create audit log entry for completion
    await prisma.auditLog.create({
      data: {
        action: killResult.killed > 0 ? 'pipeline_stopped' : 'pipeline_stop_failed',
        resourceType: 'episode',
        resourceId: episodeId,
        metadata: {
          processesKilled: killResult.killed,
          processesFailed: killResult.failed.length,
          failedProcesses: killResult.failed,
        },
      },
    });
    
    // Emit SSE event for real-time updates
    try {
      const sseResponse = await fetch(
        `${process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000'}/api/internal/events`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-API-Key': process.env.WEB_API_KEY || 'development',
          },
          body: JSON.stringify({
            type: 'pipeline_stopped',
            episodeId,
            processesKilled: killResult.killed,
            processesFailed: killResult.failed.length,
          }),
        }
      );
      
      if (!sseResponse.ok) {
        console.error('Failed to emit SSE event for pipeline stop');
      }
    } catch (error) {
      console.error('Error emitting SSE event:', error);
    }
    
    // Return success response
    return NextResponse.json({
      message: killResult.killed > 0 
        ? `Successfully stopped ${killResult.killed} running processes`
        : 'No processes were running or all stop attempts failed',
      episodeId,
      processesKilled: killResult.killed,
      processesFailed: killResult.failed.length,
      failedProcesses: killResult.failed,
      episodeStatusUpdated: episode.status === 'processing',
    });
    
  } catch (error) {
    console.error('Failed to stop pipeline processes:', error);
    
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid episode ID' },
        { status: 400 }
      );
    }
    
    return NextResponse.json(
      { error: 'Failed to stop pipeline processes' },
      { status: 500 }
    );
  }
}