/**
 * API route handler for approving drafts
 * Handles approval workflow and prepares for Twitter publishing
 * Interacts with: Prisma database, Audit logging, Twitter queue
 */

import { NextRequest, NextResponse } from "next/server"
import { prisma } from "@/lib/db"
import { emitEvent } from "@/lib/sse-events"

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const body = await request.json()
    const { finalText, scheduleAt } = body

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
      // Update the draft status
      const approvedDraft = await tx.draftReply.update({
        where: { id: parseInt(params.id) },
        data: {
          status: "approved",
          text: finalText || draft.text,
          approvedAt: new Date(),
        },
      })

      // Update the tweet status to indicate it has an approved draft
      await tx.tweet.update({
        where: { id: draft.tweetId },
        data: {
          status: "drafted",
        },
      })

      // Create audit log entry
      await tx.auditLog.create({
        data: {
          action: "draft_approved",
          resourceType: "draft",
          resourceId: parseInt(params.id),
          metadata: {
            tweetId: draft.tweet.twitterId,
            originalText: draft.text,
            finalText: finalText || draft.text,
            textChanged: Boolean(finalText && finalText !== draft.text),
            scheduleAt: scheduleAt || null,
          },
        },
      })

      return { approvedDraft }
    }, {
      maxWait: 10000, // Maximum time to wait for a transaction slot (10s)
      timeout: 20000, // Maximum time for the transaction to complete (20s)
    })

    // Post to Twitter AFTER the transaction completes
    let postResult = null
    if (!scheduleAt) {
      // Post immediately to Twitter
      try {
        const { exec } = await import('child_process')
        const { promisify } = await import('util')
        const execAsync = promisify(exec)
        
        const pythonPath = process.env.PYTHON_PATH || 'python3'
        const scriptPath = '/Users/pentester/Tools/WDFWatch/scripts/safe_twitter_reply.py'
        const responseText = finalText || draft.text
        
        // Clean environment to avoid conflicts
        const cleanEnv = { ...process.env }
        delete cleanEnv.DEBUG  // Remove Prisma debug flag that causes pydantic error
        
        // Execute the Python script to post the reply
        const command = `${pythonPath} ${scriptPath} --tweet-id "${draft.tweet.twitterId}" --message "${responseText.replace(/"/g, '\\"')}"`
        
        const { stdout, stderr } = await execAsync(command, {
          env: {
            ...cleanEnv,
            WDFWATCH_MODE: 'true',
            WDF_DEBUG: 'false'  // Override the debug setting
          }
        })
        
        console.log('Twitter reply posted:', stdout)
        
        // Update draft as posted
        await prisma.draftReply.update({
          where: { id: draft.id },
          data: {
            postedAt: new Date(),
            status: 'posted'
          }
        })
        
        // Add to queue with completed status for tracking
        const queueId = `${draft.tweet.twitterId}-${Date.now()}`
        await prisma.tweetQueue.create({
          data: {
            tweetId: queueId,
            twitterId: draft.tweet.twitterId,
            source: 'approved_draft',
            priority: 8,
            status: 'completed',
            episodeId: draft.tweet.episodeId || undefined,
            addedBy: 'system',
            processedAt: new Date(),
            metadata: {
              draftId: draft.id,
              responseText: finalText || draft.text,
              approvedAt: new Date().toISOString(),
              postedAt: new Date().toISOString(),
              success: true
            },
            retryCount: 0,
          }
        })
        
        postResult = { success: true, message: 'Posted to Twitter' }
      } catch (error: any) {
        console.error('Failed to post to Twitter:', error)
        postResult = { success: false, error: error.message }
        
        // Add to queue as pending for retry
        const queueId = `${draft.tweet.twitterId}-${Date.now()}`
        await prisma.tweetQueue.create({
          data: {
            tweetId: queueId,
            twitterId: draft.tweet.twitterId,
            source: 'approved_draft',
            priority: 8,
            status: 'pending',
            episodeId: draft.tweet.episodeId || undefined,
            addedBy: 'system',
            metadata: {
              draftId: draft.id,
              responseText: finalText || draft.text,
              approvedAt: new Date().toISOString(),
              error: 'Failed to post immediately, queued for retry'
            },
            retryCount: 0,
          }
        })
      }
    } else {
      // Add to queue for scheduled posting
      const queueId = `${draft.tweet.twitterId}-${Date.now()}`
      await prisma.tweetQueue.create({
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
            scheduleAt: scheduleAt,
            approvedAt: new Date().toISOString(),
          },
          retryCount: 0,
        }
      })
      postResult = { success: true, message: 'Scheduled for later posting' }
    }

    // Log the result
    if (postResult) {
      if (postResult.success) {
        console.log('✅ Tweet posted successfully:', draft.tweet.twitterId)
      } else {
        console.log('⚠️ Tweet queued for retry:', postResult.error)
      }
    }

    return NextResponse.json({
      id: result.approvedDraft.id.toString(),
      status: result.approvedDraft.status,
      approvedAt: result.approvedDraft.approvedAt?.toISOString(),
      text: result.approvedDraft.text,
      postResult: postResult,
    })
  } catch (error) {
    console.error("Failed to approve draft:", error)
    return NextResponse.json(
      { error: "Failed to approve draft" },
      { status: 500 }
    )
  }
}