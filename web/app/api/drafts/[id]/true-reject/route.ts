/**
 * API route handler for true rejection of drafts
 * Marks tweet as irrelevant and applies keyword penalties
 * Interacts with: Prisma database, Keyword learning system
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
    const draftId = parseInt(params.id)

    // Fetch draft with tweet information
    const draft = await prisma.draftReply.findUnique({
      where: { id: draftId },
      include: {
        tweet: {
          select: {
            id: true,
            twitterId: true,
            search_keywords: true,
            authorHandle: true,
            fullText: true,
            episodeId: true
          }
        }
      }
    })

    if (!draft) {
      return NextResponse.json(
        { error: "Draft not found" },
        { status: 404 }
      )
    }

    if (!draft.tweet) {
      return NextResponse.json(
        { error: "Tweet not found for this draft" },
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
      // Update the tweet status to mark it as irrelevant
      // This removes it from the pool of relevant tweets
      await tx.tweet.update({
        where: { id: draft.tweetId },
        data: {
          status: "skip", // Mark as skip so it won't be included in response generation
          relevanceScore: 0.0, // Set relevance score to 0
          classificationRationale: reason || "Marked as irrelevant by user"
        }
      })

      // Update the draft status to rejected
      const rejectedDraft = await tx.draftReply.update({
        where: { id: draftId },
        data: {
          status: "rejected",
          rejectedAt: new Date(),
          rejectionReason: reason || "Tweet marked as irrelevant"
        }
      })

      // Delete all other pending drafts for this tweet
      // since the tweet itself is now irrelevant
      await tx.draftReply.updateMany({
        where: {
          tweetId: draft.tweetId,
          status: "pending",
          id: { not: draftId }
        },
        data: {
          status: "rejected",
          rejectedAt: new Date(),
          rejectionReason: "Tweet marked as irrelevant"
        }
      })

      // Create audit log entry
      await tx.auditLog.create({
        data: {
          action: "tweet_marked_irrelevant",
          resourceType: "tweet",
          resourceId: draft.tweetId,
          metadata: {
            draftId: draftId,
            tweetId: draft.tweet.twitterId,
            reason: reason || "Marked as irrelevant by user",
            keywords: draft.tweet.search_keywords,
            previousStatus: "relevant",
            newStatus: "skip"
          }
        }
      })

      // If this tweet is part of an episode, update the episode's relevant tweets
      if (draft.tweet.episodeId) {
        // Remove from episode's classified.json if it exists
        try {
          const episode = await tx.podcastEpisode.findUnique({
            where: { id: draft.tweet.episodeId }
          })
          
          if (episode && episode.claudeEpisodeDir) {
            const classifiedPath = path.join(
              process.cwd(),
              "..",
              "claude-pipeline",
              "episodes",
              episode.claudeEpisodeDir,
              "classified.json"
            )
            
            // Update classified.json to mark this tweet as SKIP
            // This is done asynchronously to not block the response
            const fs = require("fs").promises
            fs.readFile(classifiedPath, "utf-8")
              .then(data => {
                const classified = JSON.parse(data)
                const updatedClassified = classified.map((item: any) => {
                  if (item.id === draft.tweet.twitterId) {
                    return { ...item, classification: "SKIP", score: 0.0 }
                  }
                  return item
                })
                return fs.writeFile(classifiedPath, JSON.stringify(updatedClassified, null, 2))
              })
              .catch((err: any) => {
                console.error("Failed to update classified.json:", err)
                // Non-critical error, continue
              })
          }
        } catch (error) {
          console.error("Failed to update episode files:", error)
          // Non-critical error, continue
        }
      }

      return rejectedDraft
    })
    
    // Apply keyword penalty for the true rejection
    try {
      const keywords = draft.tweet.search_keywords || []
      
      if (keywords.length > 0) {
        const scriptPath = path.join(process.cwd(), "scripts", "apply_keyword_penalty.py")
        const pythonPath = process.env.PYTHON_PATH || "python3"
        
        // Apply a stronger penalty for true rejections (0.5 instead of 0.2)
        const command = `${pythonPath} ${scriptPath} --tweet-id "${draft.tweet.twitterId}" --keywords ${keywords.join(" ")} --penalty 0.5`
        
        console.log(`Applying strong keyword penalty for true rejection: ${command}`)
        
        // Run the Python script asynchronously
        execAsync(command).catch(error => {
          console.error("Failed to apply keyword penalty:", error)
          // Don't throw - we still want to return success for the rejection
        })
      }
    } catch (error) {
      console.error("Failed to apply keyword penalty:", error)
      // Continue - keyword penalty is not critical for rejection
    }

    console.log(`Tweet ${draft.tweet.twitterId} marked as irrelevant, draft ${draftId} rejected`)

    return NextResponse.json({
      id: result.id.toString(),
      status: result.status,
      rejectedAt: result.rejectedAt?.toISOString(),
      tweetStatus: "skip",
      message: "Tweet marked as irrelevant and removed from relevant pool"
    })
    
  } catch (error) {
    console.error("Failed to perform true rejection:", error)
    return NextResponse.json(
      { error: "Failed to mark tweet as irrelevant" },
      { status: 500 }
    )
  }
}