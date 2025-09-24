/**
 * Reset endpoint for clearing pipeline stage outputs
 * Deletes drafts from database when response stage is reset
 */

import { NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { unlink } from 'fs/promises'
import { join } from 'path'

export async function POST(
  request: Request,
  { params }: { params: { id: string } }
) {
  try {
    const episodeId = parseInt(params.id)
    const { stageId } = await request.json()

    // Get episode details
    const episode = await prisma.podcastEpisode.findUnique({
      where: { id: episodeId },
      select: {
        id: true,
        episodeDir: true,
        claudeEpisodeDir: true,
        tweets: {
          select: { id: true }
        }
      }
    })

    if (!episode) {
      return NextResponse.json(
        { error: 'Episode not found' },
        { status: 404 }
      )
    }

    // Handle response stage reset - delete all pending drafts
    if (stageId === 'response') {
      // Get all tweet IDs for this episode
      const tweetIds = episode.tweets.map(t => t.id)
      
      if (tweetIds.length > 0) {
        // Delete all pending drafts for these tweets
        const result = await prisma.draftReply.deleteMany({
          where: {
            tweetId: { in: tweetIds },
            status: 'pending'
          }
        })
        
        console.log(`Deleted ${result.count} pending drafts for episode ${episodeId}`)
      }

      // Also delete the responses.json file if it exists
      const episodeDir = episode.claudeEpisodeDir || episode.episodeDir
      if (episodeDir) {
        try {
          const responsesPath = join(
            process.cwd(),
            '..',
            'claude-pipeline',
            'episodes',
            episodeDir,
            'responses.json'
          )
          await unlink(responsesPath)
          console.log(`Deleted responses.json for episode ${episodeId}`)
        } catch (error) {
          // File might not exist, that's OK
          console.log('responses.json not found or already deleted')
        }
      }
    }

    // Handle classification stage reset
    if (stageId === 'classification') {
      // Update tweets to reset classification
      await prisma.tweet.updateMany({
        where: { episodeId },
        data: {
          status: 'scraped',
          classificationScore: null,
          classificationReason: null
        }
      })

      // Delete classified.json file
      const episodeDir = episode.claudeEpisodeDir || episode.episodeDir
      if (episodeDir) {
        try {
          const classifiedPath = join(
            process.cwd(),
            '..',
            'claude-pipeline',
            'episodes',
            episodeDir,
            'classified.json'
          )
          await unlink(classifiedPath)
          console.log(`Deleted classified.json for episode ${episodeId}`)
        } catch (error) {
          console.log('classified.json not found or already deleted')
        }
      }
    }

    // Handle summarization stage reset
    if (stageId === 'summarization') {
      // Delete keywords from database
      await prisma.keyword.deleteMany({
        where: { episodeId }
      })

      // Delete summary files
      const episodeDir = episode.claudeEpisodeDir || episode.episodeDir
      if (episodeDir) {
        const filesToDelete = ['summary.md', 'keywords.json', 'transcript.txt']
        for (const file of filesToDelete) {
          try {
            const filePath = join(
              process.cwd(),
              '..',
              'claude-pipeline',
              'episodes',
              episodeDir,
              file
            )
            await unlink(filePath)
            console.log(`Deleted ${file} for episode ${episodeId}`)
          } catch (error) {
            console.log(`${file} not found or already deleted`)
          }
        }
      }
    }

    return NextResponse.json({
      success: true,
      message: `Reset ${stageId} stage for episode ${episodeId}`
    })
  } catch (error) {
    console.error('Error resetting stage:', error)
    return NextResponse.json(
      { error: 'Failed to reset stage' },
      { status: 500 }
    )
  }
}