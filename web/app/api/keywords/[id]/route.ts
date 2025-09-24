/**
 * API routes for individual keyword operations
 * 
 * Handles operations on specific keywords:
 * - Get keyword details
 * - Update keyword properties
 * - Delete keyword
 * 
 * Related files:
 * - /web/app/api/keywords/route.ts (Bulk operations)
 * - /web/components/keywords/KeywordManager.tsx (UI component)
 */

import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { getCurrentUserId } from '@/lib/auth'
import { z } from 'zod'

const UpdateKeywordSchema = z.object({
  keyword: z.string().min(1).max(100).optional(),
  weight: z.number().min(0).max(1).optional(),
  enabled: z.boolean().optional(),
})

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const keyword = await prisma.keyword.findUnique({
      where: { id: parseInt(params.id) },
      include: {
        episode: {
          select: {
            id: true,
            title: true,
          },
        },
      },
    })

    if (!keyword) {
      return NextResponse.json(
        { error: 'Keyword not found' },
        { status: 404 }
      )
    }

    return NextResponse.json(keyword)
  } catch (error) {
    console.error('Failed to fetch keyword:', error)
    return NextResponse.json(
      { error: 'Failed to fetch keyword' },
      { status: 500 }
    )
  }
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const body = await request.json()
    const validated = UpdateKeywordSchema.parse(body)

    // Check if keyword exists
    const existing = await prisma.keyword.findUnique({
      where: { id: parseInt(params.id) },
    })

    if (!existing) {
      return NextResponse.json(
        { error: 'Keyword not found' },
        { status: 404 }
      )
    }

    // Check for duplicate if keyword text is being changed
    if (validated.keyword && validated.keyword !== existing.keyword) {
      const duplicate = await prisma.keyword.findFirst({
        where: {
          keyword: validated.keyword,
          episodeId: existing.episodeId,
          NOT: { id: parseInt(params.id) },
        },
      })

      if (duplicate) {
        return NextResponse.json(
          { error: 'Keyword already exists' },
          { status: 409 }
        )
      }
    }

    const keyword = await prisma.keyword.update({
      where: { id: parseInt(params.id) },
      data: {
        ...validated,
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
        action: 'UPDATE_KEYWORD',
        resourceType: 'keyword',
        resourceId: keyword.id,
        metadata: {
          changes: validated,
          previous: {
            keyword: existing.keyword,
            weight: existing.weight,
          },
        },
        userId: await getCurrentUserId(),
      },
    })

    return NextResponse.json(keyword)
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid keyword data', details: error.errors },
        { status: 400 }
      )
    }

    console.error('Failed to update keyword:', error)
    return NextResponse.json(
      { error: 'Failed to update keyword' },
      { status: 500 }
    )
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const keyword = await prisma.keyword.findUnique({
      where: { id: parseInt(params.id) },
    })

    if (!keyword) {
      return NextResponse.json(
        { error: 'Keyword not found' },
        { status: 404 }
      )
    }

    await prisma.keyword.delete({
      where: { id: parseInt(params.id) },
    })

    // Log audit event
    await prisma.auditLog.create({
      data: {
        action: 'DELETE_KEYWORD',
        resourceType: 'keyword',
        resourceId: parseInt(params.id),
        metadata: {
          keyword: keyword.keyword,
          episodeId: keyword.episodeId,
        },
        userId: await getCurrentUserId(),
      },
    })

    return NextResponse.json({ 
      message: 'Keyword deleted successfully' 
    })
  } catch (error) {
    console.error('Failed to delete keyword:', error)
    return NextResponse.json(
      { error: 'Failed to delete keyword' },
      { status: 500 }
    )
  }
}