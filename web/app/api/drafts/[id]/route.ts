/**
 * API route handler for individual draft operations
 * Provides endpoints for updating, approving, and rejecting drafts
 * Interacts with: Prisma database client, Audit logging, Twitter publishing
 */

import { NextRequest, NextResponse } from "next/server"
import { prisma } from "@/lib/db"

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const draft = await prisma.draftReply.findUnique({
      where: { id: parseInt(params.id) },
      include: {
        tweet: {
          select: {
            id: true,
            twitterId: true,
            authorHandle: true,
            fullText: true,
            textPreview: true,
          },
        },
      },
    })

    if (!draft) {
      return NextResponse.json(
        { error: "Draft not found" },
        { status: 404 }
      )
    }

    return NextResponse.json({
      id: draft.id.toString(),
      tweetId: draft.tweet.twitterId,
      text: draft.text,
      status: draft.status,
      modelName: draft.modelName,
      styleScore: draft.styleScore,
      toxicityScore: draft.toxicityScore,
      createdAt: draft.createdAt.toISOString(),
      updatedAt: draft.updatedAt.toISOString(),
      tweet: {
        id: draft.tweet.twitterId,
        authorHandle: draft.tweet.authorHandle,
        fullText: draft.tweet.fullText,
        textPreview: draft.tweet.textPreview || draft.tweet.fullText?.substring(0, 280) || "",
      },
    })
  } catch (error) {
    console.error("Failed to fetch draft:", error)
    return NextResponse.json(
      { error: "Failed to fetch draft" },
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
    const { text, status } = body

    const draft = await prisma.draftReply.findUnique({
      where: { id: parseInt(params.id) },
    })

    if (!draft) {
      return NextResponse.json(
        { error: "Draft not found" },
        { status: 404 }
      )
    }

    // Update the draft
    const updatedDraft = await prisma.draftReply.update({
      where: { id: parseInt(params.id) },
      data: {
        ...(text !== undefined && { text }),
        ...(status !== undefined && { status }),
      },
    })

    // Log to audit trail
    await prisma.auditLog.create({
      data: {
        action: "draft_updated",
        resourceType: "draft",
        resourceId: parseInt(params.id),
        metadata: {
          changes: {
            ...(text !== undefined && { text: { from: draft.text, to: text } }),
            ...(status !== undefined && { status: { from: draft.status, to: status } }),
          },
        },
      },
    })

    return NextResponse.json({
      id: updatedDraft.id.toString(),
      text: updatedDraft.text,
      status: updatedDraft.status,
      updatedAt: updatedDraft.updatedAt.toISOString(),
    })
  } catch (error) {
    console.error("Failed to update draft:", error)
    return NextResponse.json(
      { error: "Failed to update draft" },
      { status: 500 }
    )
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const draft = await prisma.draftReply.findUnique({
      where: { id: parseInt(params.id) },
    })

    if (!draft) {
      return NextResponse.json(
        { error: "Draft not found" },
        { status: 404 }
      )
    }

    // Soft delete by marking as superseded
    await prisma.draftReply.update({
      where: { id: parseInt(params.id) },
      data: { superseded: true },
    })

    // Log to audit trail
    await prisma.auditLog.create({
      data: {
        action: "draft_deleted",
        resourceType: "draft",
        resourceId: parseInt(params.id),
        metadata: {
          reason: "manual_deletion",
        },
      },
    })

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error("Failed to delete draft:", error)
    return NextResponse.json(
      { error: "Failed to delete draft" },
      { status: 500 }
    )
  }
}