/**
 * API route for manually triggering tweet scraping
 * 
 * Allows users to initiate scraping with custom parameters:
 * - Specific keywords or use existing ones
 * - Custom date ranges and limits
 * - Episode association
 * 
 * Related files:
 * - /web/app/(dashboard)/scraping/page.tsx (UI trigger)
 * - /src/wdf/tasks/scrape.py (Python scraping task)
 * - /web/lib/web_bridge.py (Python integration)
 */

import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { getCurrentUserId } from '@/lib/auth'
import { z } from 'zod'
import { exec } from 'child_process'
import { promisify } from 'util'
import path from 'path'

const execAsync = promisify(exec)

const ScrapeRequestSchema = z.object({
  episodeId: z.string().optional(),
  keywords: z.array(z.string()).optional(),
  useEpisodeKeywords: z.boolean().default(true),
  maxTweets: z.number().min(1).max(1000).optional(),
  maxResultsPerKeyword: z.number().min(10).max(100).optional(),
  daysBack: z.number().min(1).max(365).optional(),
  minLikes: z.number().min(0).optional(),
  minRetweets: z.number().min(0).optional(),
  excludeReplies: z.boolean().optional(),
  excludeRetweets: z.boolean().optional(),
})

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const validated = ScrapeRequestSchema.parse(body)

    // Generate a unique run ID
    const runId = `manual-scrape-${Date.now()}`

    // Prepare keywords
    let keywords: string[] = []
    
    if (validated.keywords && validated.keywords.length > 0) {
      // Use provided keywords
      keywords = validated.keywords
    } else if (validated.useEpisodeKeywords && validated.episodeId) {
      // Fetch keywords from episode
      const episodeKeywords = await prisma.keyword.findMany({
        where: {
          episodeId: parseInt(validated.episodeId),
        },
        orderBy: { weight: 'desc' },
      })
      keywords = episodeKeywords.map(k => k.keyword)
    } else {
      // Fetch all enabled keywords
      const allKeywords = await prisma.keyword.findMany({
        where: {},
        orderBy: { weight: 'desc' },
        take: 20, // Limit to top 20 keywords
      })
      keywords = allKeywords.map(k => k.keyword)
    }

    if (keywords.length === 0) {
      return NextResponse.json(
        { error: 'No keywords available for scraping' },
        { status: 400 }
      )
    }

    // Fetch scraping settings or use provided values
    let scrapingConfig = {
      maxTweets: 100,
      maxResultsPerKeyword: 10,
      daysBack: 7,
      minLikes: 0,
      minRetweets: 0,
      excludeReplies: false,
      excludeRetweets: false,
    }

    const settings = await prisma.setting.findUnique({
      where: { key: 'scraping_config' }
    })

    if (settings && settings.value) {
      scrapingConfig = { ...scrapingConfig, ...(settings.value as any) }
    }

    // Override with request parameters
    if (validated.maxTweets !== undefined) scrapingConfig.maxTweets = validated.maxTweets
    if (validated.maxResultsPerKeyword !== undefined) scrapingConfig.maxResultsPerKeyword = validated.maxResultsPerKeyword
    if (validated.daysBack !== undefined) scrapingConfig.daysBack = validated.daysBack
    if (validated.minLikes !== undefined) scrapingConfig.minLikes = validated.minLikes
    if (validated.minRetweets !== undefined) scrapingConfig.minRetweets = validated.minRetweets
    if (validated.excludeReplies !== undefined) scrapingConfig.excludeReplies = validated.excludeReplies
    if (validated.excludeRetweets !== undefined) scrapingConfig.excludeRetweets = validated.excludeRetweets

    // Create audit log for scraping request
    await prisma.auditLog.create({
      data: {
        action: 'TRIGGER_MANUAL_SCRAPE',
        resourceType: 'scraping',
        resourceId: null,
        metadata: {
          keywords: keywords,
          config: scrapingConfig,
          episodeId: validated.episodeId,
        },
        userId: await getCurrentUserId(),
      },
    })

    // Prepare scraping parameters as JSON
    const scrapingParams = {
      keywords,
      ...scrapingConfig,
      run_id: runId,
      episode_id: validated.episodeId,
    }

    // Execute Python scraping task with parameters
    const projectRoot = path.resolve(process.cwd(), '..')
    const pythonPath = process.env.PYTHON_PATH || 'python'
    
    const command = `cd "${projectRoot}" && ${pythonPath} src/wdf/tasks/scrape_manual.py --params '${JSON.stringify(scrapingParams)}'`
    
    // Start the process asynchronously
    exec(command, (error, stdout, stderr) => {
      if (error) {
        console.error('Scraping process error:', error)
        console.error('stderr:', stderr)
      } else {
        console.log('Scraping completed:', stdout)
      }
    })

    return NextResponse.json({
      message: 'Scraping initiated successfully',
      runId,
      keywords: keywords.length,
      config: scrapingConfig,
    }, { status: 202 }) // 202 Accepted for async operation
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid scraping parameters', details: error.errors },
        { status: 400 }
      )
    }

    console.error('Failed to trigger scraping:', error)
    return NextResponse.json(
      { error: 'Failed to trigger scraping' },
      { status: 500 }
    )
  }
}