/**
 * API routes for managing scraping settings
 * 
 * Handles configuration for tweet scraping including:
 * - Tweet count limits
 * - Date range filters
 * - Engagement thresholds
 * 
 * Related files:
 * - /web/app/(dashboard)/settings/scraping/page.tsx (UI component)
 * - /src/wdf/tasks/scrape.py (Python scraping task)
 */

import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { z } from 'zod'

// Schema for scraping settings
const ScrapingSettingsSchema = z.object({
  maxTweets: z.number().min(1).max(1000).default(100),
  maxResultsPerKeyword: z.number().min(10).max(100).default(10), // Conservative default for API quota
  daysBack: z.number().min(1).max(365).default(7),
  minLikes: z.number().min(0).default(0),
  minRetweets: z.number().min(0).default(0),
  minReplies: z.number().min(0).default(0),
  excludeReplies: z.boolean().default(false),
  excludeRetweets: z.boolean().default(false),
  language: z.string().default('en'),
})

export type ScrapingSettings = z.infer<typeof ScrapingSettingsSchema>

const SETTINGS_KEY = 'scraping_config'

export async function GET() {
  try {
    // Fetch scraping settings from database
    const setting = await prisma.setting.findUnique({
      where: { key: SETTINGS_KEY }
    })

    if (!setting) {
      // Return default settings if none exist
      const defaultSettings: ScrapingSettings = {
        maxTweets: 100,
        maxResultsPerKeyword: 10,  // Conservative default (NOT 100!)
        daysBack: 7,
        minLikes: 0,
        minRetweets: 0,
        minReplies: 0,
        excludeReplies: false,
        excludeRetweets: false,
        language: 'en',
      }
      
      return NextResponse.json(defaultSettings)
    }

    const settings = ScrapingSettingsSchema.parse(setting.value)
    return NextResponse.json(settings)
  } catch (error) {
    console.error('Failed to fetch scraping settings:', error)
    return NextResponse.json(
      { error: 'Failed to fetch scraping settings' },
      { status: 500 }
    )
  }
}

export async function PUT(request: NextRequest) {
  try {
    const body = await request.json()
    const validatedSettings = ScrapingSettingsSchema.parse(body)

    // Upsert settings in database
    const setting = await prisma.setting.upsert({
      where: { key: SETTINGS_KEY },
      update: {
        value: validatedSettings,
        updatedAt: new Date(),
      },
      create: {
        key: SETTINGS_KEY,
        value: validatedSettings,
        description: 'Tweet scraping configuration',
      },
    })

    // Log audit event
    await prisma.auditLog.create({
      data: {
        action: 'UPDATE_SCRAPING_SETTINGS',
        resourceType: 'setting',
        resourceId: null,
        metadata: {
          changes: validatedSettings,
        },
        userId: 'system', // TODO: Get from auth context
      },
    })

    return NextResponse.json(validatedSettings)
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid settings format', details: error.errors },
        { status: 400 }
      )
    }

    console.error('Failed to update scraping settings:', error)
    return NextResponse.json(
      { error: 'Failed to update scraping settings' },
      { status: 500 }
    )
  }
}