/**
 * API route for managing episode keywords
 *
 * Handles updating keywords in both database and keywords.json file
 *
 * Related files:
 * - /web/components/episodes/KeywordsEditor.tsx (UI component)
 * - /src/wdf/tasks/scrape.py (Python scraping that reads keywords)
 */

import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { z } from 'zod'
import path from 'path'
import fs from 'fs/promises'

const KeywordsUpdateSchema = z.object({
  keywords: z.array(z.object({
    keyword: z.string().min(1),
    weight: z.number().min(0).max(1)
  })).min(1, 'At least one keyword is required')
})

export async function PUT(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const episodeId = parseInt(params.id)

    // Validate request body
    const body = await request.json()
    const validated = KeywordsUpdateSchema.parse(body)

    // Check if episode exists
    const episode = await prisma.podcastEpisode.findUnique({
      where: { id: episodeId },
      select: {
        id: true,
        claudeEpisodeDir: true,
        pipelineType: true,
        pipelineConfiguration: true
      }
    })

    if (!episode) {
      return NextResponse.json(
        { error: 'Episode not found' },
        { status: 404 }
      )
    }

    // Delete existing keywords and create new ones
    await prisma.$transaction([
      // Delete old keywords
      prisma.keyword.deleteMany({
        where: { episodeId }
      }),
      // Create new keywords
      prisma.keyword.createMany({
        data: validated.keywords.map(kw => ({
          keyword: kw.keyword,
          weight: kw.weight,
          episodeId: episodeId,
          enabled: true
        }))
      })
    ])

    // Update keywords.json file in episode directory
    const episodesBaseDir = process.env.EPISODES_DIR ||
      path.join(process.cwd(), '..', 'claude-pipeline', 'episodes')

    if (episode.claudeEpisodeDir) {
      const episodeDir = path.join(episodesBaseDir, episode.claudeEpisodeDir)
      const keywordsFilePath = path.join(episodeDir, 'keywords.json')

      try {
        // Check if directory exists
        await fs.access(episodeDir)

        // Format keywords for JSON file
        // Check episode type from pipelineConfiguration metadata
        const metadata = episode.pipelineConfiguration as any
        const episodeType = metadata?.metadata?.episodeType

        let keywordsData
        if (episodeType === 'keyword_search') {
          // Keyword search episodes: use simple string array format
          keywordsData = validated.keywords.map(kw => kw.keyword)
        } else {
          // Normal episodes: use object format with weights
          keywordsData = validated.keywords.map(kw => ({
            keyword: kw.keyword,
            weight: kw.weight
          }))
        }

        // Write to keywords.json
        await fs.writeFile(
          keywordsFilePath,
          JSON.stringify(keywordsData, null, 2),
          'utf-8'
        )

        console.log(`Updated keywords.json for episode ${episodeId} at ${keywordsFilePath}`)
      } catch (error) {
        console.warn(`Could not update keywords.json file: ${error}`)
        // Don't fail the request if file write fails - database update succeeded
      }
    }

    // Also update transcripts/keywords.json if this is a legacy episode
    if (!episode.claudeEpisodeDir) {
      const transcriptsDir = path.join(process.cwd(), '..', 'transcripts')
      const keywordsFilePath = path.join(transcriptsDir, 'keywords.json')

      try {
        const keywordsData = validated.keywords.map(kw => ({
          keyword: kw.keyword,
          weight: kw.weight
        }))

        await fs.writeFile(
          keywordsFilePath,
          JSON.stringify(keywordsData, null, 2),
          'utf-8'
        )

        console.log(`Updated transcripts/keywords.json for legacy episode ${episodeId}`)
      } catch (error) {
        console.warn(`Could not update transcripts/keywords.json: ${error}`)
      }
    }

    return NextResponse.json({
      success: true,
      message: `Updated ${validated.keywords.length} keywords`,
      keywords: validated.keywords
    })

  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid keywords data', details: error.errors },
        { status: 400 }
      )
    }

    console.error('Failed to update keywords:', error)
    return NextResponse.json(
      { error: 'Failed to update keywords', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    )
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const episodeId = parseInt(params.id)

    // Fetch keywords from database
    const keywords = await prisma.keyword.findMany({
      where: {
        episodeId,
        enabled: true
      },
      select: {
        keyword: true,
        weight: true
      },
      orderBy: [
        { weight: 'desc' },
        { keyword: 'asc' }
      ]
    })

    return NextResponse.json({
      keywords
    })

  } catch (error) {
    console.error('Failed to fetch keywords:', error)
    return NextResponse.json(
      { error: 'Failed to fetch keywords' },
      { status: 500 }
    )
  }
}
