/**
 * Episode API Route (Individual)
 * 
 * Handles operations on individual episodes including deletion.
 * Integrates with: Database tables (episodes, tweets, drafts, keywords, pipeline_runs)
 */

import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';
import { z } from 'zod';
import { processTracker } from '@/lib/process-tracker';

// Schema for route params
const routeParamsSchema = z.object({
  id: z.string().transform((val) => parseInt(val, 10)),
});

export async function DELETE(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    // Validate and parse episode ID
    const { id: episodeId } = routeParamsSchema.parse(params);
    
    // Check if episode exists
    const episode = await prisma.podcastEpisode.findUnique({
      where: { id: episodeId },
      include: {
        _count: {
          select: {
            tweets: true,
            keywords_entries: true,
            pipelineRuns: true,
          },
        },
      },
    });
    
    if (!episode) {
      return NextResponse.json(
        { error: 'Episode not found' },
        { status: 404 }
      );
    }
    
    // Stop any running pipeline processes for this episode
    console.log(`[Episode Delete] Checking for running processes for episode ${episodeId}`);
    const killResult = await processTracker.killProcessesForEpisode(episodeId);
    
    if (killResult.killed > 0) {
      console.log(`[Episode Delete] Successfully killed ${killResult.killed} running processes`);
    }
    
    if (killResult.failed.length > 0) {
      console.warn(`[Episode Delete] Failed to kill ${killResult.failed.length} processes:`, killResult.failed);
    }

    // Handle stuck episodes (processing status but no running processes)
    let wasStuck = false;
    if (episode.status === 'processing' && killResult.killed === 0) {
      console.log(`[Episode Delete] Episode appears to be stuck in processing state without running processes`);
      wasStuck = true;
      
      // Calculate how long it's been stuck
      const ageInHours = (Date.now() - episode.updatedAt.getTime()) / (1000 * 60 * 60);
      console.log(`[Episode Delete] Episode has been in processing state for ${ageInHours.toFixed(1)} hours`);
    }

    // Create audit log entry for deletion attempt
    await prisma.auditLog.create({
      data: {
        action: 'episode_delete_started',
        resourceType: 'episode',
        resourceId: episodeId,
        oldValue: {
          title: episode.title,
          status: episode.status,
          tweetsCount: episode._count.tweets,
          keywordsCount: episode._count.keywords_entries,
          pipelineRunsCount: episode._count.pipelineRuns,
        },
        metadata: {
          videoUrl: episode.videoUrl,
          uploadedAt: episode.uploadedAt,
          processesKilled: killResult.killed,
          processKillFailures: killResult.failed,
          wasStuck: wasStuck,
          stuckAge: wasStuck ? (Date.now() - episode.updatedAt.getTime()) / (1000 * 60 * 60) : null,
        },
      },
    });
    
    // Delete in transaction to ensure data consistency
    await prisma.$transaction(async (tx) => {
      // Get all tweets for draft cleanup
      const tweets = await tx.tweet.findMany({
        where: { episodeId },
        select: { id: true },
      });

      const tweetIds = tweets.map(t => t.id);

      if (tweetIds.length > 0) {
        // Delete draft edits first (due to foreign key constraints)
        await tx.draftEdit.deleteMany({
          where: {
            draft: {
              tweetId: { in: tweetIds },
            },
          },
        });

        // Delete drafts
        await tx.draftReply.deleteMany({
          where: {
            tweetId: { in: tweetIds },
          },
        });
      }

      // Delete all episode-related records in dependency order
      // Start with basic tables and add more as needed

      // Delete Claude pipeline runs first (this was causing the constraint violation)
      await tx.claudePipelineRun.deleteMany({
        where: { episodeId },
      });

      // Delete pipeline runs
      await tx.pipelineRun.deleteMany({
        where: { episodeId },
      });

      // Delete tweets
      await tx.tweet.deleteMany({
        where: { episodeId },
      });

      // Delete keywords
      await tx.keyword.deleteMany({
        where: { episodeId },
      });

      // Finally, delete the episode
      await tx.podcastEpisode.delete({
        where: { id: episodeId },
      });
    });
    
    // Create audit log entry for successful deletion
    await prisma.auditLog.create({
      data: {
        action: 'episode_deleted',
        resourceType: 'episode',
        resourceId: episodeId,
        metadata: {
          title: episode.title,
          deletedAt: new Date().toISOString(),
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
            type: 'episode_deleted',
            episodeId,
            title: episode.title,
          }),
        }
      );
      
      if (!sseResponse.ok) {
        console.error('Failed to emit SSE event for episode deletion');
      }
    } catch (error) {
      console.error('Error emitting SSE event:', error);
    }
    
    return NextResponse.json({
      message: 'Episode deleted successfully',
      deletedId: episodeId,
    });
  } catch (error) {
    console.error('Failed to delete episode:', error);

    // More detailed error logging
    if (error instanceof Error) {
      console.error('Error name:', error.name);
      console.error('Error message:', error.message);
      if (error.stack) {
        console.error('Error stack:', error.stack);
      }
    }

    // Create audit log entry for failed deletion
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid episode ID' },
        { status: 400 }
      );
    }

    return NextResponse.json(
      { error: 'Failed to delete episode', details: error instanceof Error ? error.message : String(error) },
      { status: 500 }
    );
  }
}

// Schema for PATCH request body
const updateEpisodeSchema = z.object({
  claudeEpisodeDir: z.string().optional(),
  episodeDir: z.string().optional(),
  status: z.string().optional(),
  videoUrl: z.string().optional(),
});

export async function PATCH(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    // Validate and parse episode ID
    const { id: episodeId } = routeParamsSchema.parse(params);

    // Parse request body
    const body = await req.json();
    const updateData = updateEpisodeSchema.parse(body);

    // Check if episode exists
    const existingEpisode = await prisma.podcastEpisode.findUnique({
      where: { id: episodeId },
    });

    if (!existingEpisode) {
      return NextResponse.json(
        { error: 'Episode not found' },
        { status: 404 }
      );
    }

    // Update episode
    const updatedEpisode = await prisma.podcastEpisode.update({
      where: { id: episodeId },
      data: updateData,
    });

    // Create audit log entry
    await prisma.auditLog.create({
      data: {
        action: 'episode_updated',
        resourceType: 'episode',
        resourceId: episodeId,
        oldValue: {
          claudeEpisodeDir: existingEpisode.claudeEpisodeDir,
          episodeDir: existingEpisode.episodeDir,
          status: existingEpisode.status,
          videoUrl: existingEpisode.videoUrl,
        },
        newValue: updateData,
        metadata: {
          title: existingEpisode.title,
          updatedAt: new Date().toISOString(),
        },
      },
    });

    return NextResponse.json({
      id: updatedEpisode.id,
      title: updatedEpisode.title,
      claudeEpisodeDir: updatedEpisode.claudeEpisodeDir,
      episodeDir: updatedEpisode.episodeDir,
      status: updatedEpisode.status,
      videoUrl: updatedEpisode.videoUrl,
      updatedAt: updatedEpisode.updatedAt.toISOString(),
    });
  } catch (error) {
    console.error('Failed to update episode:', error);

    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid request data', details: error.errors },
        { status: 400 }
      );
    }

    return NextResponse.json(
      { error: 'Failed to update episode' },
      { status: 500 }
    );
  }
}

export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    // Validate and parse episode ID
    const { id: episodeId } = routeParamsSchema.parse(params);
    
    // Fetch episode with related counts
    const episode = await prisma.podcastEpisode.findUnique({
      where: { id: episodeId },
      include: {
        _count: {
          select: {
            tweets: true,
            keywords_entries: true,
            pipelineRuns: true,
          },
        },
        tweets: {
          where: { status: 'posted' },
          select: { id: true },
        },
      },
    });
    
    if (!episode) {
      return NextResponse.json(
        { error: 'Episode not found' },
        { status: 404 }
      );
    }
    
    // Transform the response
    const transformedEpisode = {
      id: episode.id,
      title: episode.title,
      uploadedAt: episode.uploadedAt.toISOString(),
      status: episode.status,
      videoUrl: episode.videoUrl,
      createdAt: episode.createdAt.toISOString(),
      updatedAt: episode.updatedAt.toISOString(),
      transcriptLength: episode.transcriptText?.length || 0,
      summaryLength: episode.summaryText?.length || 0,
      keywordCount: episode._count.keywords_entries,
      tweetCount: episode._count.tweets,
      postedCount: episode.tweets.length,
      pipelineRunCount: episode._count.pipelineRuns,
    };
    
    return NextResponse.json(transformedEpisode);
  } catch (error) {
    console.error('Failed to fetch episode:', error);
    
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid episode ID' },
        { status: 400 }
      );
    }
    
    return NextResponse.json(
      { error: 'Failed to fetch episode' },
      { status: 500 }
    );
  }
}