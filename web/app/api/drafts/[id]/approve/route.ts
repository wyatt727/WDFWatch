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

// Helper to load API keys - gets fresh tokens directly from Python script
async function loadApiKeys() {
  // CRITICAL: Get fresh tokens directly from Python script output
  try {
    const { exec } = await import('child_process')
    const { promisify } = await import('util')
    const execAsync = promisify(exec)

    const pythonPath = process.env.PYTHON_PATH || '/home/debian/Tools/WDFWatch/venv/bin/python'
    const ensureFreshScript = '/home/debian/Tools/WDFWatch/scripts/ensure_fresh_tokens.py'

    // Get fresh tokens as JSON output (refreshes if needed)
    console.log('Getting fresh tokens from Python script...')
    const { stdout, stderr } = await execAsync(`${pythonPath} ${ensureFreshScript} --max-age 90 --output-tokens`)

    if (stderr && !stderr.includes('Token is fresh')) {
      console.error('Token refresh warning:', stderr.trim())
    }

    // Parse the JSON output from Python script
    if (stdout) {
      try {
        const tokens = JSON.parse(stdout.trim())
        console.log('✅ Successfully got fresh tokens from Python script')

        // Add aliases for compatibility
        if (tokens.API_KEY) {
          tokens.CLIENT_ID = tokens.API_KEY
          tokens.TWITTER_API_KEY = tokens.API_KEY
        }
        if (tokens.API_KEY_SECRET) {
          tokens.CLIENT_SECRET = tokens.API_KEY_SECRET
          tokens.TWITTER_API_KEY_SECRET = tokens.API_KEY_SECRET
        }

        // Log token preview for debugging (first 20 chars only)
        if (tokens.WDFWATCH_ACCESS_TOKEN) {
          console.log(`WDFWATCH_ACCESS_TOKEN: ${tokens.WDFWATCH_ACCESS_TOKEN.substring(0, 20)}...`)
        }

        return tokens
      } catch (parseError) {
        console.error('Failed to parse token JSON:', parseError)
        console.error('stdout was:', stdout)
      }
    }
  } catch (refreshError) {
    console.error('Failed to get fresh tokens from Python:', refreshError)
  }

  // FALLBACK: Try reading from .env.wdfwatch file if Python script fails
  const envPath = path.join(process.cwd(), '..', '.env.wdfwatch')
  console.log('FALLBACK: Loading API keys from .env.wdfwatch:', envPath)

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
    if (!apiEnvVars.WDFWATCH_REFRESH_TOKEN) {
      console.error('❌ WARNING: WDFWATCH_REFRESH_TOKEN not found - token refresh will fail!')
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
  console.log('==================== DRAFT APPROVAL START ====================')
  console.log(`[Draft Approval] Processing draft ID: ${params.id}`)
  console.log(`[Draft Approval] Timestamp: ${new Date().toISOString()}`)

  try {
    const body = await request.json()
    const { finalText, scheduleAt } = body
    console.log(`[Draft Approval] Request body:`, {
      hasFinalText: !!finalText,
      finalTextLength: finalText?.length,
      scheduleAt,
      isImmediate: !scheduleAt
    })

    console.log(`[Draft Approval] Fetching draft from database...`)
    const draft = await prisma.draftReply.findUnique({
      where: { id: parseInt(params.id) },
      include: {
        tweet: true,
      },
    })

    if (!draft) {
      console.error(`[Draft Approval] ❌ DRAFT NOT FOUND: ${params.id}`)
      return NextResponse.json(
        { error: "Draft not found" },
        { status: 404 }
      )
    }
    console.log(`[Draft Approval] ✅ Draft found:`, {
      id: draft.id,
      status: draft.status,
      tweetId: draft.tweet.twitterId,
      textLength: draft.text.length
    })

    if (draft.status !== "pending") {
      console.error(`[Draft Approval] ❌ INVALID STATUS: ${draft.status} (expected: pending)`)
      return NextResponse.json(
        { error: "Draft is not in pending status" },
        { status: 400 }
      )
    }
    console.log(`[Draft Approval] ✅ Draft status is valid (pending)`)

    // Start a transaction to ensure data consistency
    console.log(`[Draft Approval] Starting database transaction...`)
    const result = await prisma.$transaction(async (tx) => {
      // Update the draft status
      console.log(`[Draft Approval] Updating draft status to approved...`)
      const approvedDraft = await tx.draftReply.update({
        where: { id: parseInt(params.id) },
        data: {
          status: "approved",
          text: finalText || draft.text,
          approvedAt: new Date(),
        },
      })
      console.log(`[Draft Approval] ✅ Draft updated to approved`)

      // Update the tweet status to indicate it has an approved draft
      console.log(`[Draft Approval] Updating tweet status to drafted...`)
      await tx.tweet.update({
        where: { id: draft.tweetId },
        data: {
          status: "drafted",
        },
      })
      console.log(`[Draft Approval] ✅ Tweet status updated`)

      // Create audit log entry
      console.log(`[Draft Approval] Creating audit log entry...`)
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
      console.log(`[Draft Approval] ✅ Audit log created`)

      return { approvedDraft }
    }, {
      maxWait: 10000, // Maximum time to wait for a transaction slot (10s)
      timeout: 20000, // Maximum time for the transaction to complete (20s)
    })
    console.log(`[Draft Approval] ✅ Database transaction completed successfully`)

    // Post to Twitter AFTER the transaction completes
    let postResult = null
    if (!scheduleAt) {
      console.log(`[Draft Approval] Preparing to post immediately to Twitter...`)

      // Post immediately to Twitter
      try {
        // Load API keys from database or .env fallback
        console.log(`[Draft Approval] Loading API keys...`)
        const apiKeys = await loadApiKeys()

        if (!apiKeys.WDFWATCH_ACCESS_TOKEN) {
          console.error(`[Draft Approval] ❌ CRITICAL: No WDFWATCH_ACCESS_TOKEN found!`)
        } else {
          console.log(`[Draft Approval] ✅ API keys loaded, token: ${apiKeys.WDFWATCH_ACCESS_TOKEN.substring(0, 20)}...`)
        }

        const { execFile } = await import('child_process')
        const { promisify } = await import('util')
        const execFileAsync = promisify(execFile)

        const pythonPath = process.env.PYTHON_PATH || '/home/debian/Tools/WDFWatch/venv/bin/python'
        const scriptPath = '/home/debian/Tools/WDFWatch/scripts/safe_twitter_reply.py'
        const responseText = finalText || draft.text

        console.log(`[Draft Approval] Python configuration:`, {
          pythonPath,
          scriptPath,
          responseTextLength: responseText.length
        })

        // Clean environment to avoid conflicts
        console.log(`[Draft Approval] Cleaning environment variables...`)
        const cleanEnv = { ...process.env }
        delete cleanEnv.DEBUG  // Remove Prisma debug flag that causes pydantic error
        // Remove dangerous tokens that could post to WDF_Show
        delete cleanEnv.ACCESS_TOKEN
        delete cleanEnv.ACCESS_TOKEN_SECRET
        delete cleanEnv.TWITTER_TOKEN
        delete cleanEnv.TWITTER_TOKEN_SECRET
        delete cleanEnv.WDFSHOW_ACCESS_TOKEN
        delete cleanEnv.WDFSHOW_ACCESS_TOKEN_SECRET

        // Use execFile to pass arguments directly without shell escaping
        // This preserves special characters (newlines, quotes, etc.) correctly
        const args = [scriptPath, '--tweet-id', draft.tweet.twitterId, '--message', responseText]

        console.log('[Draft Approval] Executing Python script with args')
        console.log(`[Draft Approval] Script: ${scriptPath}`)
        console.log(`[Draft Approval] Tweet ID: ${draft.tweet.twitterId}`)
        console.log(`[Draft Approval] Response length: ${responseText.length} chars`)
        console.log(`[Draft Approval] Environment flags:`, {
          WDFWATCH_MODE: 'true',
          WDF_DEBUG: 'false',
          WDF_WEB_MODE: 'true',
          WDF_BYPASS_QUOTA_CHECK: 'true',
          WDF_MOCK_MODE: 'false'
        })

        // Use execFile instead of exec - no shell escaping needed!
        const { stdout, stderr } = await execFileAsync(pythonPath, args, {
          env: {
            ...cleanEnv,
            ...apiKeys,  // Include loaded API keys
            WDFWATCH_MODE: 'true',
            WDF_DEBUG: 'false',  // Override the debug setting
            WDF_WEB_MODE: 'true',  // Indicate we're running from web
            WDF_BYPASS_QUOTA_CHECK: 'true',  // Bypass Redis quota checking for manual posting
            WDF_MOCK_MODE: 'false',  // Force real Twitter API
            WDF_REDIS_URL: 'redis://localhost:6379/0'  // Ensure Redis URL is set
          },
          timeout: 25000,  // 25-second timeout for Python script (leaves 5s for other operations)
          cwd: '/home/debian/Tools/WDFWatch'  // Set working directory
        })

        if (stderr) {
          console.warn('[Draft Approval] ⚠️ Python script stderr:', stderr)
        }

        console.log('[Draft Approval] ✅ Python script stdout:', stdout)
        console.log('[Draft Approval] ✅ Twitter reply posted successfully')
        
        // Update draft as posted
        console.log(`[Draft Approval] Updating draft status to posted...`)
        await prisma.draftReply.update({
          where: { id: draft.id },
          data: {
            postedAt: new Date(),
            status: 'posted'
          }
        })
        console.log(`[Draft Approval] ✅ Draft marked as posted`)

        // Add to queue with completed status for tracking
        console.log(`[Draft Approval] Adding to queue with completed status...`)
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
        console.log(`[Draft Approval] ✅ Added to queue as completed`)

        postResult = { success: true, message: 'Posted to Twitter' }
      } catch (error: any) {
        console.error('[Draft Approval] ❌❌❌ TWITTER POSTING FAILED ❌❌❌')
        console.error('[Draft Approval] Error type:', error.constructor.name)
        console.error('[Draft Approval] Error message:', error.message)
        console.error('[Draft Approval] Error code:', error.code)
        console.error('[Draft Approval] Error details:', {
          message: error.message,
          code: error.code,
          killed: error.killed,
          signal: error.signal,
          stdout: error.stdout?.substring(0, 500),
          stderr: error.stderr?.substring(0, 500)
        })

        if (error.stdout) {
          console.error('[Draft Approval] Full stdout:', error.stdout)
        }
        if (error.stderr) {
          console.error('[Draft Approval] Full stderr:', error.stderr)
        }

        postResult = { success: false, error: error.message || 'Failed to execute posting script' }
        
        // Add to queue as pending for retry
        console.log(`[Draft Approval] Adding to queue for retry...`)
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
        console.log(`[Draft Approval] ✅ Added to queue for retry`)
      }
    } else {
      // Add to queue for scheduled posting
      console.log(`[Draft Approval] Scheduling for later posting at: ${scheduleAt}`)
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
      console.log(`[Draft Approval] ✅ Added to queue as scheduled`)
      postResult = { success: true, message: 'Scheduled for later posting' }
    }

    // Log the result
    if (postResult) {
      if (postResult.success) {
        console.log(`[Draft Approval] ✅✅✅ FINAL RESULT: SUCCESS`)
        console.log(`[Draft Approval] ✅ Tweet ${draft.tweet.twitterId} - ${postResult.message}`)
      } else {
        console.log(`[Draft Approval] ⚠️⚠️⚠️ FINAL RESULT: QUEUED FOR RETRY`)
        console.log(`[Draft Approval] ⚠️ Tweet ${draft.tweet.twitterId} - Error: ${postResult.error}`)
      }
    }

    console.log('==================== DRAFT APPROVAL END ====================')

    return NextResponse.json({
      id: result.approvedDraft.id.toString(),
      status: result.approvedDraft.status,
      approvedAt: result.approvedDraft.approvedAt?.toISOString(),
      text: result.approvedDraft.text,
      postResult: postResult,
    })
  } catch (error: any) {
    console.error('[Draft Approval] ❌❌❌ UNEXPECTED ERROR ❌❌❌')
    console.error('[Draft Approval] Error type:', error.constructor?.name)
    console.error('[Draft Approval] Error message:', error.message)
    console.error('[Draft Approval] Stack trace:', error.stack)
    console.error('[Draft Approval] Full error object:', error)
    console.log('==================== DRAFT APPROVAL FAILED ====================')

    return NextResponse.json(
      { error: "Failed to approve draft" },
      { status: 500 }
    )
  }
}