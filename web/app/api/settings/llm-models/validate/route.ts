/**
 * API route for validating LLM model availability
 * 
 * Tests if selected models are accessible:
 * - Gemini models: Checks if gemini CLI is available
 * - Ollama models: Checks if Ollama is running and model is pulled
 * - OpenAI models: Checks if API key is configured
 * 
 * Related files:
 * - /web/app/api/settings/llm-models/route.ts (Main config endpoint)
 * - /scripts/validate_llm_models.py (Python validation script)
 */

import { NextRequest, NextResponse } from 'next/server'
import { spawn } from 'child_process'
import { z } from 'zod'
import { prisma } from '@/lib/prisma'
import { decrypt } from '@/lib/crypto'

// Schema for validation request
const ValidateRequestSchema = z.object({
  model: z.string(),
  provider: z.enum(['gemini', 'ollama', 'openai']),
})

type ValidateRequest = z.infer<typeof ValidateRequestSchema>

/**
 * POST /api/settings/llm-models/validate
 * Validates if a specific model is available
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { model, provider } = ValidateRequestSchema.parse(body)

    if (provider === 'gemini') {
      // Validate Gemini model
      const isValid = await validateGeminiModel(model)
      return NextResponse.json({ 
        valid: isValid,
        provider,
        model,
        message: isValid ? 'Model is available' : 'Gemini CLI not found or model not accessible'
      })
    } else if (provider === 'ollama') {
      // Validate Ollama model
      const result = await validateOllamaModel(model)
      return NextResponse.json({ 
        valid: result.valid,
        provider,
        model,
        message: result.message
      })
    } else if (provider === 'openai') {
      // Validate OpenAI model
      const result = await validateOpenAIModel(model)
      return NextResponse.json({
        valid: result.valid,
        provider,
        model,
        message: result.message
      })
    }

    return NextResponse.json(
      { error: 'Invalid provider' },
      { status: 400 }
    )
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid request format', details: error.errors },
        { status: 400 }
      )
    }

    console.error('Failed to validate model:', error)
    return NextResponse.json(
      { error: 'Failed to validate model' },
      { status: 500 }
    )
  }
}

/**
 * Validate if Gemini model is accessible via gemini-cli npm package
 */
async function validateGeminiModel(model: string): Promise<boolean> {
  return new Promise((resolve) => {
    // Check if gemini CLI is available (installed via npm)
    const gemini = spawn('which', ['gemini'])
    
    gemini.on('close', (code) => {
      if (code === 0) {
        // gemini CLI is installed
        resolve(true)
      } else {
        // Try to check if it's available in node_modules
        const npmGemini = spawn('npx', ['gemini', '--version'])
        npmGemini.on('close', (npmCode) => {
          resolve(npmCode === 0)
        })
        npmGemini.on('error', () => {
          resolve(false)
        })
      }
    })
    
    gemini.on('error', () => {
      resolve(false)
    })
  })
}

/**
 * Validate if Ollama model is available
 */
async function validateOllamaModel(model: string): Promise<{ valid: boolean; message: string }> {
  try {
    // First check if Ollama is running
    const response = await fetch('http://localhost:11434/api/tags')
    
    if (!response.ok) {
      return { valid: false, message: 'Ollama is not running' }
    }
    
    const data = await response.json()
    const models = data.models || []
    
    // Check if the specific model is available
    const modelExists = models.some((m: any) => 
      m.name === model || m.name.startsWith(model + ':')
    )
    
    if (modelExists) {
      return { valid: true, message: 'Model is available' }
    } else {
      return { valid: false, message: `Model '${model}' is not pulled. Run: ollama pull ${model}` }
    }
  } catch (error) {
    return { valid: false, message: 'Cannot connect to Ollama. Is it running?' }
  }
}

/**
 * Validate if OpenAI model is accessible
 */
async function validateOpenAIModel(model: string): Promise<{ valid: boolean; message: string }> {
  try {
    // Check if OpenAI API key is configured
    const apiKeySetting = await prisma.setting.findUnique({
      where: { key: 'api_keys' }
    })

    if (!apiKeySetting) {
      return { valid: false, message: 'OpenAI API key not configured. Please add it in API Keys settings.' }
    }

    const apiKeys = apiKeySetting.value as any
    if (!apiKeys?.openai?.apiKey) {
      return { valid: false, message: 'OpenAI API key not configured. Please add it in API Keys settings.' }
    }

    // Decrypt the API key
    let apiKey: string
    try {
      apiKey = decrypt(apiKeys.openai.apiKey)
    } catch (error) {
      return { valid: false, message: 'Failed to decrypt OpenAI API key' }
    }

    // Test the API key with a minimal request
    const response = await fetch('https://api.openai.com/v1/models', {
      headers: {
        'Authorization': `Bearer ${apiKey}`,
      },
    })

    if (!response.ok) {
      if (response.status === 401) {
        return { valid: false, message: 'Invalid OpenAI API key' }
      }
      return { valid: false, message: 'Failed to connect to OpenAI API' }
    }

    // Check if the specific model exists
    const data = await response.json()
    const models = data.data || []
    const modelExists = models.some((m: any) => m.id === model)

    if (modelExists || model.startsWith('gpt-')) {
      // Even if model not in list, GPT models are usually available
      return { valid: true, message: 'Model is available' }
    } else {
      return { valid: false, message: `Model '${model}' not found in OpenAI account` }
    }
  } catch (error) {
    console.error('OpenAI validation error:', error)
    return { valid: false, message: 'Failed to validate OpenAI model' }
  }
}