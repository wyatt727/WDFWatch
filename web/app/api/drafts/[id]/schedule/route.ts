/**
 * API route handler for scheduling drafts
 * Handles adding approved drafts to queue for later posting
 * Interacts with: Prisma database, Tweet queue
 */

import { NextRequest, NextResponse } from "next/server"
import { prisma } from "@/lib/db"

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const body = await request.json()
    const { scheduleAt, finalText } = body

    const draft = await prisma.draftReply.findUnique({
      where: { id: parseInt(params.id) },
      include: {
        tweet: true,
      },
    })

    if (!draft) {
      return NextResponse.json(
        { error: "Draft not found" },
        { status: 404 }
      )
    }

    if (draft.status !== "pending") {
      return NextResponse.json(
        { error: "Draft is not in pending status" },
        { status: 400 }
      )
    }

    // Start a transaction to ensure data consistency
    const result = await prisma.$transaction(async (tx) => {
      // Update the draft status to scheduled
      const scheduledDraft = await tx.draftReply.update({
        where: { id: parseInt(params.id) },
        data: {
          status: "scheduled",
          text: finalText || draft.text,
          scheduledFor: scheduleAt ? new Date(scheduleAt) : null,
        },
      })

      // Update the tweet status to indicate it has a scheduled draft
      await tx.tweet.update({
        where: { id: draft.tweetId },
        data: {
          status: "scheduled",
        },
      })

      // Add to tweet queue for scheduled posting
      const queueId = `${draft.tweet.twitterId}-${Date.now()}`
      await tx.tweetQueue.create({
        data: {
          tweetId: queueId,
          twitterId: draft.tweet.twitterId,
          source: 'scheduled_draft',
          priority: 5,
          status: 'scheduled',
          episodeId: draft.tweet.episodeId || undefined,
          addedBy: 'system',
          metadata: {
            draftId: draft.id,
            responseText: finalText || draft.text,
            scheduleAt: scheduleAt || new Date(Date.now() + 60 * 60 * 1000).toISOString(), // Default to 1 hour from now
          },
          retryCount: 0,
        }
      })

      // Create audit log entry
      await tx.auditLog.create({
        data: {
          action: "draft_scheduled",
          resourceType: "draft",
          resourceId: parseInt(params.id),
          metadata: {
            tweetId: draft.tweet.twitterId,
            text: finalText || draft.text,
            scheduleAt: scheduleAt,
          },
        },
      })

      return scheduledDraft
    })

    return NextResponse.json({
      id: result.id.toString(),
      status: result.status,
      scheduledFor: result.scheduledFor?.toISOString(),
      text: result.text,
      message: "Draft scheduled successfully",
    })
  } catch (error) {
    console.error("Failed to schedule draft:", error)
    return NextResponse.json(
      { error: "Failed to schedule draft" },
      { status: 500 }
    )
  }
}