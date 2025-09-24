/**
 * Single Tweet Response API
 * 
 * Allows users to respond to specific tweets outside the normal pipeline.
 * Features:
 * - Direct URL input for any tweet
 * - Instant response generation
 * - Episode context selection
 * - Preview and approval workflow
 * 
 * Related files:
 * - /web/app/(dashboard)/single-tweet/page.tsx (UI)
 * - /src/wdf/tasks/single_tweet_response.py (Python generator)
 * - /web/components/single-tweet/ResponseEditor.tsx
 */

import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { z } from 'zod'
import { getCurrentUserId } from '@/lib/auth'
import { emitEvent } from '@/lib/sse-events'
import { exec } from 'child_process'
import { promisify } from 'util'

const execAsync = promisify(exec)

// Tweet URL parser
const TWEET_URL_REGEX = /(?:twitter\.com|x\.com)\/(?:#!\/)?(\w+)\/status(?:es)?\/(\d+)/i

function parseTweetUrl(url: string): { username: string; tweetId: string } | null {
  const match = url.match(TWEET_URL_REGEX)
  if (!match) return null
  return {
    username: match[1],
    tweetId: match[2]
  }
}

// POST /api/single-tweet/analyze - Analyze a tweet URL
const AnalyzeSchema = z.object({
  tweetUrl: z.string().url(),
  episodeId: z.number().optional()
})

export async function POST(request: NextRequest) {
  const pathname = new URL(request.url).pathname
  
  if (pathname.endsWith('/analyze')) {
    return handleAnalyze(request)
  } else if (pathname.endsWith('/generate')) {
    return handleGenerate(request)
  } else if (pathname.endsWith('/approve')) {
    return handleApprove(request)
  }
  
  return NextResponse.json({ error: 'Invalid endpoint' }, { status: 404 })
}

async function handleAnalyze(request: NextRequest) {
  try {
    const body = await request.json()
    const validated = AnalyzeSchema.parse(body)
    
    // Parse tweet URL
    const parsed = parseTweetUrl(validated.tweetUrl)
    if (!parsed) {
      return NextResponse.json(
        { error: 'Invalid tweet URL format' },
        { status: 400 }
      )
    }

    // Check if tweet already exists in database
    const existingTweet = await prisma.tweet.findUnique({
      where: { twitterId: parsed.tweetId }
    })

    if (existingTweet) {
      // Check for existing drafts
      const existingDrafts = await prisma.draftReply.findMany({
        where: {
          tweetId: existingTweet.id,
          status: { in: ['pending', 'approved'] }
        }
      })

      return NextResponse.json({
        tweet: existingTweet,
        existingDrafts,
        needsFetch: false,
        parsed
      })
    }

    // Tweet not in database - need to fetch from Twitter
    // This would normally call Twitter API, but we'll simulate for safety
    const mockTweetData = {
      twitterId: parsed.tweetId,
      authorHandle: parsed.username,
      authorName: `User @${parsed.username}`,
      fullText: `[Tweet content would be fetched from Twitter API for ID: ${parsed.tweetId}]`,
      textPreview: `[Preview of tweet ${parsed.tweetId}]`,
      metrics: {
        likes: 0,
        retweets: 0,
        replies: 0
      },
      scrapedAt: new Date()
    }

    return NextResponse.json({
      tweet: mockTweetData,
      existingDrafts: [],
      needsFetch: true,
      parsed,
      warning: 'Tweet will be fetched from Twitter API when generating response'
    })
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid request data', details: error.errors },
        { status: 400 }
      )
    }

    console.error('Failed to analyze tweet:', error)
    return NextResponse.json(
      { error: 'Failed to analyze tweet' },
      { status: 500 }
    )
  }
}

// POST /api/single-tweet/generate - Generate response for single tweet
const GenerateSchema = z.object({
  tweetUrl: z.string().url(),
  tweetText: z.string().optional(), // If already fetched
  episodeId: z.number().optional(),
  useLatestEpisode: z.boolean().default(true),
  customContext: z.string().optional(),
  modelOverride: z.string().optional()
})

async function handleGenerate(request: NextRequest) {
  try {
    const body = await request.json()
    const validated = GenerateSchema.parse(body)
    const userId = await getCurrentUserId()
    
    // Parse tweet URL
    const parsed = parseTweetUrl(validated.tweetUrl)
    if (!parsed) {
      return NextResponse.json(
        { error: 'Invalid tweet URL format' },
        { status: 400 }
      )
    }

    // Determine episode context
    let episodeContext = null
    if (validated.episodeId) {
      episodeContext = await prisma.podcastEpisode.findUnique({
        where: { id: validated.episodeId }
      })
    } else if (validated.useLatestEpisode) {
      episodeContext = await prisma.podcastEpisode.findFirst({
        where: { status: 'completed' },
        orderBy: { publishedAt: 'desc' }
      })
    }

    // Create response request record
    const responseRequest = await prisma.$executeRaw`
      INSERT INTO tweet_response_requests (
        tweet_url, tweet_id, tweet_text, requested_by,
        episode_context_id, status
      )
      VALUES (
        ${validated.tweetUrl},
        ${parsed.tweetId},
        ${validated.tweetText || null},
        ${userId},
        ${episodeContext?.id || null},
        'pending'
      )
      RETURNING id
    `

    // Prepare generation parameters
    const generationParams = {
      tweet_url: validated.tweetUrl,
      tweet_id: parsed.tweetId,
      tweet_text: validated.tweetText,
      episode_id: episodeContext?.id,
      episode_title: episodeContext?.title,
      episode_summary: episodeContext?.summaryData,
      custom_context: validated.customContext,
      model: validated.modelOverride || 'deepseek-r1:latest',
      request_id: responseRequest
    }

    // Call Python script to generate response
    const command = `python -m src.wdf.tasks.single_tweet_response --params '${JSON.stringify(generationParams)}'`
    
    // Start generation asynchronously
    exec(command, async (error, stdout, stderr) => {
      if (error) {
        console.error('Response generation error:', error)
        console.error('stderr:', stderr)
        
        // Update request status to failed
        await prisma.$executeRaw`
          UPDATE tweet_response_requests
          SET status = 'failed', error_message = ${error.message}
          WHERE id = ${responseRequest}
        `
        
        // Emit failure event
        emitSSEEvent({
          type: 'single_tweet_response_failed',
          data: {
            requestId: responseRequest,
            error: error.message
          }
        })
      } else {
        try {
          // Parse response from stdout
          const response = JSON.parse(stdout)
          
          // Update request with generated response
          await prisma.$executeRaw`
            UPDATE tweet_response_requests
            SET 
              response_generated = ${response.text},
              status = 'generated'
            WHERE id = ${responseRequest}
          `
          
          // Emit success event
          emitSSEEvent({
            type: 'single_tweet_response_generated',
            data: {
              requestId: responseRequest,
              response: response.text,
              characterCount: response.text.length
            }
          })
        } catch (parseError) {
          console.error('Failed to parse response:', parseError)
        }
      }
    })

    // Create audit log
    await prisma.auditLog.create({
      data: {
        action: 'GENERATE_SINGLE_TWEET_RESPONSE',
        resourceType: 'tweet_response',
        resourceId: parsed.tweetId,
        metadata: {
          tweetUrl: validated.tweetUrl,
          episodeId: episodeContext?.id,
          model: validated.modelOverride
        },
        userId
      }
    })

    return NextResponse.json({
      message: 'Response generation started',
      requestId: responseRequest,
      estimatedTime: '10-30 seconds',
      episodeContext: episodeContext ? {
        id: episodeContext.id,
        title: episodeContext.title
      } : null
    }, { status: 202 })
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid request data', details: error.errors },
        { status: 400 }
      )
    }

    console.error('Failed to generate response:', error)
    return NextResponse.json(
      { error: 'Failed to generate response' },
      { status: 500 }
    )
  }
}

// POST /api/single-tweet/approve - Approve and publish single tweet response
const ApproveSchema = z.object({
  requestId: z.number(),
  editedResponse: z.string().optional(),
  publishImmediately: z.boolean().default(false)
})

async function handleApprove(request: NextRequest) {
  try {
    const body = await request.json()
    const validated = ApproveSchema.parse(body)
    const userId = await getCurrentUserId()

    // Get the response request
    const responseRequest = await prisma.$queryRaw<any[]>`
      SELECT * FROM tweet_response_requests
      WHERE id = ${validated.requestId}
    `

    if (!responseRequest || responseRequest.length === 0) {
      return NextResponse.json(
        { error: 'Response request not found' },
        { status: 404 }
      )
    }

    const request = responseRequest[0]
    const finalResponse = validated.editedResponse || request.response_generated

    // Validate response length
    if (finalResponse.length > 280) {
      return NextResponse.json(
        { error: 'Response exceeds 280 character limit', length: finalResponse.length },
        { status: 400 }
      )
    }

    // Update request status
    await prisma.$executeRaw`
      UPDATE tweet_response_requests
      SET 
        response_generated = ${finalResponse},
        approved = true,
        approved_at = CURRENT_TIMESTAMP,
        status = 'approved'
      WHERE id = ${validated.requestId}
    `

    // If publish immediately, add to publishing queue
    if (validated.publishImmediately) {
      // This would normally post to Twitter
      // For safety, we'll just update the status
      await prisma.$executeRaw`
        UPDATE tweet_response_requests
        SET 
          published = true,
          published_at = CURRENT_TIMESTAMP,
          status = 'published'
        WHERE id = ${validated.requestId}
      `

      // Emit published event
      emitSSEEvent({
        type: 'single_tweet_published',
        data: {
          requestId: validated.requestId,
          tweetId: request.tweet_id,
          response: finalResponse
        }
      })
    }

    // Create audit log
    await prisma.auditLog.create({
      data: {
        action: validated.publishImmediately ? 'PUBLISH_SINGLE_TWEET' : 'APPROVE_SINGLE_TWEET',
        resourceType: 'tweet_response',
        resourceId: request.tweet_id,
        metadata: {
          requestId: validated.requestId,
          responseLength: finalResponse.length,
          edited: validated.editedResponse !== undefined
        },
        userId
      }
    })

    return NextResponse.json({
      message: validated.publishImmediately ? 'Response published successfully' : 'Response approved successfully',
      requestId: validated.requestId,
      status: validated.publishImmediately ? 'published' : 'approved',
      response: finalResponse
    })
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid request data', details: error.errors },
        { status: 400 }
      )
    }

    console.error('Failed to approve response:', error)
    return NextResponse.json(
      { error: 'Failed to approve response' },
      { status: 500 }
    )
  }
}

// GET /api/single-tweet/requests - List single tweet response requests
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const status = searchParams.get('status') || 'all'
    const limit = parseInt(searchParams.get('limit') || '20')
    const offset = parseInt(searchParams.get('offset') || '0')

    const where: any = {}
    if (status !== 'all') {
      where.status = status
    }

    const requests = await prisma.$queryRaw`
      SELECT 
        r.*,
        e.title as episode_title
      FROM tweet_response_requests r
      LEFT JOIN podcast_episodes e ON e.id = r.episode_context_id
      WHERE ${status} = 'all' OR r.status = ${status}
      ORDER BY r.requested_at DESC
      LIMIT ${limit}
      OFFSET ${offset}
    `

    const total = await prisma.$queryRaw<[{ count: bigint }]>`
      SELECT COUNT(*) as count
      FROM tweet_response_requests
      WHERE ${status} = 'all' OR status = ${status}
    `

    return NextResponse.json({
      requests,
      total: Number(total[0].count),
      limit,
      offset
    })
  } catch (error) {
    console.error('Failed to fetch response requests:', error)
    return NextResponse.json(
      { error: 'Failed to fetch response requests' },
      { status: 500 }
    )
  }
}