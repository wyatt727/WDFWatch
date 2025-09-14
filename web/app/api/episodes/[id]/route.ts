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
      // Delete all drafts associated with tweets from this episode
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
      
      // Delete tweets
      await tx.tweet.deleteMany({
        where: { episodeId },
      });
      
      // Delete keywords (should cascade automatically due to schema)
      await tx.keyword.deleteMany({
        where: { episodeId },
      });
      
      // Delete pipeline runs
      await tx.pipelineRun.deleteMany({
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
    
    // Create audit log entry for failed deletion
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid episode ID' },
        { status: 400 }
      );
    }
    
    return NextResponse.json(
      { error: 'Failed to delete episode' },
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