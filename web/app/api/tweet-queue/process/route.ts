/**
 * API route for processing the tweet queue
 * Handles posting approved replies to Twitter
 * Interacts with: Python Twitter posting functionality
 */

import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { exec } from 'child_process'
import { promisify } from 'util'
import { decrypt } from '@/lib/crypto'

const execAsync = promisify(exec)

// Helper to load API keys from database with .env fallback
async function loadApiKeys() {
  const apiEnvVars: Record<string, string> = {}

  try {
    // First, try to load from database
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

  return apiEnvVars
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { batchSize = 10 } = body

    // Get pending items from the queue with approved_draft source
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

    if (queueItems.length === 0) {
      return NextResponse.json({
        message: 'No items to process',
        processed: 0
      })
    }

    // Load API keys once for all items
    const apiKeys = await loadApiKeys()

    const results = []

    for (const item of queueItems) {
      try {
        // Extract the response text from metadata
        const responseText = item.metadata?.responseText
        const twitterId = item.originalTweetId || item.twitterId

        if (!responseText || !twitterId) {
          console.error('Missing response text or Twitter ID for queue item:', item.id)

          // Mark as failed
          await prisma.tweetQueue.update({
            where: { id: item.id },
            data: {
              status: 'failed',
              processedAt: new Date()
            }
          })

          results.push({
            id: item.id,
            status: 'failed',
            error: 'Missing required data'
          })
          continue
        }

        // Mark as processing
        await prisma.tweetQueue.update({
          where: { id: item.id },
          data: { status: 'processing' }
        })

        // Call Python script to post the reply
        const pythonPath = process.env.PYTHON_PATH || 'python3'
        const scriptPath = '/home/debian/Tools/WDFWatch/scripts/safe_twitter_reply.py'

        // Escape the response text for shell - just escape double quotes to prevent breaking out
        const escapedResponse = responseText.replace(/"/g, '\\"')

        const command = `${pythonPath} ${scriptPath} --tweet-id "${twitterId}" --message "${escapedResponse}"`

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

          const { stdout, stderr } = await execAsync(command, {
            env: {
              ...cleanEnv,
              ...apiKeys,  // Include loaded API keys
              WDFWATCH_MODE: 'true',
              WDF_DEBUG: 'false',  // Override the debug setting
              WDF_WEB_MODE: 'true'  // Indicate we're running from web
            }
          })
          
          console.log('Reply posted successfully:', stdout)
          
          // Mark as completed
          await prisma.tweetQueue.update({
            where: { id: item.id },
            data: { 
              status: 'completed',
              processedAt: new Date()
            }
          })
          
          // Update the draft status if we have the draft ID
          if (item.metadata?.draftId) {
            await prisma.draftReply.update({
              where: { id: item.metadata.draftId },
              data: {
                postedAt: new Date(),
                status: 'posted'
              }
            })
          }
          
          results.push({ 
            id: item.id, 
            status: 'completed',
            tweetId: twitterId 
          })
          
        } catch (execError: any) {
          console.error('Failed to post reply:', execError)

          const errorOutput = (execError.stderr || execError.stdout || execError.message || '').toString()
          let finalStatus = 'failed'
          let errorCategory = 'unknown'
          let shouldRetry = true

          // Categorize the error based on output
          if (errorOutput.includes('restricted who can reply') ||
              errorOutput.includes('not allowed to reply')) {
            // Tweet author has restricted replies - can't fix this
            errorCategory = 'reply_restricted'
            shouldRetry = false
            console.log(`Tweet ${twitterId}: Reply restricted by author`)
          } else if (errorOutput.includes('duplicate content')) {
            // Already posted this exact message somewhere
            errorCategory = 'duplicate_content'
            finalStatus = 'completed' // Count as success since content exists
            shouldRetry = false
            console.log(`Tweet ${twitterId}: Duplicate content (already posted)`)
          } else if (errorOutput.includes('404') ||
                     errorOutput.includes('Tweet not found') ||
                     errorOutput.includes('No status found')) {
            // Tweet was deleted
            errorCategory = 'tweet_deleted'
            shouldRetry = false
            console.log(`Tweet ${twitterId}: Tweet deleted or not found`)
          } else if (errorOutput.includes('429') ||
                     errorOutput.includes('Too Many Requests')) {
            // Rate limited - should retry later
            errorCategory = 'rate_limited'
            shouldRetry = true
            console.log(`Tweet ${twitterId}: Rate limited`)
          } else if (errorOutput.includes('401') ||
                     errorOutput.includes('Unauthorized')) {
            // Token issue - needs attention
            errorCategory = 'auth_error'
            shouldRetry = false
            console.log(`Tweet ${twitterId}: Authentication error`)
          }

          // Update queue item based on error category
          const updateData: any = {
            processedAt: new Date(),
            retryCount: { increment: 1 }
          }

          // Set status based on category
          if (finalStatus === 'completed') {
            updateData.status = 'completed'
          } else if (!shouldRetry || (item.retryCount || 0) >= 3) {
            updateData.status = 'failed'
          } else {
            updateData.status = 'pending' // Keep as pending for retry
            delete updateData.processedAt // Don't set processedAt for pending
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

          await prisma.tweetQueue.update({
            where: { id: item.id },
            data: updateData
          })

          results.push({
            id: item.id,
            status: updateData.status,
            error: errorCategory,
            message: errorOutput.substring(0, 200)
          })
        }
        
      } catch (error: any) {
        console.error('Error processing queue item:', error)
        results.push({ 
          id: item.id, 
          status: 'error', 
          error: error.message 
        })
      }
    }

    // Create audit log
    await prisma.auditLog.create({
      data: {
        action: 'PROCESS_TWEET_QUEUE',
        resourceType: 'tweet_queue',
        metadata: {
          batchSize,
          processed: results.length,
          successful: results.filter(r => r.status === 'completed').length,
          failed: results.filter(r => r.status === 'failed').length,
          results
        }
      }
    })

    return NextResponse.json({
      message: 'Queue processing completed',
      processed: results.length,
      successful: results.filter(r => r.status === 'completed').length,
      failed: results.filter(r => r.status === 'failed').length,
      results
    })
    
  } catch (error) {
    console.error('Failed to process queue:', error)
    return NextResponse.json(
      { error: 'Failed to process queue' },
      { status: 500 }
    )
  }
}