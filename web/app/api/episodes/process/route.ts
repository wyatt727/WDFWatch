/**
 * Episode Processing API Route
 * 
 * Triggers the Python pipeline to process a podcast episode.
 * Integrates with: Python pipeline via subprocess
 */

import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';
import { z } from 'zod';
import { spawn } from 'child_process';
import { join } from 'path';
import { processTracker, ProcessTracker } from '@/lib/process-tracker';

// Schema for processing request
const processEpisodeSchema = z.object({
  episodeId: z.union([z.number(), z.string()]).transform((val) => String(val)),
});

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    
    // Validate input
    const { episodeId } = processEpisodeSchema.parse(body);
    
    // Check if episode exists
    const episode = await prisma.podcastEpisode.findUnique({
      where: { id: parseInt(episodeId) },
    });
    
    if (!episode) {
      return NextResponse.json(
        { error: 'Episode not found' },
        { status: 404 }
      );
    }
    
    if (episode.status === 'processing' || processTracker.isFullPipelineRunning(parseInt(episodeId))) {
      return NextResponse.json(
        { error: 'Episode is already being processed' },
        { status: 400 }
      );
    }
    
    // Generate run ID
    const runId = `episode-${episodeId}-${Date.now()}`;
    
    // Update episode status to processing
    await prisma.podcastEpisode.update({
      where: { id: parseInt(episodeId) },
      data: { status: 'processing' },
    });
    
    // Create audit log entry
    await prisma.auditLog.create({
      data: {
        action: 'episode_processing_started',
        resourceType: 'episode',
        resourceId: parseInt(episodeId),
        metadata: {
          runId: runId,
        },
      },
    });
    
    // Spawn Python pipeline process
    const pythonPath = process.env.PYTHON_PATH || 'python';
    const pipelinePath = join(process.cwd(), '..', 'main.py');
    
    const pipelineProcess = spawn(pythonPath, [
      pipelinePath,
      '--non-interactive',
      '--episode-id', episodeId,
    ], {
      cwd: join(process.cwd(), '..'),
      env: {
        ...process.env,
        WDF_WEB_MODE: 'true',
        DATABASE_URL: process.env.DATABASE_URL,
        WEB_URL: process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000',
      },
    });
    
    // Register the full pipeline process with the tracker
    const processKey = ProcessTracker.getFullPipelineKey(parseInt(episodeId), runId);
    processTracker.register(processKey, {
      process: pipelineProcess,
      episodeId: parseInt(episodeId),
      type: 'full_pipeline',
      runId,
      startedAt: new Date(),
    });
    
    // Log pipeline output
    pipelineProcess.stdout.on('data', (data) => {
      console.log(`Pipeline stdout: ${data}`);
    });
    
    pipelineProcess.stderr.on('data', (data) => {
      console.error(`Pipeline stderr: ${data}`);
    });
    
    // Handle pipeline completion
    pipelineProcess.on('close', async (code) => {
      // Unregister the process from tracker
      processTracker.unregister(processKey);
      
      const status = code === 0 ? 'completed' : 'failed';
      
      try {
        // Update episode status
        await prisma.podcastEpisode.update({
          where: { id: parseInt(episodeId) },
          data: { status: status },
        });
        
        // Create audit log entry
        await prisma.auditLog.create({
          data: {
            action: `episode_processing_${status}`,
            resourceType: 'episode',
            resourceId: parseInt(episodeId),
            metadata: {
              exitCode: code,
              runId: runId,
            },
          },
        });
        
        // Emit SSE event
        const sseResponse = await fetch(`${process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000'}/api/internal/events`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-API-Key': process.env.WEB_API_KEY || 'development',
          },
          body: JSON.stringify({
            type: 'episode_processing_complete',
            episodeId,
            status,
          }),
        });
        
        if (!sseResponse.ok) {
          console.error('Failed to emit SSE event');
        }
      } catch (error) {
        console.error('Failed to update episode status:', error);
      }
    });
    
    return NextResponse.json({
      message: 'Pipeline processing started',
      episodeId,
      runId: runId,
    });
  } catch (error) {
    console.error('Failed to start pipeline processing:', error);
    
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid input', details: error.errors },
        { status: 400 }
      );
    }
    
    return NextResponse.json(
      { error: 'Failed to start pipeline processing' },
      { status: 500 }
    );
  }
}