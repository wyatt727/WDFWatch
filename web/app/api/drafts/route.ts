/**
 * API route handler for draft replies
 * Provides draft management endpoints for listing and creating drafts
 * Interacts with: Prisma database client, Draft components, Pipeline integration
 */

import { NextRequest, NextResponse } from "next/server"
import { prisma } from "@/lib/db"
import { DraftStatus } from "@/lib/types"

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const status = searchParams.get("status") as DraftStatus | null
    const tweetId = searchParams.get("tweetId")
    const cursor = searchParams.get("cursor")
    const limit = parseInt(searchParams.get("limit") || "20")

    // Build where clause
    const where: any = {
      superseded: false, // Only get active drafts
    }
    
    // When filtering for approved, include both approved and posted statuses
    if (status === 'approved') {
      where.status = { in: ['approved', 'posted'] }
    } else if (status) {
      where.status = status
    }
    
    if (tweetId) where.tweetId = parseInt(tweetId)

    // Fetch drafts with pagination
    const drafts = await prisma.draftReply.findMany({
      where,
      take: limit + 1,
      ...(cursor && {
        cursor: { id: parseInt(cursor) },
        skip: 1,
      }),
      orderBy: { createdAt: "desc" },
      include: {
        tweet: {
          select: {
            id: true,
            twitterId: true,
            authorHandle: true,
            authorName: true,
            textPreview: true,
            fullText: true,
            metrics: true,
            relevanceScore: true,
            classificationRationale: true,
            threadData: true,
            createdAt: true,
          },
        },
      },
    })

    // Check if there are more items
    const hasMore = drafts.length > limit
    const items = hasMore ? drafts.slice(0, -1) : drafts

    // Transform to API format
    const transformedItems = items.map((draft) => {
      // Parse metrics if it exists
      const metrics = draft.tweet.metrics as any || {}
      
      return {
        id: draft.id.toString(),
        tweetId: draft.tweet.twitterId,
        text: draft.text,
        status: draft.status as DraftStatus,
        modelName: draft.modelName,
        model: draft.modelName, // Alias for compatibility
        version: 1, // Default version
        styleScore: draft.styleScore,
        toxicityScore: draft.toxicityScore,
        createdAt: draft.createdAt.toISOString(),
        updatedAt: draft.updatedAt.toISOString(),
        editHistory: [
          {
            version: 1,
            text: draft.text,
            editedAt: draft.createdAt.toISOString(),
          }
        ],
        tweet: {
          id: draft.tweet.twitterId,
          authorHandle: draft.tweet.authorHandle,
          authorName: draft.tweet.authorName,
          textPreview: draft.tweet.textPreview || draft.tweet.fullText?.substring(0, 280) || "",
          fullText: draft.tweet.fullText,
          likeCount: metrics.like_count || metrics.likeCount || 0,
          retweetCount: metrics.retweet_count || metrics.retweetCount || 0,
          replyCount: metrics.reply_count || metrics.replyCount || 0,
          relevanceScore: draft.tweet.relevanceScore,
          classificationRationale: draft.tweet.classificationRationale,
          threadData: draft.tweet.threadData,
          createdAt: draft.tweet.createdAt?.toISOString(),
        },
      }
    })

    // Get next cursor
    const nextCursor = hasMore ? items[items.length - 1].id.toString() : undefined

    return NextResponse.json({
      items: transformedItems,
      nextCursor,
      hasMore,
    })
  } catch (error) {
    console.error("Failed to fetch drafts:", error)
    return NextResponse.json(
      { error: "Failed to fetch drafts" },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { tweetId, text, modelName } = body

    if (!tweetId || !text || !modelName) {
      return NextResponse.json(
        { error: "Missing required fields" },
        { status: 400 }
      )
    }

    // Find the tweet by twitterId
    const tweet = await prisma.tweet.findUnique({
      where: { twitterId: tweetId },
      include: {
        drafts: {
          where: {
            superseded: false,
            status: {
              in: ['approved', 'posted', 'scheduled']
            }
          }
        }
      }
    })

    if (!tweet) {
      return NextResponse.json(
        { error: "Tweet not found" },
        { status: 404 }
      )
    }

    // Don't block creation if there's an approved/posted draft
    // The user clarified that generating new responses is OK, 
    // they just shouldn't overwrite approved ones

    // Use a transaction to ensure data consistency
    const draft = await prisma.$transaction(async (tx) => {
      // Mark any existing pending drafts as superseded
      await tx.draftReply.updateMany({
        where: {
          tweetId: tweet.id,
          status: 'pending',
          superseded: false
        },
        data: {
          superseded: true
        }
      })

      // Create the new draft
      return await tx.draftReply.create({
        data: {
          tweetId: tweet.id,
          text,
          modelName,
          status: "pending",
          superseded: false,
        },
      })
    })

    // Log to audit trail
    await prisma.auditLog.create({
      data: {
        action: "draft_created",
        resourceType: "draft",
        resourceId: draft.id,
        metadata: {
          tweetId: tweet.twitterId,
          modelName,
          textLength: text.length,
        },
      },
    })

    return NextResponse.json({
      id: draft.id.toString(),
      tweetId: tweet.twitterId,
      text: draft.text,
      status: draft.status,
      modelName: draft.modelName,
      createdAt: draft.createdAt.toISOString(),
    })
  } catch (error) {
    console.error("Failed to create draft:", error)
    return NextResponse.json(
      { error: "Failed to create draft" },
      { status: 500 }
    )
  }
}