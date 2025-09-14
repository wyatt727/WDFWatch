/**
 * API route handler for individual tweet operations
 * Handles tweet status updates with SSE event emission
 * Interacts with: Prisma database, SSE event system
 */

import { NextRequest, NextResponse } from "next/server"
import { prisma } from "@/lib/db"
import { SSEEvents } from "@/lib/sse-events"
import { TweetStatus } from "@/lib/types"

interface RouteParams {
  params: {
    id: string
  }
}

export async function GET(request: NextRequest, { params }: RouteParams) {
  try {
    const tweet = await prisma.tweet.findUnique({
      where: { twitterId: params.id },
      include: {
        drafts: {
          orderBy: { createdAt: "desc" },
        },
      },
    })

    if (!tweet) {
      return NextResponse.json({ error: "Tweet not found" }, { status: 404 })
    }

    // Transform to TweetDetail format
    const detail = {
      id: tweet.twitterId,
      authorHandle: tweet.authorHandle,
      textPreview: tweet.textPreview || tweet.fullText?.substring(0, 280) || "",
      fullText: tweet.fullText || "",
      createdAt: tweet.createdAt.toISOString(),
      relevanceScore: tweet.relevanceScore,
      status: tweet.status as TweetStatus,
      hasDraft: tweet.drafts.length > 0,
      flags: tweet.flags as any,
      thread: [], // TODO: Implement thread fetching
      classificationRationale: tweet.classificationRationale,
      drafts: tweet.drafts.map(draft => ({
        id: draft.id.toString(),
        model: draft.modelName,
        createdAt: draft.createdAt.toISOString(),
        version: draft.version,
        text: draft.text,
        styleScore: draft.styleScore,
        toxicityScore: draft.toxicityScore,
        superseded: draft.superseded,
      })),
    }

    return NextResponse.json(detail)
  } catch (error) {
    console.error("Failed to fetch tweet:", error)
    return NextResponse.json(
      { error: "Failed to fetch tweet" },
      { status: 500 }
    )
  }
}

export async function PATCH(request: NextRequest, { params }: RouteParams) {
  try {
    const body = await request.json()
    const { status } = body

    if (!status || !["unclassified", "skipped", "relevant", "drafted", "posted"].includes(status)) {
      return NextResponse.json(
        { error: "Invalid status" },
        { status: 400 }
      )
    }

    // Update tweet status
    const tweet = await prisma.tweet.update({
      where: { twitterId: params.id },
      data: {
        status,
        updatedAt: new Date(),
      },
    })

    // Emit SSE event for real-time update
    await SSEEvents.tweetStatusChanged(tweet.twitterId, status as TweetStatus)

    // Log audit event
    await prisma.auditLog.create({
      data: {
        action: "tweet_status_changed",
        resourceType: "tweet",
        resourceId: tweet.id,
        metadata: {
          oldStatus: tweet.status,
          newStatus: status,
        },
      },
    })

    return NextResponse.json({
      id: tweet.twitterId,
      status: tweet.status,
    })
  } catch (error) {
    console.error("Failed to update tweet:", error)
    return NextResponse.json(
      { error: "Failed to update tweet" },
      { status: 500 }
    )
  }
}