/**
 * Reset Stuck Episodes API Route
 * 
 * Finds and resets episodes that are stuck in 'processing' state without
 * corresponding running processes. This handles orphaned episodes from
 * before the process tracking system was implemented.
 * 
 * Integrates with: processTracker, database, audit logging
 */

import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';
import { z } from 'zod';
import { processTracker } from '@/lib/process-tracker';

// Schema for request body
const resetStuckSchema = z.object({
  dryRun: z.boolean().optional().default(false),
  olderThanHours: z.number().min(1).max(168).optional().default(24), // 1 hour to 1 week
});

interface StuckEpisode {
  id: number;
  title: string;
  status: string;
  updatedAt: Date;
  hasRunningProcess: boolean;
  ageInHours: number;
}

async function findStuckEpisodes(olderThanHours: number): Promise<StuckEpisode[]> {
  // Find episodes in processing state
  const processingEpisodes = await prisma.podcastEpisode.findMany({
    where: {
      status: 'processing',
    },
    select: {
      id: true,
      title: true,
      status: true,
      updatedAt: true,
    },
  });

  const stuckEpisodes: StuckEpisode[] = [];
  const cutoffTime = new Date(Date.now() - (olderThanHours * 60 * 60 * 1000));

  for (const episode of processingEpisodes) {
    // Check if there's actually a running process for this episode
    const runningProcesses = processTracker.getProcessesForEpisode(episode.id);
    const hasRunningProcess = runningProcesses.length > 0;

    // Calculate age
    const ageInHours = (Date.now() - episode.updatedAt.getTime()) / (1000 * 60 * 60);

    // Consider it stuck if:
    // 1. No running process AND older than cutoff time
    // 2. OR no running process AND older than 1 hour (for safety)
    const isStuck = !hasRunningProcess && (
      episode.updatedAt < cutoffTime || ageInHours > 1
    );

    if (isStuck) {
      stuckEpisodes.push({
        id: episode.id,
        title: episode.title,
        status: episode.status,
        updatedAt: episode.updatedAt,
        hasRunningProcess,
        ageInHours,
      });
    }
  }

  return stuckEpisodes;
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { dryRun, olderThanHours } = resetStuckSchema.parse(body);

    console.log(`[Reset Stuck Episodes] Starting scan (dry-run: ${dryRun}, older than: ${olderThanHours}h)`);

    // Find stuck episodes
    const stuckEpisodes = await findStuckEpisodes(olderThanHours);

    if (stuckEpisodes.length === 0) {
      return NextResponse.json({
        message: 'No stuck episodes found',
        stuckEpisodes: [],
        resetCount: 0,
        dryRun,
      });
    }

    // Create audit log for the scan
    await prisma.auditLog.create({
      data: {
        action: dryRun ? 'stuck_episodes_scan' : 'stuck_episodes_reset_started',
        resourceType: 'episode',
        resourceId: null,
        metadata: {
          stuckCount: stuckEpisodes.length,
          olderThanHours,
          dryRun,
          episodes: stuckEpisodes.map(ep => ({
            id: ep.id,
            title: ep.title,
            ageInHours: ep.ageInHours,
          })),
        },
      },
    });

    if (dryRun) {
      return NextResponse.json({
        message: `Found ${stuckEpisodes.length} stuck episodes (dry run)`,
        stuckEpisodes: stuckEpisodes.map(ep => ({
          id: ep.id,
          title: ep.title,
          status: ep.status,
          ageInHours: Math.round(ep.ageInHours * 10) / 10,
          lastUpdated: ep.updatedAt.toISOString(),
        })),
        resetCount: 0,
        dryRun: true,
      });
    }

    // Reset the stuck episodes
    const resetResults = await Promise.allSettled(
      stuckEpisodes.map(async (episode) => {
        // Reset episode status to 'ready'
        await prisma.podcastEpisode.update({
          where: { id: episode.id },
          data: { 
            status: 'ready',
            updatedAt: new Date(),
          },
        });

        // Create audit log entry for individual episode
        await prisma.auditLog.create({
          data: {
            action: 'episode_reset_from_stuck',
            resourceType: 'episode',
            resourceId: episode.id,
            oldValue: {
              status: episode.status,
              updatedAt: episode.updatedAt,
            },
            newValue: {
              status: 'ready',
              updatedAt: new Date(),
            },
            metadata: {
              ageInHours: episode.ageInHours,
              hadRunningProcess: episode.hasRunningProcess,
              resetReason: 'stuck_processing_without_running_process',
            },
          },
        });

        return { episodeId: episode.id, title: episode.title };
      })
    );

    const successful = resetResults.filter(r => r.status === 'fulfilled').length;
    const failed = resetResults.filter(r => r.status === 'rejected');

    // Create final audit log
    await prisma.auditLog.create({
      data: {
        action: 'stuck_episodes_reset_completed',
        resourceType: 'episode',
        resourceId: null,
        metadata: {
          totalFound: stuckEpisodes.length,
          successful,
          failed: failed.length,
          failures: failed.map(f => f.reason),
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
            type: 'stuck_episodes_reset',
            resetCount: successful,
            failedCount: failed.length,
          }),
        }
      );

      if (!sseResponse.ok) {
        console.error('Failed to emit SSE event for stuck episodes reset');
      }
    } catch (error) {
      console.error('Error emitting SSE event:', error);
    }

    return NextResponse.json({
      message: `Successfully reset ${successful} of ${stuckEpisodes.length} stuck episodes`,
      stuckEpisodes: stuckEpisodes.map(ep => ({
        id: ep.id,
        title: ep.title,
        status: ep.status,
        ageInHours: Math.round(ep.ageInHours * 10) / 10,
        lastUpdated: ep.updatedAt.toISOString(),
      })),
      resetCount: successful,
      failedCount: failed.length,
      dryRun: false,
    });

  } catch (error) {
    console.error('Failed to reset stuck episodes:', error);

    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid input', details: error.errors },
        { status: 400 }
      );
    }

    return NextResponse.json(
      { error: 'Failed to reset stuck episodes' },
      { status: 500 }
    );
  }
}

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const olderThanHours = parseInt(searchParams.get('olderThanHours') || '24');

    // Just find and return stuck episodes without resetting
    const stuckEpisodes = await findStuckEpisodes(olderThanHours);

    return NextResponse.json({
      stuckEpisodes: stuckEpisodes.map(ep => ({
        id: ep.id,
        title: ep.title,
        status: ep.status,
        ageInHours: Math.round(ep.ageInHours * 10) / 10,
        lastUpdated: ep.updatedAt.toISOString(),
        hasRunningProcess: ep.hasRunningProcess,
      })),
      count: stuckEpisodes.length,
    });

  } catch (error) {
    console.error('Failed to find stuck episodes:', error);
    return NextResponse.json(
      { error: 'Failed to find stuck episodes' },
      { status: 500 }
    );
  }
}