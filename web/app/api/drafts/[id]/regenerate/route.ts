/**
 * API route handler for regenerating draft responses
 * Uses Claude CLI to generate new response with episode context
 * Interacts with: Prisma database, Claude CLI, Episode files
 */

import { NextRequest, NextResponse } from "next/server"
import { prisma } from "@/lib/db"
import { spawn } from "child_process"
import path from "path"
import fs from "fs/promises"

// No escaping needed since we're using spawn with direct arguments

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const draftId = parseInt(params.id)
    
    // Allow passing episodeId in request body if needed
    let body: any = {}
    try {
      body = await request.json()
    } catch {
      // No body provided, that's ok
    }
    const requestedEpisodeId = body.episodeId
    
    // Fetch draft with tweet and episode information
    const draft = await prisma.draftReply.findUnique({
      where: { id: draftId },
      include: {
        tweet: {
          include: {
            episode: true
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

    // Debug logging to understand the data structure
    console.log("Draft data:", {
      draftId: draft.id,
      tweetId: draft.tweet.id,
      twitterId: draft.tweet.twitterId,
      episodeId: draft.tweet.episodeId,
      hasEpisode: !!draft.tweet.episode,
      episodeData: draft.tweet.episode ? {
        id: draft.tweet.episode.id,
        episodeDir: draft.tweet.episode.episodeDir,
        claudeEpisodeDir: draft.tweet.episode.claudeEpisodeDir,
        title: draft.tweet.episode.title
      } : null
    })

    // Get episode directory - handle various scenarios
    let episode = draft.tweet.episode
    
    // If no episode but we have a requestedEpisodeId, try to fetch it
    if (!episode && requestedEpisodeId) {
      console.log(`No episode on tweet, but requestedEpisodeId provided: ${requestedEpisodeId}`)
      episode = await prisma.podcastEpisode.findUnique({
        where: { id: requestedEpisodeId }
      })
      if (episode) {
        console.log(`Found episode ${episode.id}: ${episode.title}`)
      }
    }
    
    // If still no episode, try to find the most recent episode as fallback
    if (!episode) {
      console.log("No episode found, trying to find most recent episode...")
      const recentEpisode = await prisma.podcastEpisode.findFirst({
        where: {
          claudeEpisodeDir: { not: null }
        },
        orderBy: { createdAt: 'desc' }
      })
      if (recentEpisode) {
        console.log(`Using most recent episode as fallback: ${recentEpisode.id} - ${recentEpisode.title}`)
        episode = recentEpisode
      }
    }
    
    let episodeDir = null
    let summaryPath = null
    
    // Try different approaches to find the episode directory
    if (episode) {
      if (episode.claudeEpisodeDir) {
        episodeDir = episode.claudeEpisodeDir
      } else if (episode.episodeDir) {
        // Try the regular episodeDir field
        episodeDir = episode.episodeDir
      } else if (episode.id) {
        // Try constructing from episode ID
        episodeDir = `episode_${episode.id}`
      }
    }
    
    // If we have an episode directory, try to find the summary
    if (episodeDir) {
      // Try different possible paths
      const possiblePaths = process.env.EPISODES_DIR ? [
        path.join(process.env.EPISODES_DIR, episodeDir, "summary.md"),
        path.join(process.cwd(), "..", "claude-pipeline", "episodes", episodeDir, "summary.md"),
      ] : [
        path.join(process.cwd(), "..", "claude-pipeline", "episodes", episodeDir, "summary.md"),
        path.join(process.cwd(), "claude-pipeline", "episodes", episodeDir, "summary.md"),
        path.join(process.cwd(), "..", "episodes", episodeDir, "summary.md"),
        path.join(process.cwd(), "episodes", episodeDir, "summary.md"),
      ]
      
      console.log(`Looking for summary in episode directory: ${episodeDir}`)
      for (const testPath of possiblePaths) {
        try {
          await fs.access(testPath)
          summaryPath = testPath
          console.log(`✓ Found summary at: ${testPath}`)
          break
        } catch {
          console.log(`✗ Not found at: ${testPath}`)
        }
      }
    }
    
    // Calculate the relative path from responder to summary
    let summaryLocation = ""
    if (summaryPath && episodeDir) {
      // From specialized/responder/ dir, episodes is at ../../episodes/
      summaryLocation = `../../episodes/${episodeDir}/summary.md`
      console.log(`Using episode summary at: @${summaryLocation}`)
    } else {
      console.warn(`No episode summary found for draft ${draftId}, using general context`)
    }

    // Get video URL from episode or use default
    let videoUrl = "@WDF_Show"  // Default to X handle
    if (episode?.videoUrl) {
      videoUrl = episode.videoUrl
      console.log(`Using episode video URL: ${videoUrl}`)
    } else if (episodeDir) {
      // Try to read video_url.txt from episode directory
      const videoUrlPath = path.join(process.cwd(), "..", "claude-pipeline", "episodes", episodeDir, "video_url.txt")
      try {
        const videoUrlContent = await fs.readFile(videoUrlPath, 'utf-8')
        videoUrl = videoUrlContent.trim()
        console.log(`Found video URL from file: ${videoUrl}`)
      } catch {
        console.log("No video URL file found, using default @WDF_Show")
      }
    }

    // Get tweet text
    const tweetText = draft.tweet.fullText

    // Log the full tweet for debugging
    console.log(`Full tweet text (${tweetText.length} chars):`)
    console.log(tweetText)
    
    // Build Claude CLI command
    const claudePath = "/home/debian/.claude/local/claude"
    const specializedDir = path.join(process.cwd(), "..", "claude-pipeline", "specialized", "responder")
    
    console.log("Executing Claude command for regeneration...")
    console.log(`Episode: ${episodeDir || 'No specific episode'}`)
    console.log(`Tweet (${tweetText.length} chars): ${tweetText.substring(0, 100)}...`)
    console.log(`Summary location: @${summaryLocation || 'none'}`)
    
    // Add debugging to verify paths and command
    console.log("Debugging regeneration setup:")
    console.log("- Claude path:", claudePath)
    console.log("- Specialized dir:", specializedDir)
    console.log("- Current working dir:", process.cwd())
    
    // Skip version test for now since we know CLI exists from file checks
    
    // Check if no-mcp.json exists (we're in responder, so go up two levels)
    const noMcpPath = path.join(specializedDir, '..', '..', 'no-mcp.json')
    try {
      await fs.access(noMcpPath)
      console.log("✓ no-mcp.json exists at:", noMcpPath)
    } catch {
      console.error("✗ no-mcp.json NOT FOUND at:", noMcpPath)
    }
    
    // Check if the summary.md file exists (if we have one)
    if (summaryPath) {
      try {
        await fs.access(summaryPath)
        console.log("✓ summary.md exists at:", summaryPath)
        const stats = await fs.stat(summaryPath)
        console.log(`  File size: ${stats.size} bytes`)
        console.log(`  Last modified: ${stats.mtime}`)
      } catch {
        console.error("✗ summary.md NOT FOUND at:", summaryPath)
        summaryPath = null // Clear it if it doesn't exist
      }
    } else {
      console.warn("✗ No summary.md path determined")
    }
    
    // Check if CLAUDE.md exists in the responder directory (we're already in responder)
    const claudeMdPath = path.join(specializedDir, 'CLAUDE.md')
    try {
      await fs.access(claudeMdPath)
      const stats = await fs.stat(claudeMdPath)
      console.log("✓ CLAUDE.md exists at:", claudeMdPath)
      console.log(`  File size: ${stats.size} bytes`)
    } catch {
      console.error("✗ CLAUDE.md NOT FOUND at:", claudeMdPath)
    }
    
    // Build simplified prompt that references CLAUDE.md for all rules
    const summaryRef = summaryLocation ? `Use @${summaryLocation} for episode context. ` : ""

    // Include classification rationale if available for stance-aware responses
    const classificationReason = (draft.tweet as any).classificationRationale || ""
    const reasonSection = classificationReason ? `\n\nCLASSIFICATION CONTEXT:\n${classificationReason}\n\n` : "\n\n"

    const fullPrompt = `ULTRATHINK and craft the most engaging response possible. You are the WDF Podcast Tweet Response Generator. ${summaryRef}Follow the EXACT guidelines in @CLAUDE.md. DO NOT STRAY FROM INSTRUCTIONS IN CLAUDE.md NO MATTER WHAT. Include this URL/handle: ${videoUrl}${reasonSection}Tweet to respond to:
${tweetText}

Generated response:`
    
    console.log("Tweet text (first 200 chars):", tweetText.substring(0, 200))
    console.log("Full prompt length:", fullPrompt.length, "chars")
    console.log("Using spawn with direct arguments to avoid shell quoting issues")
    
    console.log("Executing command with 60s timeout...")
    const responsePromise = new Promise<string>((resolve, reject) => {
      const child = spawn(claudePath, [
        '--model', 'sonnet',
        '--strict-mcp-config',
        '--mcp-config', '../../no-mcp.json',
        '--print',
        '--dangerously-skip-permissions',
        fullPrompt
      ], {
        cwd: specializedDir,
        timeout: 60000,
        stdio: ['pipe', 'pipe', 'pipe'],
        env: {
          ...process.env,
          HOME: '/home/debian',
          USER: 'debian',
          TERM: 'xterm-256color'
        }
      })

      // Close stdin immediately to prevent interactive mode
      child.stdin.end()

      // Log spawn details
      console.log('Spawned process PID:', child.pid)
      
      let stdout = ''
      let stderr = ''
      
      child.stdout.on('data', (data) => {
        const chunk = data.toString()
        stdout += chunk
        console.log('[Claude STDOUT]', chunk.substring(0, 200))
      })

      child.stderr.on('data', (data) => {
        const chunk = data.toString()
        stderr += chunk
        console.log('[Claude STDERR]', chunk.substring(0, 200))
      })
      
      child.on('close', (code) => {
        if (code === 0) {
          console.log("Command succeeded! Output length:", stdout.length)
          console.log("First 100 chars of output:", stdout.substring(0, 100))
          resolve(stdout)
        } else {
          console.error("Command failed with details:", {
            code: code,
            stdout: stdout ? `${stdout.length} chars: ${stdout.substring(0, 500)}` : 'empty',
            stderr: stderr ? `${stderr.length} chars: ${stderr.substring(0, 500)}` : 'empty'
          })
          reject(new Error(`Claude CLI exited with code ${code}: ${stderr || 'No error output'}`))
        }
      })
      
      child.on('error', (err) => {
        console.error("Spawn error:", err.message)
        reject(err)
      })
    })
    
    
    const stdout = await responsePromise
    
    // Clean the response
    let newResponse = stdout.trim()
    
    // Remove any quotes if Claude wrapped the response
    if (newResponse.startsWith('"') && newResponse.endsWith('"')) {
      newResponse = newResponse.slice(1, -1)
    }
    
    // Validate character count
    if (newResponse.length > 280) {
      newResponse = newResponse.substring(0, 277) + "..."
    }
    
    // Update the draft with new response
    const updatedDraft = await prisma.$transaction(async (tx) => {
      // Increment version number
      const newVersion = (draft.version || 1) + 1
      
      // Update the draft
      const updated = await tx.draftReply.update({
        where: { id: draftId },
        data: {
          text: newResponse,
          version: newVersion,
          characterCount: newResponse.length,
          updatedAt: new Date(),
          // Reset approval/rejection status
          status: "pending",
          approvedAt: null,
          approvedBy: null,
          rejectedAt: null,
          rejectedBy: null,
          rejectionReason: null
        }
      })
      
      // Create audit log entry
      await tx.auditLog.create({
        data: {
          action: "draft_regenerated",
          resourceType: "draft",
          resourceId: draftId,
          metadata: {
            tweetId: draft.tweet.twitterId,
            episodeId: episode?.id || null,
            episodeDir: episodeDir || 'no-episode',
            oldText: draft.text,
            newText: newResponse,
            version: newVersion,
            modelName: "claude-sonnet",
            hadEpisodeContext: !!episodeDir
          }
        }
      })
      
      return updated
    })
    
    console.log(`Successfully regenerated draft ${draftId} (v${updatedDraft.version})`)
    
    return NextResponse.json({
      id: updatedDraft.id.toString(),
      text: updatedDraft.text,
      version: updatedDraft.version,
      characterCount: updatedDraft.characterCount,
      status: updatedDraft.status
    })
    
  } catch (error) {
    console.error("Failed to regenerate draft:", error)
    
    // Provide more specific error messages
    if (error instanceof Error) {
      if (error.message.includes("command not found")) {
        return NextResponse.json(
          { error: "Claude CLI not found. Please ensure it's installed." },
          { status: 500 }
        )
      }
      if (error.message.includes("ENOENT")) {
        return NextResponse.json(
          { error: "Required files or directories not found" },
          { status: 500 }
        )
      }
      if (error.message.includes("timeout")) {
        return NextResponse.json(
          { error: "Claude CLI timed out. Please try again." },
          { status: 504 }
        )
      }
    }
    
    return NextResponse.json(
      { error: "Failed to regenerate draft response" },
      { status: 500 }
    )
  }
}