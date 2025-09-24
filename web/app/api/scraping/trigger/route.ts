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
import { decrypt } from '@/lib/crypto'
import { z } from 'zod'
import { exec } from 'child_process'
import { promisify } from 'util'
import path from 'path'
import fs from 'fs/promises'

const execAsync = promisify(exec)

const ScrapeRequestSchema = z.object({
  episodeId: z.string().optional(),
  keywords: z.array(z.string()).optional(),
  useEpisodeKeywords: z.boolean().default(true),
  maxTweets: z.number().min(1).max(1000).optional(),
  maxResultsPerKeyword: z.number().min(10).max(100).optional(),
  targetTweetsPerKeyword: z.number().min(50).max(500).optional(), // For focused mode
  daysBack: z.number().min(1).max(365).optional(),
  minLikes: z.number().min(0).optional(),
  minRetweets: z.number().min(0).optional(),
  excludeReplies: z.boolean().optional(),
  excludeRetweets: z.boolean().optional(),
  createEpisode: z.boolean().optional(),
  focusedMode: z.boolean().optional(),
})

// Helper to copy files from one episode to another
async function copyEpisodeTemplate(sourceDir: string, targetDir: string) {
  const fs = await import('fs/promises')
  const filesToCopy = ['transcript.txt', 'summary.md', 'podcast_overview.txt', 'video_url.txt']

  for (const file of filesToCopy) {
    const sourcePath = path.join(sourceDir, file)
    const targetPath = path.join(targetDir, file)
    try {
      await fs.copyFile(sourcePath, targetPath)
    } catch (error) {
      console.warn(`Could not copy ${file}:`, error)
    }
  }
}

// Helper to load API keys from database
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

    // Handle compound API keys (client_id:client_secret format)
    if (apiEnvVars.API_KEY) {
      // If API_KEY contains colon, it's in compound format
      if (apiEnvVars.API_KEY.includes(':')) {
        const [clientId, clientSecret] = apiEnvVars.API_KEY.split(':', 2)
        apiEnvVars.CLIENT_ID = clientId
        apiEnvVars.API_KEY = clientId  // Overwrite compound with extracted ID
        console.log('Extracted CLIENT_ID from compound API_KEY')

        // If we got a secret from the compound, use it as CLIENT_SECRET
        if (clientSecret && !apiEnvVars.CLIENT_SECRET) {
          apiEnvVars.CLIENT_SECRET = clientSecret
        }
      } else {
        apiEnvVars.CLIENT_ID = apiEnvVars.API_KEY
      }
    }

    if (apiEnvVars.API_KEY_SECRET) {
      // If API_KEY_SECRET contains colon, extract the actual secret
      if (apiEnvVars.API_KEY_SECRET.includes(':')) {
        const parts = apiEnvVars.API_KEY_SECRET.split(':')
        const actualSecret = parts[parts.length - 1]  // Take the last part as the secret
        apiEnvVars.CLIENT_SECRET = actualSecret
        apiEnvVars.API_KEY_SECRET = actualSecret  // Overwrite compound with extracted secret
        console.log('Extracted CLIENT_SECRET from compound API_KEY_SECRET')
      } else {
        apiEnvVars.CLIENT_SECRET = apiEnvVars.API_KEY_SECRET
      }
    }

    console.log('Successfully loaded API keys from .env.wdfwatch')
    const relevantKeys = Object.keys(apiEnvVars).filter(k =>
      k.includes('API') || k.includes('TOKEN') || k.includes('CLIENT') || k.includes('WDFWATCH')
    )
    console.log(`Found ${relevantKeys.length} API-related keys:`, relevantKeys)

    // Clear DEBUG variable if it exists to prevent Python conflicts
    delete apiEnvVars.DEBUG

    return apiEnvVars
  } catch (fileError) {
    console.log('.env.wdfwatch not found or not readable:', fileError)
    console.log('Falling back to database...')

    // Fallback to database if .env.wdfwatch doesn't exist
    try {
      const setting = await prisma.setting.findUnique({
        where: { key: 'api_keys' }
      })

      if (!setting || !setting.value) {
        console.log('No API keys found in database either')
        return {}
      }

      console.log('Found API keys setting in database')

      const encryptedConfig = setting.value as any
      const apiEnvVars: Record<string, string> = {}

      // Decrypt Twitter API keys
      if (encryptedConfig.twitter) {
        console.log('Twitter config found, decrypting...')
        try {
          if (encryptedConfig.twitter.apiKey) {
            const decrypted = decrypt(encryptedConfig.twitter.apiKey)
            // Handle compound API key - extract CLIENT_ID
            if (decrypted.includes(':')) {
              const [clientId, clientSecret] = decrypted.split(':', 2)
              apiEnvVars.API_KEY = clientId  // Use extracted ID as API_KEY
              apiEnvVars.CLIENT_ID = clientId
              // If we got a secret from the compound, use it as CLIENT_SECRET
              if (clientSecret && !apiEnvVars.CLIENT_SECRET) {
                apiEnvVars.CLIENT_SECRET = clientSecret
              }
              console.log('  Decrypted compound API_KEY and extracted CLIENT_ID')
            } else {
              apiEnvVars.API_KEY = decrypted
              apiEnvVars.CLIENT_ID = decrypted // Alias for compatibility
              console.log('  Decrypted API_KEY')
            }
          }
          if (encryptedConfig.twitter.apiSecret) {
            const decrypted = decrypt(encryptedConfig.twitter.apiSecret)
            // Handle compound API secret - extract CLIENT_SECRET
            if (decrypted.includes(':')) {
              const parts = decrypted.split(':')
              const actualSecret = parts[parts.length - 1]  // Take the last part as the secret
              apiEnvVars.API_KEY_SECRET = actualSecret  // Use extracted secret as API_KEY_SECRET
              apiEnvVars.CLIENT_SECRET = actualSecret
              console.log('  Decrypted compound API_KEY_SECRET and extracted CLIENT_SECRET')
            } else {
              apiEnvVars.API_KEY_SECRET = decrypted
              apiEnvVars.CLIENT_SECRET = decrypted // Alias
              console.log('  Decrypted API_KEY_SECRET')
            }
          }
          if (encryptedConfig.twitter.bearerToken) {
            apiEnvVars.BEARER_TOKEN = decrypt(encryptedConfig.twitter.bearerToken)
            console.log('  Decrypted BEARER_TOKEN')
          }
          if (encryptedConfig.twitter.accessToken) {
            apiEnvVars.WDFWATCH_ACCESS_TOKEN = decrypt(encryptedConfig.twitter.accessToken)
            console.log('  Decrypted WDFWATCH_ACCESS_TOKEN')
          }
          if (encryptedConfig.twitter.accessTokenSecret) {
            apiEnvVars.WDFWATCH_ACCESS_TOKEN_SECRET = decrypt(encryptedConfig.twitter.accessTokenSecret)
            console.log('  Decrypted WDFWATCH_ACCESS_TOKEN_SECRET')
          }
        } catch (error) {
          console.error('Failed to decrypt Twitter API keys:', error)
        }
      }

      // Decrypt Gemini API key
      if (encryptedConfig.gemini?.apiKey) {
        try {
          apiEnvVars.GEMINI_API_KEY = decrypt(encryptedConfig.gemini.apiKey)
        } catch (error) {
          console.error('Failed to decrypt Gemini API key:', error)
        }
      }

      return apiEnvVars
    } catch (error) {
      console.error('Failed to load API keys from database:', error)
      return {}
    }
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const validated = ScrapeRequestSchema.parse(body)

    // Generate a unique run ID
    const runId = `manual-scrape-${Date.now()}`

    let episodeId: number | null = null
    let episodeTitle: string | null = null
    let episodeDir: string | undefined = undefined

    // Define episodes base directory at function scope
    const episodesBaseDir = process.env.EPISODES_DIR || path.join(process.cwd(), '..', 'claude-pipeline', 'episodes')

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

    // Create new episode if in focused mode
    if (validated.createEpisode && validated.focusedMode) {
      // Generate episode name from first keyword
      const baseKeyword = keywords[0].replace(/[^a-zA-Z0-9\s-]/g, '').replace(/\s+/g, '_').toLowerCase()
      episodeDir = `keyword_${baseKeyword}`

      // Check if episode with this name already exists
      const existingCount = await prisma.podcastEpisode.count({
        where: {
          title: {
            startsWith: `Keyword: ${keywords[0]}`
          }
        }
      })

      // Create unique title
      episodeTitle = existingCount > 0
        ? `Keyword: ${keywords[0]} (${existingCount + 1})`
        : `Keyword: ${keywords[0]}`

      // Create new episode in database
      const newEpisode = await prisma.podcastEpisode.create({
        data: {
          title: episodeTitle,
          status: 'scraping',
          claudePipelineStatus: 'in_progress',
          pipelineType: 'claude',
          claudeEpisodeDir: episodeDir, // Use keyword-based directory name
          // Store pipeline stages and metadata in pipelineConfiguration field
          pipelineConfiguration: {
            stages: {
              summarization: 'completed', // Already have summary from wdf_general
              tweet_discovery: 'in_progress',
              classification: 'pending',
              response_generation: 'pending',
              moderation: 'pending'
            },
            metadata: {
              episodeType: 'keyword_search',
              searchKeywords: keywords,
              targetTweetsPerKeyword: validated.targetTweetsPerKeyword || 100,
              createdFrom: 'manual_scrape',
              templateEpisode: 'wdf_general'
            }
          }
        }
      })

      episodeId = newEpisode.id

      // Create episode directory and copy files from wdf_general
      const newEpisodeDir = path.join(episodesBaseDir, episodeDir)
      const wdfGeneralDir = path.join(episodesBaseDir, 'wdf_general')

      // Create directory
      const fs = await import('fs/promises')
      await fs.mkdir(newEpisodeDir, { recursive: true })

      // Check if wdf_general exists before copying
      try {
        await fs.access(wdfGeneralDir)
        // Copy template files from wdf_general
        await copyEpisodeTemplate(wdfGeneralDir, newEpisodeDir)
      } catch (error) {
        console.warn('wdf_general template not found, creating minimal structure')
        // Create minimal files if wdf_general doesn't exist
        await fs.writeFile(
          path.join(newEpisodeDir, 'transcript.txt'),
          'General WDF podcast transcript placeholder'
        )
        await fs.writeFile(
          path.join(newEpisodeDir, 'summary.md'),
          '# WDF Podcast Summary\n\nGeneral summary for focused keyword search episodes.'
        )
      }

      // Create keywords.json with just the searched keywords
      await fs.writeFile(
        path.join(newEpisodeDir, 'keywords.json'),
        JSON.stringify(keywords, null, 2)
      )

      // Create metadata.json
      await fs.writeFile(
        path.join(newEpisodeDir, 'metadata.json'),
        JSON.stringify({
          episodeId: episodeId,
          title: episodeTitle,
          episodeType: 'keyword_search',
          searchKeywords: keywords,
          createdAt: new Date().toISOString(),
          pipelineStages: {
            summarization: 'completed',
            tweet_discovery: 'in_progress',
            classification: 'pending',
            response_generation: 'pending'
          }
        }, null, 2)
      )

      // Also save keywords to database
      await prisma.keyword.createMany({
        data: keywords.map(kw => ({
          keyword: kw,
          weight: 1.0,
          episodeId: episodeId
        }))
      })
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
    // In focused mode, use targetTweetsPerKeyword to set maxResultsPerKeyword
    if (validated.focusedMode && validated.targetTweetsPerKeyword) {
      scrapingConfig.maxResultsPerKeyword = validated.targetTweetsPerKeyword
      scrapingConfig.maxTweets = validated.targetTweetsPerKeyword * keywords.length
    }
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
      episode_id: episodeId ? String(episodeId) : validated.episodeId ? String(validated.episodeId) : undefined, // Convert to string for Python
      episode_dir: episodeDir || undefined, // Pass the actual directory name for keyword-based episodes
      focused_mode: validated.focusedMode || false,
      target_per_keyword: validated.targetTweetsPerKeyword || scrapingConfig.maxResultsPerKeyword,
    }

    // Load API keys from database
    const apiKeys = await loadApiKeys()

    // Execute Python scraping task with parameters
    const projectRoot = path.resolve(process.cwd(), '..')
    const pythonPath = process.env.PYTHON_PATH || '/home/debian/Tools/WDFWatch/venv/bin/python'

    // Use different Python script for focused mode
    const scriptName = validated.focusedMode ? 'scrape_focused.py' : 'scrape_manual.py'
    const command = `cd "${projectRoot}" && ${pythonPath} src/wdf/tasks/${scriptName} --params '${JSON.stringify(scrapingParams)}'`

    // Prepare environment variables with API keys
    const processEnv = {
      ...process.env,
      ...apiKeys,
      WDF_WEB_MODE: 'true',
      WDF_MOCK_MODE: 'false', // Force real Twitter API when manually triggered
      WDF_NO_AUTO_SCRAPE: 'false', // Allow scraping when manually triggered
      WDF_BYPASS_QUOTA_CHECK: 'true', // Bypass Redis quota checking for manual scraping
      WDF_REDIS_URL: 'redis://localhost:6379/0', // Ensure Redis URL is set
      EPISODES_DIR: episodesBaseDir, // Ensure Python uses the same episodes directory as Web UI
      WDF_CURRENT_EPISODE_ID: episodeId ? String(episodeId) : undefined // Pass episode ID for tweet association
    }

    // Execute scraping synchronously and wait for completion
    console.log('Starting scraping process...')
    console.log('Command:', command)
    console.log('Episode ID:', episodeId || 'None (no episode association)')
    console.log('API Keys loaded:', Object.keys(apiKeys).length > 0 ? `Found ${Object.keys(apiKeys).length} keys` : 'No API keys found')

    // Debug: Log the actual keys being passed (masked)
    for (const [key, value] of Object.entries(apiKeys)) {
      if (value) {
        console.log(`  ${key}: ***${value.slice(-4)}`)
      }
    }

    // Validate API keys before starting scrape
    const requiredKeys = ['API_KEY', 'API_KEY_SECRET', 'WDFWATCH_ACCESS_TOKEN']
    const missingKeys = requiredKeys.filter(key => !apiKeys[key])

    if (missingKeys.length > 0) {
      console.error('Missing required API keys:', missingKeys)
      throw new Error(`Missing required API keys: ${missingKeys.join(', ')}. Please configure Twitter API credentials in Settings.`)
    }

    try {
      // Run the scraping process and wait for it to complete
      const { stdout, stderr } = await execAsync(command, {
        maxBuffer: 1024 * 1024 * 10, // 10MB buffer for large outputs
        env: processEnv
      })

      console.log('Scraping completed successfully')
      console.log('stdout:', stdout)
      if (stderr) {
        console.warn('stderr:', stderr)
      }

      // Verify tweets.json was created if in focused mode
      if (validated.focusedMode && episodeId && episodeDir) {
        const tweetsPath = path.join(
          episodesBaseDir,
          episodeDir,
          'tweets.json'
        )

        try {
          const tweetsContent = await fs.readFile(tweetsPath, 'utf-8')
          const tweets = JSON.parse(tweetsContent)
          console.log(`Scraping successful: ${tweets.length} tweets collected`)

          // Update episode status to show scraping is complete
          await prisma.podcastEpisode.update({
            where: { id: episodeId },
            data: {
              status: 'ready_for_classification',
              claudePipelineStatus: 'ready',
              pipelineConfiguration: {
                stages: {
                  summarization: 'completed',
                  tweet_discovery: 'completed', // Mark as completed
                  classification: 'pending',
                  response_generation: 'pending',
                  moderation: 'pending'
                },
                metadata: {
                  episodeType: 'keyword_search',
                  searchKeywords: keywords,
                  targetTweetsPerKeyword: validated.targetTweetsPerKeyword || 100,
                  createdFrom: 'manual_scrape',
                  templateEpisode: 'wdf_general',
                  tweetsCollected: tweets.length,
                  scrapingCompletedAt: new Date().toISOString()
                }
              }
            }
          })

        } catch (fileError) {
          console.error('Failed to verify tweets.json:', fileError)
          // Don't throw - scraping might have partially succeeded
        }
      }

      return NextResponse.json({
        message: validated.focusedMode
          ? 'Episode created and scraping completed successfully'
          : 'Scraping completed successfully',
        runId,
        keywords: keywords.length,
        config: scrapingConfig,
        episodeId: episodeId,
        episodeTitle: episodeTitle,
        status: 'completed'
      }, { status: 200 }) // 200 OK - operation completed

    } catch (execError: any) {
      console.error('Scraping process failed:', execError)
      console.error('stderr:', execError.stderr)
      console.error('stdout:', execError.stdout)

      // Analyze error to provide better user feedback
      let errorMessage = 'Scraping failed'
      let userFriendlyMessage = execError.message || 'Unknown error occurred'

      // Check for authentication errors
      const errorOutput = (execError.stderr || '') + (execError.stdout || '')
      if (errorOutput.includes('401') || errorOutput.includes('Unauthorized')) {
        errorMessage = 'Twitter API authentication failed'
        userFriendlyMessage = 'Twitter API credentials are invalid or expired. Please check your API keys in Settings → API Keys.'
      } else if (errorOutput.includes('invalid_client')) {
        errorMessage = 'Twitter API client credentials invalid'
        userFriendlyMessage = 'Twitter API client ID/secret are invalid. Please verify your Twitter API app credentials in Settings → API Keys.'
      } else if (errorOutput.includes('Rate limited') || errorOutput.includes('429')) {
        errorMessage = 'Twitter API rate limit exceeded'
        userFriendlyMessage = 'Twitter API rate limit exceeded. Please wait a few minutes before trying again.'
      } else if (errorOutput.includes('No module named')) {
        errorMessage = 'Python dependency error'
        userFriendlyMessage = 'Server configuration error. Please contact support.'
      }

      // If episode was created but scraping failed, update its status
      if (episodeId) {
        await prisma.podcastEpisode.update({
          where: { id: episodeId },
          data: {
            status: 'error',
            claudePipelineStatus: 'error',
            pipelineConfiguration: {
              ...((await prisma.podcastEpisode.findUnique({
                where: { id: episodeId },
                select: { pipelineConfiguration: true }
              }))?.pipelineConfiguration as any || {}),
              error: errorMessage,
              details: userFriendlyMessage,
              stderr: execError.stderr,
              stdout: execError.stdout
            }
          }
        })
      }

      return NextResponse.json(
        {
          error: errorMessage,
          details: userFriendlyMessage,
          episodeId: episodeId, // Still return episode ID so user can retry
          technical: execError.message // Technical details for debugging
        },
        { status: 500 }
      )
    }
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid scraping parameters', details: error.errors },
        { status: 400 }
      )
    }

    console.error('Failed to trigger scraping:', error)
    const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred'
    return NextResponse.json(
      {
        error: 'Failed to trigger scraping',
        details: errorMessage,
        type: validated?.focusedMode ? 'focused_scrape' : 'standard_scrape'
      },
      { status: 500 }
    )
  }
}