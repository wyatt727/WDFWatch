/**
 * API route handler for approving drafts
 * Handles approval workflow and prepares for Twitter publishing
 * Interacts with: Prisma database, Audit logging, Twitter queue
 */

import { NextRequest, NextResponse } from "next/server"
import { prisma } from "@/lib/db"
import { emitEvent } from "@/lib/sse-events"
import { decrypt } from "@/lib/crypto"
import path from "path"

// Helper to load API keys from .env.wdfwatch first, then database fallback
async function loadApiKeys() {
  // First, try to load from .env.wdfwatch file
  const envPath = path.join(process.cwd(), '..', '.env.wdfwatch')
  console.log('Loading API keys from .env.wdfwatch:', envPath)

  try {
    const fs = await import('fs/promises')
    const envContent = await fs.readFile(envPath, 'utf-8')
    const apiEnvVars: Record<string, string> = {}

    // Parse .env.wdfwatch file
    const lines = envContent.split('\n')
    for (const line of lines) {
      const trimmed = line.trim()
      if (trimmed && !trimmed.startsWith('#') && trimmed.includes('=')) {
        const [key, ...valueParts] = trimmed.split('=')
        const value = valueParts.join('=').replace(/^['"]|['"]$/g, '') // Remove quotes
        apiEnvVars[key] = value
      }
    }

    // Add aliases for compatibility
    if (apiEnvVars.API_KEY) {
      apiEnvVars.CLIENT_ID = apiEnvVars.API_KEY
      apiEnvVars.TWITTER_API_KEY = apiEnvVars.API_KEY
    }
    if (apiEnvVars.API_KEY_SECRET) {
      apiEnvVars.CLIENT_SECRET = apiEnvVars.API_KEY_SECRET
      apiEnvVars.TWITTER_API_KEY_SECRET = apiEnvVars.API_KEY_SECRET
    }

    // CRITICAL: Ensure WDFWATCH tokens are loaded
    if (!apiEnvVars.WDFWATCH_ACCESS_TOKEN) {
      console.error('❌ WARNING: WDFWATCH_ACCESS_TOKEN not found in .env.wdfwatch!')
    }
    if (!apiEnvVars.WDFWATCH_ACCESS_TOKEN_SECRET) {
      console.error('⚠️  WARNING: WDFWATCH_ACCESS_TOKEN_SECRET not found in .env.wdfwatch!')
    }

    console.log('Successfully loaded API keys from .env.wdfwatch')
    const relevantKeys = Object.keys(apiEnvVars).filter(k =>
      k.includes('API') || k.includes('TOKEN') || k.includes('CLIENT') || k.includes('WDFWATCH')
    )
    console.log(`Found ${relevantKeys.length} API-related keys:`, relevantKeys)

    // Log token preview for debugging (first 20 chars only)
    if (apiEnvVars.WDFWATCH_ACCESS_TOKEN) {
      console.log(`WDFWATCH_ACCESS_TOKEN loaded: ${apiEnvVars.WDFWATCH_ACCESS_TOKEN.substring(0, 20)}...`)
    }

    // Clear DEBUG variable if it exists to prevent Python conflicts
    delete apiEnvVars.DEBUG

    return apiEnvVars
  } catch (fileError) {
    console.log('.env.wdfwatch not found or not readable:', fileError)
    console.log('Falling back to database...')
  }

  // Fallback to database if .env.wdfwatch doesn't exist
  const apiEnvVars: Record<string, string> = {}

  try {
    // Try to load from database
    const setting = await prisma.setting.findUnique({
      where: { key: 'api_keys' }
    })

    if (setting && setting.value) {
      const encryptedConfig = setting.value as any

      // Decrypt Twitter API keys
      if (encryptedConfig.twitter) {
        try {
          if (encryptedConfig.twitter.apiKey) {
            apiEnvVars.API_KEY = decrypt(encryptedConfig.twitter.apiKey)
            apiEnvVars.CLIENT_ID = apiEnvVars.API_KEY // Alias for compatibility
            apiEnvVars.TWITTER_API_KEY = apiEnvVars.API_KEY
          }
          if (encryptedConfig.twitter.apiSecret) {
            apiEnvVars.API_KEY_SECRET = decrypt(encryptedConfig.twitter.apiSecret)
            apiEnvVars.CLIENT_SECRET = apiEnvVars.API_KEY_SECRET // Alias
            apiEnvVars.TWITTER_API_KEY_SECRET = apiEnvVars.API_KEY_SECRET
          }
          if (encryptedConfig.twitter.bearerToken) {
            apiEnvVars.BEARER_TOKEN = decrypt(encryptedConfig.twitter.bearerToken)
          }
          if (encryptedConfig.twitter.accessToken) {
            apiEnvVars.WDFWATCH_ACCESS_TOKEN = decrypt(encryptedConfig.twitter.accessToken)
          }
          if (encryptedConfig.twitter.accessTokenSecret) {
            apiEnvVars.WDFWATCH_ACCESS_TOKEN_SECRET = decrypt(encryptedConfig.twitter.accessTokenSecret)
          }
        } catch (error) {
          console.error('Failed to decrypt Twitter API keys from database:', error)
        }
      }
    }
  } catch (error) {
    console.error('Failed to load API keys from database:', error)
  }

  // Fallback to environment variables if not found in database
  if (!apiEnvVars.API_KEY) {
    const envApiKey = process.env.API_KEY || process.env.CLIENT_ID || process.env.TWITTER_API_KEY
    if (envApiKey) {
      apiEnvVars.API_KEY = envApiKey
      apiEnvVars.CLIENT_ID = envApiKey
      apiEnvVars.TWITTER_API_KEY = envApiKey
    }
  }

  if (!apiEnvVars.API_KEY_SECRET) {
    const envApiSecret = process.env.API_KEY_SECRET || process.env.CLIENT_SECRET || process.env.TWITTER_API_KEY_SECRET
    if (envApiSecret) {
      apiEnvVars.API_KEY_SECRET = envApiSecret
      apiEnvVars.CLIENT_SECRET = envApiSecret
      apiEnvVars.TWITTER_API_KEY_SECRET = envApiSecret
    }
  }

  if (!apiEnvVars.BEARER_TOKEN && process.env.BEARER_TOKEN) {
    apiEnvVars.BEARER_TOKEN = process.env.BEARER_TOKEN
  }

  if (!apiEnvVars.WDFWATCH_ACCESS_TOKEN && process.env.WDFWATCH_ACCESS_TOKEN) {
    apiEnvVars.WDFWATCH_ACCESS_TOKEN = process.env.WDFWATCH_ACCESS_TOKEN
  }

  if (!apiEnvVars.WDFWATCH_ACCESS_TOKEN_SECRET && process.env.WDFWATCH_ACCESS_TOKEN_SECRET) {
    apiEnvVars.WDFWATCH_ACCESS_TOKEN_SECRET = process.env.WDFWATCH_ACCESS_TOKEN_SECRET
  }

  console.log('API Keys loaded:', {
    hasApiKey: !!apiEnvVars.API_KEY,
    hasApiSecret: !!apiEnvVars.API_KEY_SECRET,
    hasBearerToken: !!apiEnvVars.BEARER_TOKEN,
    hasAccessToken: !!apiEnvVars.WDFWATCH_ACCESS_TOKEN,
    source: apiEnvVars.API_KEY ? 'database/env' : 'none'
  })

  return apiEnvVars
}

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
        // Load API keys from database or .env fallback
        const apiKeys = await loadApiKeys()

        const { exec } = await import('child_process')
        const { promisify } = await import('util')
        const execAsync = promisify(exec)

        const pythonPath = process.env.PYTHON_PATH || '/home/debian/Tools/WDFWatch/venv/bin/python'
        const scriptPath = '/home/debian/Tools/WDFWatch/scripts/safe_twitter_reply.py'
        const responseText = finalText || draft.text

        // Clean environment to avoid conflicts
        const cleanEnv = { ...process.env }
        delete cleanEnv.DEBUG  // Remove Prisma debug flag that causes pydantic error
        // Remove dangerous tokens that could post to WDF_Show
        delete cleanEnv.ACCESS_TOKEN
        delete cleanEnv.ACCESS_TOKEN_SECRET
        delete cleanEnv.TWITTER_TOKEN
        delete cleanEnv.TWITTER_TOKEN_SECRET
        delete cleanEnv.WDFSHOW_ACCESS_TOKEN
        delete cleanEnv.WDFSHOW_ACCESS_TOKEN_SECRET

        // Execute the Python script to post the reply
        // Use JSON.stringify for proper escaping
        const escapedMessage = JSON.stringify(responseText).slice(1, -1) // Remove outer quotes
        const command = `${pythonPath} ${scriptPath} --tweet-id "${draft.tweet.twitterId}" --message "${escapedMessage}"`

        console.log('Executing command:', command.substring(0, 100) + '...')

        const { stdout, stderr } = await execAsync(command, {
          env: {
            ...cleanEnv,
            ...apiKeys,  // Include loaded API keys
            WDFWATCH_MODE: 'true',
            WDF_DEBUG: 'false',  // Override the debug setting
            WDF_WEB_MODE: 'true',  // Indicate we're running from web
            WDF_BYPASS_QUOTA_CHECK: 'true',  // Bypass Redis quota checking for manual posting
            WDF_MOCK_MODE: 'false',  // Force real Twitter API
            WDF_REDIS_URL: 'redis://localhost:6379/0'  // Ensure Redis URL is set
          }
        })

        if (stderr) {
          console.error('Python script stderr:', stderr)
        }

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
        console.error('Error details:', {
          message: error.message,
          code: error.code,
          killed: error.killed,
          signal: error.signal,
          stdout: error.stdout?.substring(0, 500),
          stderr: error.stderr?.substring(0, 500)
        })
        postResult = { success: false, error: error.message || 'Failed to execute posting script' }
        
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