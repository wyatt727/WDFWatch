/**
 * Optimized API route handler for tweets with performance enhancements
 * Part of Phase 4 Performance Optimization
 * 
 * Connected files:
 * - /web/app/api/tweets/route.ts - Original API route
 * - /web/components/tweets/VirtualTweetInboxList.tsx - Consumer
 * - /web/lib/db.ts - Database connection
 */

import { NextRequest, NextResponse } from "next/server"
import { prisma } from "@/lib/db"
import { TweetStatus } from "@/lib/types"
import { unstable_cache } from 'next/cache'

export const dynamic = 'force-dynamic';

// Cache tweet counts for better performance
const getCachedTweetCount = unstable_cache(
  async (status?: TweetStatus) => {
    return prisma.tweet.count({
      where: status ? { status } : {}
    })
  },
  ['tweet-count'],
  {
    revalidate: 60, // Revalidate every minute
    tags: ['tweets']
  }
)

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const status = searchParams.get("status") as TweetStatus | null
    const cursor = searchParams.get("cursor")
    const limit = Math.min(parseInt(searchParams.get("limit") || "20"), 100) // Cap at 100
    const search = searchParams.get("search")
    const includeFullText = searchParams.get("includeFullText") === "true"
    
    // Build optimized where clause
    const where: any = {}
    
    if (status) {
      where.status = status
    }
    
    if (search && search.length > 2) { // Only search if term is > 2 chars
      where.OR = [
        { textPreview: { contains: search, mode: 'insensitive' } },
        { authorHandle: { contains: search, mode: 'insensitive' } },
        { fullText: { contains: search, mode: 'insensitive' } }
      ]
    }
    
    // Use parallel queries for better performance
    const [tweets, totalCount] = await Promise.all([
      // Main query with optimized field selection
      prisma.tweet.findMany({
        where,
        take: limit + 1,
        ...(cursor && {
          cursor: { id: parseInt(cursor) },
          skip: 1,
        }),
        orderBy: { id: "desc" }, // Use id instead of createdAt for better index usage
        select: {
          id: true,
          twitterId: true,
          authorHandle: true,
          authorName: true,
          textPreview: true,
          ...(includeFullText && { fullText: true }),
          createdAt: true,
          relevanceScore: true,
          status: true,
          flags: true,
          metrics: true,
          // Optimize draft count query
          drafts: {
            where: {
              status: "pending",
              superseded: false,
            },
            select: { id: true },
            take: 1, // We only need to know if there's at least one
          },
        },
      }),
      // Get total count for pagination info (cached)
      getCachedTweetCount(status || undefined)
    ])
    
    // Check if there are more items
    const hasMore = tweets.length > limit
    const items = hasMore ? tweets.slice(0, -1) : tweets
    
    // Transform to API format with minimal processing
    const transformedItems = items.map((tweet) => ({
      id: tweet.twitterId,
      dbId: tweet.id, // Include DB ID for virtual scrolling
      authorHandle: tweet.authorHandle,
      authorName: tweet.authorName,
      textPreview: tweet.textPreview || (tweet.fullText as string)?.substring(0, 280) || "",
      ...(includeFullText && { fullText: tweet.fullText }),
      createdAt: tweet.createdAt.toISOString(),
      relevanceScore: tweet.relevanceScore,
      status: tweet.status as TweetStatus,
      hasDraft: tweet.drafts.length > 0,
      flags: tweet.flags || {},
      metrics: tweet.metrics || {},
    }))
    
    // Get next cursor
    const nextCursor = hasMore ? items[items.length - 1].id.toString() : undefined
    
    // Calculate pagination metadata
    const currentPage = cursor ? undefined : 1
    const totalPages = Math.ceil(totalCount / limit)
    
    // Set cache headers for client-side caching
    const headers = new Headers()
    headers.set('Cache-Control', 'private, max-age=10, stale-while-revalidate=30')
    
    return NextResponse.json({
      items: transformedItems,
      nextCursor,
      hasMore,
      totalCount,
      totalPages,
      currentPage,
    }, { headers })
    
  } catch (error) {
    console.error("Failed to fetch tweets:", error)
    
    // More detailed error response for debugging
    const errorMessage = error instanceof Error ? error.message : "Unknown error"
    
    return NextResponse.json(
      { 
        error: "Failed to fetch tweets",
        details: process.env.NODE_ENV === 'development' ? errorMessage : undefined
      },
      { status: 500 }
    )
  }
}

// POST endpoint for batch operations (e.g., marking multiple as read)
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { action, tweetIds } = body
    
    if (!action || !Array.isArray(tweetIds)) {
      return NextResponse.json(
        { error: "Invalid request body" },
        { status: 400 }
      )
    }
    
    switch (action) {
      case 'markAsRead':
        await prisma.tweet.updateMany({
          where: {
            twitterId: { in: tweetIds },
            status: 'unclassified'
          },
          data: {
            status: 'skip'
          }
        })
        break
        
      case 'markAsRelevant':
        await prisma.tweet.updateMany({
          where: {
            twitterId: { in: tweetIds }
          },
          data: {
            status: 'relevant'
          }
        })
        break
        
      default:
        return NextResponse.json(
          { error: "Unknown action" },
          { status: 400 }
        )
    }
    
    // Revalidate cache
    return NextResponse.json({ success: true }, {
      headers: {
        'X-Revalidate-Tag': 'tweets'
      }
    })
    
  } catch (error) {
    console.error("Failed to update tweets:", error)
    return NextResponse.json(
      { error: "Failed to update tweets" },
      { status: 500 }
    )
  }
}