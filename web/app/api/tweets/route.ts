/**
 * API route handler for tweets
 * Provides paginated tweet list with filtering
 * Interacts with: Prisma database client, Tweet components
 */

import { NextRequest, NextResponse } from "next/server"
import { prisma } from "@/lib/db"
import { TweetStatus } from "@/lib/types"

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const status = searchParams.get("status") as TweetStatus | null
    const cursor = searchParams.get("cursor")
    const limit = parseInt(searchParams.get("limit") || "20")

    // Build where clause
    const where = status ? { status } : {}

    // Fetch tweets with pagination
    const tweets = await prisma.tweet.findMany({
      where,
      take: limit + 1, // Fetch one extra to determine if there are more
      ...(cursor && {
        cursor: { id: parseInt(cursor) },
        skip: 1, // Skip the cursor item
      }),
      orderBy: { createdAt: "desc" },
      select: {
        id: true,
        twitterId: true,
        authorHandle: true,
        textPreview: true,
        createdAt: true,
        relevanceScore: true,
        status: true,
        flags: true,
        _count: {
          select: {
            drafts: {
              where: {
                status: "pending",
                superseded: false,
              },
            },
          },
        },
      },
    })

    // Check if there are more items
    const hasMore = tweets.length > limit
    const items = hasMore ? tweets.slice(0, -1) : tweets

    // Transform to API format
    const transformedItems = items.map((tweet) => ({
      id: tweet.twitterId,
      authorHandle: tweet.authorHandle,
      textPreview: tweet.textPreview || "",
      createdAt: tweet.createdAt.toISOString(),
      relevanceScore: tweet.relevanceScore,
      status: tweet.status as TweetStatus,
      hasDraft: tweet._count.drafts > 0,
      flags: tweet.flags as any,
    }))

    // Get next cursor
    const nextCursor = hasMore ? items[items.length - 1].id.toString() : undefined

    return NextResponse.json({
      items: transformedItems,
      nextCursor,
      hasMore,
    })
  } catch (error) {
    console.error("Failed to fetch tweets:", error)
    return NextResponse.json(
      { error: "Failed to fetch tweets" },
      { status: 500 }
    )
  }
}