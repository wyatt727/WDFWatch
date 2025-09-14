/**
 * API route for processing the tweet queue
 * Handles posting approved replies to Twitter
 * Interacts with: Python Twitter posting functionality
 */

import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { exec } from 'child_process'
import { promisify } from 'util'

const execAsync = promisify(exec)

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
        // Using safe_twitter_reply.py (which we'll create based on safe_twitter_post.py)
        const pythonPath = process.env.PYTHON_PATH || 'python3'
        const scriptPath = '/Users/pentester/Tools/WDFWatch/scripts/safe_twitter_reply.py'
        
        const command = `${pythonPath} ${scriptPath} --tweet-id "${twitterId}" --message "${responseText.replace(/"/g, '\\"')}"`
        
        try {
          // Clean environment to avoid conflicts
          const cleanEnv = { ...process.env }
          delete cleanEnv.DEBUG  // Remove Prisma debug flag that causes pydantic error
          
          const { stdout, stderr } = await execAsync(command, {
            env: {
              ...cleanEnv,
              // Ensure we're using WDFwatch tokens
              WDFWATCH_MODE: 'true',
              WDF_DEBUG: 'false'  // Override the debug setting
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
          
          // Mark as failed and increment retry count
          await prisma.tweetQueue.update({
            where: { id: item.id },
            data: { 
              status: 'failed',
              processedAt: new Date(),
              retryCount: { increment: 1 }
            }
          })
          
          results.push({ 
            id: item.id, 
            status: 'failed', 
            error: execError.message 
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