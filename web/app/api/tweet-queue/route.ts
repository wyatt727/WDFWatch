/**
 * Tweet Queue Management API
 * 
 * Provides endpoints for managing the persistent tweet queue:
 * - GET: List queued tweets with filtering
 * - POST: Add tweets to queue (manual or from scraping)
 * - PATCH: Update tweet priority or status
 * 
 * Related files:
 * - /web/app/(dashboard)/tweet-queue/page.tsx (UI)
 * - /src/wdf/tasks/queue_processor.py (Python processor)
 * - /web/lib/tweet-queue.ts (Queue utilities)
 */

import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { z } from 'zod'
import { getCurrentUserId } from '@/lib/auth'
import { emitEvent } from '@/lib/sse-events'

// Queue status enum
export enum QueueStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled'
}

// Queue source enum
export enum QueueSource {
  MANUAL = 'manual',
  SCRAPE = 'scrape',
  DIRECT_URL = 'direct_url',
  CACHE = 'cache'
}

// GET /api/tweet-queue - List queued tweets
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const status = searchParams.get('status') || 'pending'
    const limit = parseInt(searchParams.get('limit') || '50')
    const offset = parseInt(searchParams.get('offset') || '0')
    const episodeId = searchParams.get('episodeId')
    const includeOrphaned = searchParams.get('includeOrphaned') === 'true'

    // Build where clause
    const where: any = {}
    
    if (status !== 'all') {
      where.status = status
    }
    
    if (episodeId) {
      where.episodeId = parseInt(episodeId)
    } else if (includeOrphaned) {
      where.episodeId = null
    }

    // Fetch queued tweets with count
    const [items, total] = await Promise.all([
      prisma.$queryRaw`
        SELECT 
          q.id,
          q.tweet_id as "tweetId",
          q.twitter_id as "twitterId",
          q.source,
          q.priority,
          q.status,
          q.episode_id as "episodeId",
          q.added_by as "addedBy",
          q.added_at as "addedAt",
          q.processed_at as "processedAt",
          q.metadata,
          q.retry_count as "retryCount",
          t.full_text as "tweetText",
          t.author_handle as "authorHandle",
          t.author_name as "authorName",
          t.relevance_score as "relevanceScore",
          t.metrics,
          e.title as "episodeTitle"
        FROM tweet_queue q
        LEFT JOIN tweets t ON t.twitter_id = q.twitter_id
        LEFT JOIN podcast_episodes e ON e.id = q.episode_id
        WHERE 
          (${status} = 'all' OR q.status = ${status})
          AND (${!episodeId} OR q.episode_id = ${episodeId ? parseInt(episodeId) : null})
          AND (${!includeOrphaned} OR q.episode_id IS NULL)
        ORDER BY 
          CASE 
            WHEN q.status = 'processing' THEN 0
            WHEN q.status = 'pending' THEN 1
            ELSE 2
          END,
          q.priority DESC,
          q.added_at DESC
        LIMIT ${limit}
        OFFSET ${offset}
      `,
      prisma.$queryRaw<[{ count: bigint }]>`
        SELECT COUNT(*) as count
        FROM tweet_queue q
        WHERE 
          (${status} = 'all' OR q.status = ${status})
          AND (${!episodeId} OR q.episode_id = ${episodeId ? parseInt(episodeId) : null})
          AND (${!includeOrphaned} OR q.episode_id IS NULL)
      `
    ])

    // Calculate statistics
    const stats = await prisma.$queryRaw<any[]>`
      SELECT 
        status,
        COUNT(*) as count,
        AVG(priority) as avg_priority
      FROM tweet_queue
      GROUP BY status
    `

    return NextResponse.json({
      items,
      total: Number(total[0].count),
      limit,
      offset,
      stats: stats.reduce((acc, stat) => {
        acc[stat.status] = {
          count: Number(stat.count),
          avgPriority: parseFloat(stat.avg_priority || '0')
        }
        return acc
      }, {} as Record<string, any>)
    })
  } catch (error) {
    console.error('Failed to fetch tweet queue:', error)
    return NextResponse.json(
      { error: 'Failed to fetch tweet queue' },
      { status: 500 }
    )
  }
}

// POST /api/tweet-queue - Add tweets to queue
const AddToQueueSchema = z.object({
  tweets: z.array(z.object({
    twitterId: z.string(),
    source: z.enum(['manual', 'scrape', 'direct_url', 'cache']),
    priority: z.number().min(0).max(10).optional(),
    episodeId: z.number().optional(),
    metadata: z.record(z.any()).optional()
  })),
  processingOptions: z.object({
    autoProcess: z.boolean().default(false),
    batchSize: z.number().min(1).max(100).default(10)
  }).optional()
})

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const validated = AddToQueueSchema.parse(body)
    const userId = await getCurrentUserId()

    // Check for existing tweets in queue
    const existingTweetIds = await prisma.$queryRaw<{ twitter_id: string }[]>`
      SELECT twitter_id 
      FROM tweet_queue 
      WHERE 
        twitter_id IN (${validated.tweets.map(t => t.twitterId).join(',')})
        AND status != 'completed'
    `
    
    const existingSet = new Set(existingTweetIds.map(t => t.twitter_id))
    const newTweets = validated.tweets.filter(t => !existingSet.has(t.twitterId))

    if (newTweets.length === 0) {
      return NextResponse.json({
        message: 'All tweets already in queue',
        added: 0,
        skipped: validated.tweets.length
      })
    }

    // Calculate priority based on various factors
    const calculatePriority = (tweet: any): number => {
      let priority = tweet.priority || 5

      // Boost priority for manual additions
      if (tweet.source === 'manual') priority += 2
      
      // Boost priority for tweets with episodes
      if (tweet.episodeId) priority += 1

      return Math.min(10, priority)
    }

    // Add tweets to queue
    const queueEntries = newTweets.map(tweet => ({
      tweet_id: `${tweet.twitterId}-${Date.now()}`,
      twitter_id: tweet.twitterId,
      source: tweet.source,
      priority: calculatePriority(tweet),
      status: 'pending',
      episode_id: tweet.episodeId || null,
      added_by: userId,
      metadata: tweet.metadata || {},
      retry_count: 0
    }))

    await prisma.$executeRaw`
      INSERT INTO tweet_queue (
        tweet_id, twitter_id, source, priority, status, 
        episode_id, added_by, metadata, retry_count
      )
      VALUES ${queueEntries.map(entry => 
        `('${entry.tweet_id}', '${entry.twitter_id}', '${entry.source}', 
          ${entry.priority}, '${entry.status}', ${entry.episode_id}, 
          '${entry.added_by}', '${JSON.stringify(entry.metadata)}', ${entry.retry_count})`
      ).join(', ')}
    `

    // Log the queue update (SSE event type not defined for this yet)
    console.log('Tweets added to queue:', {
      added: newTweets.length,
      source: validated.tweets[0]?.source,
    })

    // Create audit log
    await prisma.auditLog.create({
      data: {
        action: 'ADD_TO_TWEET_QUEUE',
        resourceType: 'tweet_queue',
        resourceId: null,
        metadata: {
          tweetsAdded: newTweets.length,
          tweetsSkipped: validated.tweets.length - newTweets.length,
          source: validated.tweets[0]?.source
        },
        userId
      }
    })

    // Auto-process if requested
    if (validated.processingOptions?.autoProcess) {
      // Trigger Python processor asynchronously
      setTimeout(async () => {
        const { exec } = await import('child_process')
        const { promisify } = await import('util')
        const execAsync = promisify(exec)
        
        try {
          await execAsync(`python -m src.wdf.tasks.queue_processor --batch-size ${validated.processingOptions?.batchSize}`)
        } catch (error) {
          console.error('Failed to trigger queue processor:', error)
        }
      }, 1000)
    }

    return NextResponse.json({
      message: 'Tweets added to queue successfully',
      added: newTweets.length,
      skipped: validated.tweets.length - newTweets.length,
      queueEntries: queueEntries.map(e => e.tweet_id)
    })
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid request data', details: error.errors },
        { status: 400 }
      )
    }

    console.error('Failed to add tweets to queue:', error)
    return NextResponse.json(
      { error: 'Failed to add tweets to queue' },
      { status: 500 }
    )
  }
}

// PATCH /api/tweet-queue - Update queue entries
const UpdateQueueSchema = z.object({
  queueIds: z.array(z.string()),
  updates: z.object({
    status: z.enum(['pending', 'processing', 'completed', 'failed', 'cancelled']).optional(),
    priority: z.number().min(0).max(10).optional(),
    episodeId: z.number().nullable().optional(),
    retryCount: z.number().optional()
  })
})

export async function PATCH(request: NextRequest) {
  try {
    const body = await request.json()
    const validated = UpdateQueueSchema.parse(body)
    const userId = await getCurrentUserId()

    // Check if any updates are provided
    if (Object.keys(validated.updates).length === 0) {
      return NextResponse.json(
        { error: 'No updates provided' },
        { status: 400 }
      )
    }

    // Update queue entries using Prisma's updateMany
    const updateData: any = {}
    if (validated.updates.status !== undefined) {
      updateData.status = validated.updates.status
      if (validated.updates.status === 'processing') {
        updateData.processedAt = new Date()
      } else if (validated.updates.status === 'pending') {
        // Reset retry count when retrying
        updateData.retryCount = 0
      }
    }
    if (validated.updates.priority !== undefined) {
      updateData.priority = validated.updates.priority
    }
    if (validated.updates.episodeId !== undefined) {
      updateData.episodeId = validated.updates.episodeId
    }
    if (validated.updates.retryCount !== undefined) {
      updateData.retryCount = validated.updates.retryCount
    }

    const result = await prisma.tweetQueue.updateMany({
      where: {
        tweetId: {
          in: validated.queueIds
        }
      },
      data: updateData
    })

    // Log the queue update (SSE event type not defined for this yet)
    console.log('Queue entries updated:', {
      updated: validated.queueIds.length,
      changes: validated.updates
    })

    // Create audit log
    await prisma.auditLog.create({
      data: {
        action: 'UPDATE_TWEET_QUEUE',
        resourceType: 'tweet_queue',
        resourceId: validated.queueIds[0],
        metadata: {
          queueIds: validated.queueIds,
          updates: validated.updates
        },
        userId
      }
    })

    return NextResponse.json({
      message: 'Queue entries updated successfully',
      updated: result.count
    })
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid update data', details: error.errors },
        { status: 400 }
      )
    }

    console.error('Failed to update queue:', error)
    return NextResponse.json(
      { error: 'Failed to update queue' },
      { status: 500 }
    )
  }
}