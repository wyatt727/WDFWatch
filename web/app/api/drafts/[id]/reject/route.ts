/**
 * API route handler for rejecting drafts
 * Handles rejection workflow with reason tracking
 * Interacts with: Prisma database, Audit logging
 */

import { NextRequest, NextResponse } from "next/server"
import { prisma } from "@/lib/db"
import { exec } from "child_process"
import { promisify } from "util"
import path from "path"

const execAsync = promisify(exec)

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const body = await request.json()
    const { reason } = body

    const draft = await prisma.draftReply.findUnique({
      where: { id: parseInt(params.id) },
      include: {
        tweet: {
          select: {
            id: true,
            twitterId: true,
            search_keywords: true,
            authorHandle: true,
            fullText: true,
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

    if (draft.status !== "pending") {
      return NextResponse.json(
        { error: "Draft is not in pending status" },
        { status: 400 }
      )
    }

    // Start a transaction to ensure data consistency
    const result = await prisma.$transaction(async (tx) => {
      // Update the draft status
      const rejectedDraft = await tx.draftReply.update({
        where: { id: parseInt(params.id) },
        data: {
          status: "rejected",
          rejectedAt: new Date(),
        },
      })

      // Create audit log entry
      await tx.auditLog.create({
        data: {
          action: "draft_rejected",
          resourceType: "draft",
          resourceId: parseInt(params.id),
          metadata: {
            tweetId: draft.tweet.twitterId,
            reason: reason || "No reason provided",
            modelName: draft.modelName,
            draftText: draft.text,
          },
        },
      })

      // Check if there are other pending drafts for this tweet
      const otherPendingDrafts = await tx.draftReply.count({
        where: {
          tweetId: draft.tweetId,
          status: "pending",
          superseded: false,
          id: { not: draft.id },
        },
      })

      // If no other pending drafts, update tweet status back to relevant
      if (otherPendingDrafts === 0) {
        await tx.tweet.update({
          where: { id: draft.tweetId },
          data: {
            status: "relevant",
          },
        })
      }

      return rejectedDraft
    })
    
    // Apply keyword penalty for the rejected draft
    try {
      // Get keywords associated with the tweet
      const keywords = draft.tweet.search_keywords || []
      
      if (keywords.length > 0) {
        const scriptPath = path.join(process.cwd(), "scripts", "apply_keyword_penalty.py")
        const pythonPath = process.env.PYTHON_PATH || "python3"
        
        const command = `${pythonPath} ${scriptPath} --tweet-id "${draft.tweet.twitterId}" --keywords ${keywords.join(" ")} --penalty 0.2`
        
        console.log(`Applying keyword penalty for rejected draft: ${command}`)
        
        // Run the Python script asynchronously (don't wait for completion)
        execAsync(command).catch(error => {
          console.error("Failed to apply keyword penalty:", error)
          // Don't throw - we still want to return success for the rejection
        })
      }
    } catch (error) {
      console.error("Failed to apply keyword penalty:", error)
      // Continue - keyword penalty is not critical for rejection
    }

    return NextResponse.json({
      id: result.id.toString(),
      status: result.status,
      rejectedAt: result.rejectedAt?.toISOString(),
    })
  } catch (error) {
    console.error("Failed to reject draft:", error)
    return NextResponse.json(
      { error: "Failed to reject draft" },
      { status: 500 }
    )
  }
}