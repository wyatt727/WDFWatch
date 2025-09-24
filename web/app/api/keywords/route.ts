/**
 * API routes for managing keyword queries
 * 
 * Handles CRUD operations for tweet search keywords including:
 * - Listing all keywords with metadata
 * - Adding new keywords
 * - Bulk operations
 * 
 * Related files:
 * - /web/app/api/keywords/[id]/route.ts (Individual keyword operations)
 * - /web/components/keywords/KeywordManager.tsx (UI component)
 * - /src/wdf/tasks/scrape.py (Python scraping task)
 */

import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { getCurrentUserId } from '@/lib/auth'
import { z } from 'zod'

// Schema for keyword operations
const KeywordSchema = z.object({
  keyword: z.string().min(1).max(100),
  weight: z.number().min(0).max(1).default(1),
})

const BulkKeywordsSchema = z.object({
  keywords: z.array(KeywordSchema),
  episodeId: z.number(),
})

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const episodeId = searchParams.get('episodeId')

    // Build query filters
    const where: any = {}
    if (episodeId) where.episodeId = parseInt(episodeId)

    const keywords = await prisma.keyword.findMany({
      where,
      orderBy: [
        { weight: 'desc' },
        { createdAt: 'desc' },
      ],
      include: {
        episode: {
          select: {
            id: true,
            title: true,
          },
        },
      },
    })

    return NextResponse.json(keywords)
  } catch (error) {
    console.error('Failed to fetch keywords:', error)
    return NextResponse.json(
      { error: 'Failed to fetch keywords' },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    
    // Check if bulk operation
    if (Array.isArray(body.keywords)) {
      const validated = BulkKeywordsSchema.parse(body)
      
      // Create multiple keywords
      const created = await prisma.keyword.createMany({
        data: validated.keywords.map(kw => ({
          ...kw,
          episodeId: validated.episodeId,
        })),
        skipDuplicates: true,
      })

      // Log audit event
      await prisma.auditLog.create({
        data: {
          action: 'CREATE_BULK_KEYWORDS',
          resourceType: 'keyword',
          resourceId: null,
          metadata: {
            count: created.count,
            keywords: validated.keywords.map(k => k.keyword),
          },
          userId: await getCurrentUserId(),
        },
      })

      return NextResponse.json({ 
        message: `Created ${created.count} keywords`,
        count: created.count 
      })
    }

    // Single keyword creation
    const validated = KeywordSchema.parse(body)
    const episodeId = body.episodeId

    // Check for duplicates
    const existing = await prisma.keyword.findFirst({
      where: {
        keyword: validated.keyword,
        episodeId: episodeId || null,
      },
    })

    if (existing) {
      return NextResponse.json(
        { error: 'Keyword already exists' },
        { status: 409 }
      )
    }

    const keyword = await prisma.keyword.create({
      data: {
        ...validated,
        episodeId,
      },
      include: {
        episode: {
          select: {
            id: true,
            title: true,
          },
        },
      },
    })

    // Log audit event
    await prisma.auditLog.create({
      data: {
        action: 'CREATE_KEYWORD',
        resourceType: 'keyword',
        resourceId: keyword.id,
        metadata: {
          keyword: keyword.keyword,
          episodeId: keyword.episodeId,
        },
        userId: 'system', // TODO: Get from auth context
      },
    })

    return NextResponse.json(keyword, { status: 201 })
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid keyword data', details: error.errors },
        { status: 400 }
      )
    }

    console.error('Failed to create keyword:', error)
    return NextResponse.json(
      { error: 'Failed to create keyword' },
      { status: 500 }
    )
  }
}

// Bulk update operations
export async function PATCH(request: NextRequest) {
  try {
    const body = await request.json()
    const { action, keywordIds } = body

    if (!action || !Array.isArray(keywordIds)) {
      return NextResponse.json(
        { error: 'Invalid bulk operation' },
        { status: 400 }
      )
    }

    let result
    switch (action) {
      case 'update-usage':
        result = await prisma.keyword.updateMany({
          where: { id: { in: keywordIds } },
          data: { lastUsed: new Date() },
        })
        break
        
      case 'delete':
        result = await prisma.keyword.deleteMany({
          where: { id: { in: keywordIds } },
        })
        break
        
      default:
        return NextResponse.json(
          { error: 'Invalid action' },
          { status: 400 }
        )
    }

    // Log audit event
    await prisma.auditLog.create({
      data: {
        action: `BULK_${action.toUpperCase()}_KEYWORDS`,
        resourceType: 'keyword',
        resourceId: null,
        metadata: {
          count: result.count,
          keywordIds,
        },
        userId: 'system', // TODO: Get from auth context
      },
    })

    return NextResponse.json({ 
      message: `${action} ${result.count} keywords`,
      count: result.count 
    })
  } catch (error) {
    console.error('Failed to perform bulk operation:', error)
    return NextResponse.json(
      { error: 'Failed to perform bulk operation' },
      { status: 500 }
    )
  }
}