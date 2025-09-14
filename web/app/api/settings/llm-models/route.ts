/**
 * API routes for managing LLM model configuration
 * 
 * Allows users to configure which LLM models are used for each pipeline task:
 * - Summarization (Gemini)
 * - Few-shot generation (Gemini)
 * - Classification (Ollama/Gemma)
 * - Response generation (Ollama/DeepSeek)
 * - Moderation (Claude/GPT-4)
 * 
 * Related files:
 * - /web/app/(dashboard)/settings/llm-models/page.tsx (UI component)
 * - /scripts/load_llm_config.py (Python integration)
 * - /src/wdf/tasks/*.py (Task implementations)
 */

import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { getCurrentUserId } from '@/lib/auth'
import { z } from 'zod'
import { AVAILABLE_MODELS, DEFAULT_MODEL_CONFIG } from '@/lib/llm-models'
import { exec } from 'child_process'
import { promisify } from 'util'

const execAsync = promisify(exec)

// Schema for LLM models configuration
const LLMModelsSchema = z.object({
  summarization: z.string(),
  fewshot: z.string(),
  classification: z.string(),
  response: z.string(),
  moderation: z.string(),
})

export type LLMModelsConfig = z.infer<typeof LLMModelsSchema>

const SETTINGS_KEY = 'llm_models'

// Default model configuration
const DEFAULT_CONFIG: LLMModelsConfig = {
  summarization: 'gemini-2.5-pro',
  fewshot: 'gemini-2.5-pro',
  classification: 'gemma3n:e4b',
  response: 'deepseek-r1:latest',
  moderation: 'claude',
}

/**
 * GET /api/settings/llm-models
 * Returns current LLM model configuration with dynamically fetched Ollama models
 */
export async function GET() {
  try {
    // Fetch LLM models from database
    const setting = await prisma.setting.findUnique({
      where: { key: SETTINGS_KEY }
    })

    const config = setting ? setting.value as LLMModelsConfig : DEFAULT_CONFIG

    // Fetch available models with dynamic Ollama models
    const available = await getAvailableModels()

    return NextResponse.json({
      config,
      available,
    })
  } catch (error) {
    console.error('Failed to fetch LLM models:', error)
    return NextResponse.json(
      { error: 'Failed to fetch LLM model configuration' },
      { status: 500 }
    )
  }
}

/**
 * Get available models with dynamic Ollama model fetching
 */
async function getAvailableModels() {
  // Define type for model options
  type ModelOption = {
    value: string
    label: string
    provider: string
    description: string
  }

  // Start with static models for Gemini and OpenAI
  const models: {
    summarization: ModelOption[]
    fewshot: ModelOption[]
    classification: ModelOption[]
    response: ModelOption[]
  } = {
    summarization: [...AVAILABLE_MODELS.summarization],
    fewshot: [...AVAILABLE_MODELS.fewshot],
    classification: AVAILABLE_MODELS.classification.filter(m => m.provider !== 'ollama') as ModelOption[],
    response: AVAILABLE_MODELS.response.filter(m => m.provider !== 'ollama') as ModelOption[],
  }

  try {
    // Fetch Ollama models dynamically
    const ollamaModels = await fetchOllamaModels()
    
    // Add Ollama models to classification and response tasks
    models.classification.push(...ollamaModels)
    models.response.push(...ollamaModels)
  } catch (error) {
    console.error('Failed to fetch Ollama models:', error)
    // Fall back to hardcoded Ollama models if fetch fails
    models.classification.push(...AVAILABLE_MODELS.classification.filter(m => m.provider === 'ollama'))
    models.response.push(...AVAILABLE_MODELS.response.filter(m => m.provider === 'ollama'))
  }

  return models
}

/**
 * Fetch available Ollama models using ollama list command
 */
async function fetchOllamaModels() {
  try {
    const { stdout } = await execAsync('ollama list')
    const lines = stdout.trim().split('\n')
    
    // Skip header line
    const modelLines = lines.slice(1).filter(line => line.trim())
    
    const models = modelLines.map(line => {
      // Parse ollama list output format: NAME ID SIZE MODIFIED
      const parts = line.split(/\s+/)
      const name = parts[0]
      const size = parts[2] || 'Unknown'
      
      // Extract base model name and tag
      const [baseName, tag] = name.includes(':') ? name.split(':') : [name, 'latest']
      
      // Create a nice label
      const label = baseName
        .split('-')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ') + (tag !== 'latest' ? ` (${tag})` : '')
      
      // Generate description based on model characteristics
      let description = `${size} model`
      if (baseName.includes('coder') || baseName.includes('code')) {
        description = `${size} coding model`
      } else if (baseName.includes('70b') || baseName.includes('34b')) {
        description = `Large ${size} model with high accuracy`
      } else if (baseName.includes('7b') || baseName.includes('8b')) {
        description = `Efficient ${size} model`
      } else if (baseName.includes('mixtral')) {
        description = `${size} MoE model with good performance`
      } else if (baseName.includes('deepseek')) {
        description = `${size} reasoning model`
      }
      
      return {
        value: name,
        label,
        provider: 'ollama',
        description,
      }
    })
    
    return models
  } catch (error) {
    throw new Error('Failed to execute ollama list command')
  }
}

/**
 * PUT /api/settings/llm-models
 * Updates LLM model configuration
 */
export async function PUT(request: NextRequest) {
  try {
    const body = await request.json()
    const validatedConfig = LLMModelsSchema.parse(body)

    // Validate that selected models are available for their tasks
    const validationErrors: string[] = []
    
    for (const [task, model] of Object.entries(validatedConfig)) {
      const availableModels = AVAILABLE_MODELS[task as keyof typeof AVAILABLE_MODELS]
      const modelInfo = availableModels.find(m => m.value === model)
      
      if (!modelInfo) {
        return NextResponse.json(
          { error: `Invalid model '${model}' for task '${task}'` },
          { status: 400 }
        )
      }
      
      // Validate model availability (optional - only if validate query param is true)
      if (request.nextUrl.searchParams.get('validate') === 'true') {
        const validateResponse = await fetch(new URL('/api/settings/llm-models/validate', request.url), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ model, provider: modelInfo.provider })
        })
        
        if (validateResponse.ok) {
          const result = await validateResponse.json()
          if (!result.valid) {
            validationErrors.push(`${task}: ${result.message}`)
          }
        }
      }
    }
    
    // If validation was requested and there are errors, return them
    if (validationErrors.length > 0) {
      return NextResponse.json(
        { 
          error: 'Some models are not available',
          validationErrors,
          warning: 'Configuration saved but some models may not work properly'
        },
        { status: 400 }
      )
    }

    // Upsert settings in database
    const setting = await prisma.setting.upsert({
      where: { key: SETTINGS_KEY },
      update: {
        value: validatedConfig,
        updatedAt: new Date(),
        updatedBy: 'system', // TODO: Get from auth context
      },
      create: {
        key: SETTINGS_KEY,
        value: validatedConfig,
        description: 'LLM model configuration for pipeline tasks',
        updatedBy: 'system',
      },
    })

    // Log audit event
    await prisma.auditLog.create({
      data: {
        action: 'UPDATE_LLM_MODELS',
        resourceType: 'setting',
        resourceId: null,
        oldValue: setting.value || {},
        newValue: validatedConfig,
        metadata: {
          timestamp: new Date().toISOString(),
        },
        userId: await getCurrentUserId(),
      },
    })

    return NextResponse.json({ 
      success: true,
      config: validatedConfig,
      message: 'LLM model configuration updated successfully'
    })
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid configuration format', details: error.errors },
        { status: 400 }
      )
    }

    console.error('Failed to update LLM models:', error)
    return NextResponse.json(
      { error: 'Failed to update LLM model configuration' },
      { status: 500 }
    )
  }
}

/**
 * POST /api/settings/llm-models/reset
 * Resets LLM model configuration to defaults
 */
export async function POST(request: NextRequest) {
  if (request.nextUrl.pathname.endsWith('/reset')) {
    try {
      // Update settings with default configuration
      await prisma.setting.upsert({
        where: { key: SETTINGS_KEY },
        update: {
          value: DEFAULT_CONFIG,
          updatedAt: new Date(),
          updatedBy: 'system',
        },
        create: {
          key: SETTINGS_KEY,
          value: DEFAULT_CONFIG,
          description: 'LLM model configuration for pipeline tasks',
          updatedBy: 'system',
        },
      })

      // Log audit event
      await prisma.auditLog.create({
        data: {
          action: 'RESET_LLM_MODELS',
          resourceType: 'setting',
          resourceId: null,
          newValue: DEFAULT_CONFIG,
          metadata: {
            timestamp: new Date().toISOString(),
          },
          userId: await getCurrentUserId(),
        },
      })

      return NextResponse.json({ 
        success: true,
        config: DEFAULT_CONFIG,
        message: 'LLM model configuration reset to defaults'
      })
    } catch (error) {
      console.error('Failed to reset LLM models:', error)
      return NextResponse.json(
        { error: 'Failed to reset LLM model configuration' },
        { status: 500 }
      )
    }
  }

  return NextResponse.json(
    { error: 'Invalid endpoint' },
    { status: 404 }
  )
}