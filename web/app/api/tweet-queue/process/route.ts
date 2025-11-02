/**
 * API route for processing the tweet queue
 * Handles posting approved replies to Twitter
 * Interacts with: Python Twitter posting functionality
 */

import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { exec, execFile } from 'child_process'
import { promisify } from 'util'
import { decrypt } from '@/lib/crypto'

const execAsync = promisify(exec)
const execFileAsync = promisify(execFile)

// Helper to get fresh API keys directly from Python script
async function loadApiKeys() {
  // CRITICAL: Get fresh tokens directly from Python script output
  console.error('[Queue] loadApiKeys() START at:', new Date().toISOString())
  process.stderr.write('[Queue] Starting API key loading...\n')

  try {
    const pythonPath = process.env.PYTHON_PATH || '/home/debian/Tools/WDFWatch/venv/bin/python'
    const ensureFreshScript = '/home/debian/Tools/WDFWatch/scripts/ensure_fresh_tokens.py'

    // Get fresh tokens as JSON output (refreshes if needed)
    console.error('[Queue] Getting fresh tokens from Python script...')
    console.error('[Queue] Command:', `${pythonPath} ${ensureFreshScript} --max-age 90 --output-tokens`)

    const startTime = Date.now()
    const { stdout, stderr } = await execAsync(`${pythonPath} ${ensureFreshScript} --max-age 90 --output-tokens`, {
      timeout: 5000 // 5 second timeout for loading tokens
    })
    const endTime = Date.now()
    console.error(`[Queue] Token script completed in ${endTime - startTime}ms`)

    if (stderr && !stderr.includes('Token is fresh')) {
      console.error('[Queue] Token refresh warning:', stderr.trim())
    }

    // Parse the JSON output from Python script
    if (stdout) {
      try {
        const tokens = JSON.parse(stdout.trim())
        console.log('[Queue] ✅ Successfully got fresh tokens from Python script')

        // Add aliases for compatibility
        if (tokens.API_KEY) {
          tokens.CLIENT_ID = tokens.API_KEY
          tokens.TWITTER_API_KEY = tokens.API_KEY
        }
        if (tokens.API_KEY_SECRET) {
          tokens.CLIENT_SECRET = tokens.API_KEY_SECRET
          tokens.TWITTER_API_KEY_SECRET = tokens.API_KEY_SECRET
        }

        // Log token status
        if (tokens.WDFWATCH_ACCESS_TOKEN) {
          console.log(`[Queue] WDFWATCH_ACCESS_TOKEN: ${tokens.WDFWATCH_ACCESS_TOKEN.substring(0, 20)}...`)
        } else {
          console.error('[Queue] ❌ No WDFWATCH_ACCESS_TOKEN found!')
        }

        return tokens
      } catch (parseError) {
        console.error('[Queue] Failed to parse token JSON:', parseError)
        console.error('[Queue] stdout was:', stdout)
      }
    }
  } catch (refreshError) {
    console.error('[Queue] Failed to get fresh tokens from Python:', refreshError)
  }

  // FALLBACK: Try loading from database if Python script fails
  console.log('[Queue] FALLBACK: Trying to load from database...')
  const apiEnvVars: Record<string, string> = {}

  try {
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
            apiEnvVars.CLIENT_ID = apiEnvVars.API_KEY
            apiEnvVars.TWITTER_API_KEY = apiEnvVars.API_KEY
          }
          if (encryptedConfig.twitter.apiSecret) {
            apiEnvVars.API_KEY_SECRET = decrypt(encryptedConfig.twitter.apiSecret)
            apiEnvVars.CLIENT_SECRET = apiEnvVars.API_KEY_SECRET
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
          console.error('[Queue] Failed to decrypt Twitter API keys:', error)
        }
      }
    }
  } catch (error) {
    console.error('[Queue] Failed to load API keys from database:', error)
  }

  // Final fallback to environment variables
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

  if (!apiEnvVars.WDFWATCH_ACCESS_TOKEN && process.env.WDFWATCH_ACCESS_TOKEN) {
    apiEnvVars.WDFWATCH_ACCESS_TOKEN = process.env.WDFWATCH_ACCESS_TOKEN
  }

  return apiEnvVars
}

export async function POST(request: NextRequest) {
  // Use console.error to ensure it gets logged to journal
  console.error('==================== QUEUE PROCESSING START ====================')
  console.error(`[Queue] Timestamp: ${new Date().toISOString()}`)

  // Also try process.stderr.write for critical logging
  process.stderr.write(`[Queue] Processing started at ${new Date().toISOString()}\n`)

  // Track start time for timeout protection
  const batchStartTime = Date.now()
  const MAX_BATCH_DURATION_MS = 30 * 60 * 1000  // 30 minutes max for entire batch

  try {
    const body = await request.json()
    const { batchSize = 1000 } = body  // Process up to 1000 tweets (effectively all)
    console.log(`[Queue] Configuration:`, {
      batchSize,
      maxConsecutiveFailures: 10,
      maxBatchDuration: `${MAX_BATCH_DURATION_MS / 1000 / 60} minutes`
    })

    // Get ALL pending items from the queue with approved_draft source
    console.error(`[Queue] Fetching pending queue items from database...`)
    const dbStartTime = Date.now()
    const queueItems = await prisma.$queryRaw<any[]>`
      SELECT
        q.id,
        q.tweet_id as "tweetId",
        q.twitter_id as "twitterId",
        q.metadata,
        q.status,
        t.twitter_id as "originalTweetId"
      FROM tweet_queue q
      LEFT JOIN tweets t ON t.twitter_id = q.twitter_id
      WHERE
        q.status = 'pending'
        AND q.source = 'approved_draft'
      ORDER BY q.priority DESC, q.added_at ASC
      LIMIT ${batchSize}
    `
    const dbEndTime = Date.now()
    console.error(`[Queue] Database query completed in ${dbEndTime - dbStartTime}ms`)

    console.error(`[Queue] Found ${queueItems.length} items in queue`)
    process.stderr.write(`[Queue] Queue has ${queueItems.length} items to process\n`)

    if (queueItems.length === 0) {
      console.error(`[Queue] ✅ No items to process, queue is empty`)
      console.error('==================== QUEUE PROCESSING END ====================')
      return NextResponse.json({
        message: 'No items to process',
        processed: 0
      })
    }

    // ALWAYS get fresh API keys when Process Queue is pressed
    console.error(`[Queue] Loading FRESH API keys (forcing token refresh)...`)

    // First, force a token refresh by calling the Python script directly
    try {
      const pythonPath = process.env.PYTHON_PATH || '/home/debian/Tools/WDFWatch/venv/bin/python'
      const ensureFreshScript = '/home/debian/Tools/WDFWatch/scripts/ensure_fresh_tokens.py'

      console.error(`[Queue] Forcing token refresh...`)
      const { stdout, stderr } = await execAsync(`${pythonPath} ${ensureFreshScript} --max-age 0 --output-tokens`, {
        timeout: 5000 // 5 second timeout
      })

      if (stdout) {
        console.error(`[Queue] ✅ Forced token refresh successful`)
      }
    } catch (refreshError) {
      console.error(`[Queue] ⚠️ Token refresh failed:`, refreshError)
    }

    // Now load the refreshed keys
    let apiKeys = await loadApiKeys()

    if (!apiKeys.WDFWATCH_ACCESS_TOKEN) {
      console.error(`[Queue] ❌ CRITICAL: No WDFWATCH_ACCESS_TOKEN found!`)
    } else {
      console.error(`[Queue] ✅ API keys loaded, token: ${apiKeys.WDFWATCH_ACCESS_TOKEN.substring(0, 20)}...`)
    }

    const results = []
    let successCount = 0
    let consecutiveFailures = 0  // Track consecutive failures
    const MAX_CONSECUTIVE_FAILURES = 10  // Stop after 10 consecutive failures
    let rateLimitResetTime: number | null = null  // Track when rate limit resets
    let lastTokenRefresh = Date.now()  // Track when tokens were last refreshed
    const TOKEN_REFRESH_INTERVAL = 90000  // Refresh tokens every 90 seconds

    console.error(`[Queue] Starting processing of ${queueItems.length} tweets...`)
    console.error(`[Queue] Will stop after ${MAX_CONSECUTIVE_FAILURES} consecutive failures`)
    console.error(`[Queue] Token refresh interval: ${TOKEN_REFRESH_INTERVAL/1000}s`)
    process.stderr.write(`[Queue] Beginning tweet processing loop for ${queueItems.length} tweets\n`)

    for (let i = 0; i < queueItems.length; i++) {
      const item = queueItems[i]

      // Refresh API keys periodically to avoid stale tokens in long-running batches
      const timeSinceRefresh = Date.now() - lastTokenRefresh
      if (timeSinceRefresh >= TOKEN_REFRESH_INTERVAL) {
        console.error(`[Queue] ⏱️  Token age: ${Math.round(timeSinceRefresh/1000)}s - refreshing tokens...`)
        try {
          const pythonPath = process.env.PYTHON_PATH || '/home/debian/Tools/WDFWatch/venv/bin/python'
          const ensureFreshScript = '/home/debian/Tools/WDFWatch/scripts/ensure_fresh_tokens.py'

          const { stdout } = await execAsync(`${pythonPath} ${ensureFreshScript} --max-age 0 --output-tokens`, {
            timeout: 5000
          })

          if (stdout) {
            const newTokens = JSON.parse(stdout.trim())
            apiKeys = { ...apiKeys, ...newTokens }
            lastTokenRefresh = Date.now()
            console.error(`[Queue] ✅ Tokens refreshed successfully (tweet ${i + 1}/${queueItems.length})`)
          }
        } catch (refreshError) {
          console.error(`[Queue] ⚠️ Token refresh failed, continuing with existing tokens:`, refreshError)
        }
      }

      // Check if we should stop due to consecutive failures
      if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
        console.error(`[Queue] ❌ STOPPING: ${consecutiveFailures} consecutive failures reached (max: ${MAX_CONSECUTIVE_FAILURES})`)
        console.log(`[Queue] Successfully processed ${successCount} tweets before stopping`)
        break
      }

      // Check if batch processing has exceeded maximum duration (timeout protection)
      const elapsedTime = Date.now() - batchStartTime
      if (elapsedTime >= MAX_BATCH_DURATION_MS) {
        console.error(`[Queue] ⏱️  STOPPING: Batch processing timeout reached`)
        console.error(`[Queue] Elapsed time: ${Math.round(elapsedTime / 1000 / 60)} minutes (max: ${MAX_BATCH_DURATION_MS / 1000 / 60} minutes)`)
        console.log(`[Queue] Successfully processed ${successCount} tweets before timeout`)
        break
      }

      // Health check: Log progress periodically
      if ((i + 1) % 5 === 0) {
        const elapsedMinutes = Math.round(elapsedTime / 1000 / 60)
        const remainingMinutes = Math.round((MAX_BATCH_DURATION_MS - elapsedTime) / 1000 / 60)
        console.error(`[Queue] 🏥 Health check - Progress: ${i + 1}/${queueItems.length} tweets`)
        console.error(`[Queue] 🏥 Success rate: ${successCount}/${i + 1} (${Math.round(successCount / (i + 1) * 100)}%)`)
        console.error(`[Queue] 🏥 Time: ${elapsedMinutes}min elapsed, ${remainingMinutes}min remaining`)
        console.error(`[Queue] 🏥 Token age: ${Math.round((Date.now() - lastTokenRefresh) / 1000)}s`)
      }

      // Add delay between posts to avoid Twitter's burst posting limits
      // Twitter has strict burst posting protection - need significant delays
      // First post: no delay
      // Subsequent posts: 45 second delay to avoid 429 rate limits
      if (i > 0) {
        const delayMs = 45000 // 45 seconds between posts to avoid burst limits
        console.log(`[Queue] Tweet ${i + 1}/${queueItems.length} - waiting ${delayMs/1000}s before next post (avoiding burst limits)...`)
        console.error(`[Queue] ⏱️  Waiting ${delayMs/1000} seconds between tweets to avoid rate limiting`)
        await new Promise(resolve => setTimeout(resolve, delayMs))
      } else {
        console.log(`[Queue] Processing tweet ${i + 1}/${queueItems.length} (no delay for first tweet)`)
      }

      // Write progress to stderr to ensure it's logged
      process.stderr.write(`[Queue] Processing tweet ${i + 1}/${queueItems.length} - ID: ${item.twitterId || 'unknown'}\n`)

      try {
        console.log(`[Queue] Processing item ID: ${item.id}, Twitter ID: ${item.twitterId}`)

        // Extract the response text from metadata
        const responseText = item.metadata?.responseText
        const twitterId = item.originalTweetId || item.twitterId

        if (!responseText || !twitterId) {
          console.error(`[Queue] ❌ Missing data for item ${item.id}:`, {
            hasResponseText: !!responseText,
            hasTwitterId: !!twitterId,
            metadata: item.metadata
          })

          // Mark as failed
          console.log(`[Queue] Marking item ${item.id} as failed`)
          await prisma.tweetQueue.update({
            where: { id: item.id },
            data: {
              status: 'failed',
              processedAt: new Date()
            }
          })

          results.push({
            id: item.id,
            tweetId: item.twitterId,
            status: 'failed',
            statusCode: 400,
            error: 'Missing required data',
            message: `Missing ${!responseText ? 'response text' : 'Twitter ID'}`
          })
          consecutiveFailures++
          console.log(`[Queue] Tweet ${i + 1}/${queueItems.length} - ID: ${item.twitterId || 'unknown'}`)
          console.log(`[Queue] Status: 400 BAD REQUEST - Missing required data`)
          console.log(`[Queue] Consecutive failures: ${consecutiveFailures}/${MAX_CONSECUTIVE_FAILURES}`)
          continue
        }

        console.log(`[Queue] Data validated:`, {
          twitterId,
          responseTextLength: responseText.length,
          preview: responseText.substring(0, 50) + '...'
        })

        // Mark as processing
        console.log(`[Queue] Updating status to 'processing'...`)
        await prisma.tweetQueue.update({
          where: { id: item.id },
          data: { status: 'processing' }
        })

        // Call Python script to post the reply
        const pythonPath = process.env.PYTHON_PATH || '/home/debian/Tools/WDFWatch/venv/bin/python'
        const scriptPath = '/home/debian/Tools/WDFWatch/scripts/safe_twitter_reply.py'

        // Use execFile to pass arguments directly without shell escaping
        // This preserves special characters (newlines, quotes, etc.) correctly
        const args = [scriptPath, '--tweet-id', twitterId, '--message', responseText]

        console.log(`[Queue] Executing Python script to post reply...`)
        console.log(`[Queue] Script: ${scriptPath}`)
        console.log(`[Queue] Tweet ID: ${twitterId}`)
        console.log(`[Queue] Response text length: ${responseText.length} chars`)
        console.log(`[Queue] Response preview: ${responseText.substring(0, 50)}...`)
        console.log(`[Queue] Contains newlines: ${responseText.includes('\n')}`)
        console.log(`[Queue] Contains quotes: ${responseText.includes('"') || responseText.includes("'")}`)

        try {
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
            timeout: 25000,  // 25-second timeout for Python script
            cwd: '/home/debian/Tools/WDFWatch'  // Set working directory
          })

          if (stderr && !stderr.includes('Warning')) {
            console.warn(`[Queue] ⚠️ Python stderr:`, stderr)
          }

          console.log(`[Queue] ✅ Python stdout:`, stdout)
          console.log(`[Queue] ✅ Reply posted successfully for tweet ${twitterId}`)
          
          // Mark as completed
          console.log(`[Queue] Updating status to 'completed'...`)
          await prisma.tweetQueue.update({
            where: { id: item.id },
            data: {
              status: 'completed',
              processedAt: new Date()
            }
          })

          // Update the draft status if we have the draft ID
          if (item.metadata?.draftId) {
            console.log(`[Queue] Updating draft ${item.metadata.draftId} to 'posted'...`)
            await prisma.draftReply.update({
              where: { id: item.metadata.draftId },
              data: {
                postedAt: new Date(),
                status: 'posted'
              }
            })
          }

          successCount++
          consecutiveFailures = 0  // Reset consecutive failures on success

          results.push({
            id: item.id,
            status: 'completed',
            tweetId: twitterId,
            statusCode: 200,
            message: 'Successfully posted to Twitter'
          })

          console.error(`[Queue] ✅✅ Tweet ${i + 1}/${queueItems.length} POSTED`)
          console.error(`[Queue] Tweet ID: ${twitterId} - Status: 200 OK - SUCCESS`)
          console.error(`[Queue] Stats: ${successCount} successes, ${consecutiveFailures} consecutive failures`)
          process.stderr.write(`[Queue] SUCCESS: Tweet ${i + 1}/${queueItems.length} posted successfully\n`)
          
        } catch (execError: any) {
          console.error(`[Queue] ❌ Failed to post reply for tweet ${twitterId}`)
          console.error(`[Queue] Error type:`, execError.constructor.name)
          console.error(`[Queue] Error message:`, execError.message)
          console.error(`[Queue] Error code:`, execError.code)

          // Capture full error output for better debugging
          const errorOutput = (execError.stderr || execError.stdout || execError.message || '').toString()
          console.error(`[Queue] Full stderr:`, execError.stderr || 'none')
          console.error(`[Queue] Full stdout:`, execError.stdout || 'none')
          console.log(`[Queue] Error output (first 200 chars):`, errorOutput.substring(0, 200))

          // Try to extract HTTP status code from error using structured error codes
          let statusCode = 500  // Default to 500 for unknown errors

          // Check for structured error codes first
          const twitterApiErrorMatch = errorOutput.match(/TWITTER_API_ERROR:\s*(\d+)/)
          const pythonExceptionMatch = errorOutput.match(/PYTHON_EXCEPTION:\s*(\w+)/)

          if (twitterApiErrorMatch) {
            statusCode = parseInt(twitterApiErrorMatch[1], 10)
            console.log(`[Queue] Detected Twitter API error with code: ${statusCode}`)
          } else if (pythonExceptionMatch) {
            console.log(`[Queue] Detected Python exception: ${pythonExceptionMatch[1]}`)
            statusCode = 500
          } else {
            // Fallback to string matching for backwards compatibility
            if (errorOutput.includes('429')) statusCode = 429
            else if (errorOutput.includes('401')) statusCode = 401
            else if (errorOutput.includes('404')) statusCode = 404
            else if (errorOutput.includes('403')) statusCode = 403
            else if (errorOutput.includes('400')) statusCode = 400
          }

          let finalStatus = 'failed'
          let errorCategory = 'unknown'
          let shouldRetry = true

          // Categorize the error based on output
          console.log(`[Queue] Analyzing error to determine category...`)

          if (errorOutput.includes('restricted who can reply') ||
              errorOutput.includes('not allowed to reply')) {
            // Tweet author has restricted replies - can't fix this
            errorCategory = 'reply_restricted'
            shouldRetry = false
            statusCode = 403  // Forbidden
            console.log(`[Queue] ❌ Tweet ${i + 1}/${queueItems.length} - ID: ${twitterId}`)
            console.log(`[Queue] ❌ Status: 403 FORBIDDEN - Reply restricted by author`)
          } else if (errorOutput.includes('deleted or not visible') ||
                     errorOutput.includes('Tweet that is deleted')) {
            // Tweet was deleted or is not visible - same as 404
            errorCategory = 'tweet_deleted'
            shouldRetry = false
            statusCode = 403  // Keep original status code
            console.log(`[Queue] ❌ Tweet ${i + 1}/${queueItems.length} - ID: ${twitterId}`)
            console.log(`[Queue] ❌ Status: 403 FORBIDDEN - Tweet deleted or not visible`)
          } else if (errorOutput.includes('duplicate content')) {
            // Already posted this exact message somewhere
            errorCategory = 'duplicate_content'
            finalStatus = 'completed' // Count as success since content exists
            shouldRetry = false
            statusCode = 409  // Conflict
            console.log(`[Queue] ⚠️ Tweet ${i + 1}/${queueItems.length} - ID: ${twitterId}`)
            console.log(`[Queue] ⚠️ Status: 409 CONFLICT - Duplicate content (counting as success)`)
          } else if (errorOutput.includes('404') ||
                     errorOutput.includes('Tweet not found') ||
                     errorOutput.includes('No status found')) {
            // Tweet was deleted
            errorCategory = 'tweet_deleted'
            shouldRetry = false
            statusCode = 404
            console.log(`[Queue] ❌ Tweet ${i + 1}/${queueItems.length} - ID: ${twitterId}`)
            console.log(`[Queue] ❌ Status: 404 NOT FOUND - Tweet deleted or doesn't exist`)
          } else if (errorOutput.includes('429') ||
                     errorOutput.includes('Too Many Requests')) {
            // Rate limited - DON'T WAIT, just mark for retry and continue
            errorCategory = 'rate_limited'
            shouldRetry = true
            statusCode = 429
            console.error(`[Queue] ⚠️ Tweet ${i + 1}/${queueItems.length} - ID: ${twitterId}`)
            console.error(`[Queue] ⚠️ Status: 429 RATE LIMITED - Hit Twitter API limit`)

            // Calculate when rate limit resets for information only
            const now = new Date()
            const currentMinute = now.getMinutes()

            // Twitter rate limits reset every 15 minutes at :00, :15, :30, :45
            let nextResetMinute
            if (currentMinute < 15) {
              nextResetMinute = 15
            } else if (currentMinute < 30) {
              nextResetMinute = 30
            } else if (currentMinute < 45) {
              nextResetMinute = 45
            } else {
              nextResetMinute = 0  // Next hour
            }

            const resetTime = new Date(now)
            resetTime.setMinutes(nextResetMinute)
            resetTime.setSeconds(0)
            resetTime.setMilliseconds(0)

            // If we're resetting to :00, it's the next hour
            if (nextResetMinute === 0 && currentMinute >= 45) {
              resetTime.setHours(resetTime.getHours() + 1)
            }

            const waitMs = resetTime.getTime() - now.getTime()
            const waitMinutes = Math.ceil(waitMs / 1000 / 60)

            console.error(`[Queue] ========== RATE LIMIT HIT ==========`)
            console.error(`[Queue] ⏰ Twitter allows 50 tweets per 15-minute window`)
            console.error(`[Queue] 📊 Successfully posted ${successCount} tweets so far`)
            console.error(`[Queue] 🔄 Current UTC time: ${now.toISOString()}`)
            console.error(`[Queue] 🔄 Rate limit resets at: ${resetTime.toISOString()} (UTC)`)
            console.error(`[Queue] ⏱️  Wait time: ${waitMinutes} minutes from now`)
            console.error(`[Queue] 🕐 Twitter resets limits at :00, :15, :30, :45 past each hour`)
            console.error(`[Queue] ❌ STOPPING PROCESSING - Please retry in ${waitMinutes} minutes`)
            console.error(`[Queue] ====================================`)

            // DON'T WAIT - just stop processing and return results
            // Mark this tweet as pending for retry
            shouldRetry = true
            errorCategory = 'rate_limited'

            // Stop processing remaining tweets
            console.error(`[Queue] Breaking out of loop due to rate limit`)

            // Update this tweet's status before breaking
            await prisma.tweetQueue.update({
              where: { id: item.id },
              data: {
                status: 'pending',
                retryCount: { increment: 1 },
                metadata: {
                  ...item.metadata,
                  lastError: 'Rate limited - retry later',
                  errorCategory: 'rate_limited',
                  shouldRetry: true,
                  lastAttempt: new Date().toISOString(),
                  nextRetryAfter: resetTime.toISOString()
                }
              }
            })

            results.push({
              id: item.id,
              tweetId: twitterId,
              status: 'pending',
              statusCode: 429,
              error: 'rate_limited',
              message: `Rate limited - retry in approximately ${waitMinutes} minutes`
            })

            // Break out of the loop
            break
          } else if (errorOutput.includes('401') ||
                     errorOutput.includes('Unauthorized')) {
            // Token issue - needs attention
            errorCategory = 'auth_error'
            shouldRetry = false
            statusCode = 401
            console.log(`[Queue] ❌ Tweet ${i + 1}/${queueItems.length} - ID: ${twitterId}`)
            console.log(`[Queue] ❌ Status: 401 UNAUTHORIZED - Authentication failed (token expired?)`)
          } else {
            console.log(`[Queue] ❌ Tweet ${i + 1}/${queueItems.length} - ID: ${twitterId}`)
            console.log(`[Queue] ❌ Status: ${statusCode} ERROR - ${errorCategory}`)
          }

          // Update queue item based on error category
          console.log(`[Queue] Determining how to handle error...`)
          const updateData: any = {
            processedAt: new Date(),
            retryCount: { increment: 1 }
          }

          // Set status based on category with exponential backoff for retries
          const currentRetryCount = item.retryCount || 0
          const maxRetries = 5 // Increased from 3 to 5 with exponential backoff

          if (finalStatus === 'completed') {
            updateData.status = 'completed'
            console.log(`[Queue] Will mark as completed (duplicate content)`)
          } else if (!shouldRetry || currentRetryCount >= maxRetries) {
            updateData.status = 'failed'
            console.log(`[Queue] Will mark as failed (no retry: ${!shouldRetry}, retry count: ${currentRetryCount}/${maxRetries})`)
          } else {
            updateData.status = 'pending' // Keep as pending for retry
            delete updateData.processedAt // Don't set processedAt for pending

            // Calculate exponential backoff delay: 2^retryCount minutes
            const backoffMinutes = Math.pow(2, currentRetryCount)
            const nextRetryTime = new Date(Date.now() + backoffMinutes * 60 * 1000)

            console.log(`[Queue] Will keep as pending for retry #${currentRetryCount + 1}/${maxRetries}`)
            console.log(`[Queue] Exponential backoff: ${backoffMinutes} minutes (next retry after ${nextRetryTime.toISOString()})`)
          }

          // Update metadata with error details
          const currentMetadata = item.metadata || {}
          updateData.metadata = {
            ...currentMetadata,
            lastError: errorOutput.substring(0, 500),
            errorCategory,
            shouldRetry,
            lastAttempt: new Date().toISOString()
          }

          console.log(`[Queue] Updating queue item with status: ${updateData.status}`)
          await prisma.tweetQueue.update({
            where: { id: item.id },
            data: updateData
          })

          // Increment consecutive failures ONLY for retryable errors
          // Don't count permanent failures (deleted tweets, reply restrictions) as these aren't system issues
          const permanentFailures = ['tweet_deleted', 'reply_restricted', 'duplicate_content', 'rate_limited']
          if (!permanentFailures.includes(errorCategory)) {
            consecutiveFailures++
            console.log(`[Queue] ❌ Consecutive failure count: ${consecutiveFailures}/${MAX_CONSECUTIVE_FAILURES} (category: ${errorCategory})`)
          } else {
            console.log(`[Queue] Not counting as consecutive failure (permanent failure: ${errorCategory})`)
          }

          results.push({
            id: item.id,
            tweetId: twitterId,
            status: updateData.status,
            statusCode,
            error: errorCategory,
            message: errorOutput.substring(0, 200)
          })
        }
        
      } catch (error: any) {
        console.error(`[Queue] ❌❌ UNEXPECTED ERROR processing item ${item.id}`)
        console.error(`[Queue] Error type:`, error.constructor?.name)
        console.error(`[Queue] Error message:`, error.message)
        console.error(`[Queue] Stack trace:`, error.stack)
        consecutiveFailures++  // Increment on general errors too
        console.log(`[Queue] ❌ Consecutive failures: ${consecutiveFailures}/${MAX_CONSECUTIVE_FAILURES}`)

        results.push({
          id: item.id,
          tweetId: item.twitterId || 'unknown',
          status: 'error',
          statusCode: 500,
          error: 'unexpected_error',
          message: error.message
        })
        console.log(`[Queue] Tweet ${i + 1}/${queueItems.length} - ID: ${item.twitterId || 'unknown'}`)
        console.log(`[Queue] Status: 500 INTERNAL ERROR - Unexpected error`)
      }
    }

    // Create audit log
    console.log(`[Queue] Creating audit log entry...`)
    const successfulCount = results.filter(r => r.status === 'completed').length
    const failedCount = results.filter(r => r.status === 'failed' || r.status === 'error').length
    const remainingCount = queueItems.length - results.length

    await prisma.auditLog.create({
      data: {
        action: 'PROCESS_TWEET_QUEUE',
        resourceType: 'tweet_queue',
        metadata: {
          batchSize,
          processed: results.length,
          totalInQueue: queueItems.length,
          successful: successfulCount,
          failed: failedCount,
          remaining: remainingCount,
          stoppedEarly: consecutiveFailures >= MAX_CONSECUTIVE_FAILURES,
          consecutiveFailures,
          results
        }
      }
    })
    console.log(`[Queue] ✅ Audit log created`)

    const stoppedEarly = consecutiveFailures >= MAX_CONSECUTIVE_FAILURES
    const hitRateLimit = results.some(r => r.error === 'rate_limited')

    let message = 'Queue processing completed'
    if (stoppedEarly) {
      message = `Queue processing stopped after ${consecutiveFailures} consecutive failures`
    } else if (hitRateLimit && results.filter(r => r.status === 'completed').length >= 45) {
      message = `Queue processing completed successfully with automatic rate limit handling`
    }

    console.log(`[Queue] ========== FINAL RESULTS ==========`)
    console.log(`[Queue] Message: ${message}`)
    console.log(`[Queue] Processed: ${results.length}/${queueItems.length} items`)
    console.log(`[Queue] Successful: ${successfulCount} tweets posted`)
    console.log(`[Queue] Failed: ${failedCount} tweets failed`)
    console.log(`[Queue] Remaining: ${remainingCount} tweets not processed`)

    // Log individual tweet results
    console.error(`[Queue] \n========== PER-TWEET RESULTS ==========`)
    results.forEach((result, idx) => {
      const icon = result.status === 'completed' ? '✅' : '❌'
      console.error(`[Queue] ${icon} Tweet ${idx + 1}: ${result.tweetId} - Status ${result.statusCode} - ${result.status.toUpperCase()}${result.error ? ` (${result.error})` : ''}`)
    })
    console.error(`[Queue] ========================================\n`)

    if (hitRateLimit) {
      console.log(`[Queue] Note: Hit rate limit and handled it automatically`)
    }
    if (stoppedEarly) {
      console.log(`[Queue] Note: Stopped early due to consecutive failures`)
    }
    console.error(`[Queue] ===================================`)
    console.error('==================== QUEUE PROCESSING END ====================')
    process.stderr.write(`[Queue] Completed processing: ${successfulCount} success, ${failedCount} failed\n`)

    return NextResponse.json({
      message,
      processed: results.length,
      totalInQueue: queueItems.length,
      successful: results.filter(r => r.status === 'completed').length,
      failed: results.filter(r => r.status === 'failed' || r.status === 'error').length,
      remaining: queueItems.length - results.length,
      stoppedEarly,
      tokenRefreshed: true,  // Always true since we force refresh
      results
    })
    
  } catch (error: any) {
    console.error('[Queue] ❌❌❌ CRITICAL ERROR IN QUEUE PROCESSING ❌❌❌')
    console.error('[Queue] Error type:', error.constructor?.name)
    console.error('[Queue] Error message:', error.message)
    console.error('[Queue] Stack trace:', error.stack)
    console.error('[Queue] Full error:', error)
    console.log('==================== QUEUE PROCESSING FAILED ====================')

    return NextResponse.json(
      { error: 'Failed to process queue' },
      { status: 500 }
    )
  }
}