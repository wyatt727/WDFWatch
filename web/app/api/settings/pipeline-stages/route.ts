/**
 * Pipeline Stages Settings API
 * 
 * Manages which pipeline stages are enabled/disabled for episodes.
 * Allows users to configure:
 * - Enable/disable individual stages (summarization, fewshot, classification, response, moderation)
 * - Stage-specific settings
 * - Pipeline type preferences (claude, legacy, hybrid)
 * 
 * Related files:
 * - /web/lib/llm-models.ts (Stage configuration constants)
 * - /web/app/(dashboard)/settings/pipeline-stages/page.tsx (UI component)
 */

import { NextRequest, NextResponse } from 'next/server'
import { PrismaClient } from '@prisma/client'
import { DEFAULT_STAGE_CONFIG } from '@/lib/llm-models'

const prisma = new PrismaClient()

const SETTINGS_KEY = 'pipeline_stages'

interface StageConfig {
  enabled: boolean
  required: boolean
  model?: string // Optional model override per stage
}

interface PipelineStagesConfig {
  summarization: StageConfig
  fewshot: StageConfig
  scraping: StageConfig
  classification: StageConfig
  response: StageConfig
  moderation: StageConfig
  pipeline_type?: 'claude' | 'legacy' | 'hybrid' // Overall pipeline preference
}

/**
 * GET /api/settings/pipeline-stages
 * 
 * Returns current pipeline stages configuration
 */
export async function GET(request: NextRequest) {
  try {
    // Fetch current settings from database
    const setting = await prisma.setting.findUnique({
      where: { key: SETTINGS_KEY }
    })

    let stageConfig: PipelineStagesConfig

    if (setting?.value) {
      // Use existing configuration
      stageConfig = setting.value as PipelineStagesConfig
    } else {
      // Use defaults if no configuration exists
      stageConfig = {
        summarization: DEFAULT_STAGE_CONFIG.summarization,
        fewshot: DEFAULT_STAGE_CONFIG.fewshot,
        scraping: DEFAULT_STAGE_CONFIG.scraping,
        classification: DEFAULT_STAGE_CONFIG.classification,
        response: DEFAULT_STAGE_CONFIG.response,
        moderation: DEFAULT_STAGE_CONFIG.moderation,
        pipeline_type: 'hybrid'
      }
    }

    return NextResponse.json({
      success: true,
      data: stageConfig
    })

  } catch (error) {
    console.error('Failed to get pipeline stages:', error)
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to retrieve pipeline stages configuration' 
      },
      { status: 500 }
    )
  }
}

/**
 * PUT /api/settings/pipeline-stages
 * 
 * Updates pipeline stages configuration
 */
export async function PUT(request: NextRequest) {
  try {
    const body = await request.json()
    
    // Validate the incoming configuration
    const validatedConfig = validateStageConfig(body)
    
    if (!validatedConfig.isValid) {
      return NextResponse.json(
        { 
          success: false, 
          error: 'Invalid stage configuration',
          details: validatedConfig.errors
        },
        { status: 400 }
      )
    }

    // Save to database
    await prisma.setting.upsert({
      where: { key: SETTINGS_KEY },
      update: { 
        value: validatedConfig.config,
        updatedAt: new Date()
      },
      create: { 
        key: SETTINGS_KEY, 
        value: validatedConfig.config,
        updatedAt: new Date()
      }
    })

    // Log the configuration change
    console.log('Pipeline stages configuration updated:', validatedConfig.config)

    return NextResponse.json({
      success: true,
      data: validatedConfig.config,
      message: 'Pipeline stages configuration updated successfully'
    })

  } catch (error) {
    console.error('Failed to update pipeline stages:', error)
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to update pipeline stages configuration' 
      },
      { status: 500 }
    )
  }
}

/**
 * POST /api/settings/pipeline-stages/reset
 * 
 * Resets pipeline stages to default configuration
 */
export async function POST(request: NextRequest) {
  try {
    const url = new URL(request.url)
    if (!url.pathname.endsWith('/reset')) {
      return NextResponse.json({ error: 'Not found' }, { status: 404 })
    }

    // Reset to default configuration
    const defaultConfig: PipelineStagesConfig = {
      summarization: DEFAULT_STAGE_CONFIG.summarization,
      fewshot: DEFAULT_STAGE_CONFIG.fewshot,
      scraping: DEFAULT_STAGE_CONFIG.scraping,
      classification: DEFAULT_STAGE_CONFIG.classification,
      response: DEFAULT_STAGE_CONFIG.response,
      moderation: DEFAULT_STAGE_CONFIG.moderation,
      pipeline_type: 'hybrid'
    }

    await prisma.setting.upsert({
      where: { key: SETTINGS_KEY },
      update: { 
        value: defaultConfig,
        updatedAt: new Date()
      },
      create: { 
        key: SETTINGS_KEY, 
        value: defaultConfig,
        updatedAt: new Date()
      }
    })

    console.log('Pipeline stages configuration reset to defaults')

    return NextResponse.json({
      success: true,
      data: defaultConfig,
      message: 'Pipeline stages configuration reset to defaults'
    })

  } catch (error) {
    console.error('Failed to reset pipeline stages:', error)
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to reset pipeline stages configuration' 
      },
      { status: 500 }
    )
  }
}

/**
 * Validate stage configuration
 */
function validateStageConfig(config: any): { isValid: boolean; config?: PipelineStagesConfig; errors?: string[] } {
  const errors: string[] = []

  if (!config || typeof config !== 'object') {
    errors.push('Configuration must be an object')
    return { isValid: false, errors }
  }

  // Required stages
  const requiredStages = ['summarization', 'classification', 'scraping']
  
  for (const stage of requiredStages) {
    if (!config[stage] || !config[stage].enabled) {
      errors.push(`${stage} is required and cannot be disabled`)
    }
  }

  // Validate dependencies
  if (config.response?.enabled && !config.classification?.enabled) {
    errors.push('Response generation requires classification to be enabled')
  }

  if (config.moderation?.enabled && !config.response?.enabled) {
    errors.push('Moderation requires response generation to be enabled')
  }

  // Validate pipeline type
  if (config.pipeline_type && !['claude', 'legacy', 'hybrid'].includes(config.pipeline_type)) {
    errors.push('Pipeline type must be one of: claude, legacy, hybrid')
  }

  // If using Claude pipeline, fewshot should be disabled
  if (config.pipeline_type === 'claude' && config.fewshot?.enabled) {
    errors.push('Few-shot generation is not needed with Claude pipeline')
  }

  if (errors.length > 0) {
    return { isValid: false, errors }
  }

  // Build validated configuration
  const validatedConfig: PipelineStagesConfig = {
    summarization: {
      enabled: true, // Always required
      required: true,
      model: config.summarization?.model
    },
    fewshot: {
      enabled: config.fewshot?.enabled || false,
      required: false,
      model: config.fewshot?.model
    },
    scraping: {
      enabled: true, // Always required
      required: true,
      model: config.scraping?.model
    },
    classification: {
      enabled: true, // Always required
      required: true,
      model: config.classification?.model
    },
    response: {
      enabled: config.response?.enabled !== false, // Default to true
      required: false,
      model: config.response?.model
    },
    moderation: {
      enabled: config.moderation?.enabled || false,
      required: false,
      model: config.moderation?.model
    },
    pipeline_type: config.pipeline_type || 'hybrid'
  }

  return { isValid: true, config: validatedConfig }
}