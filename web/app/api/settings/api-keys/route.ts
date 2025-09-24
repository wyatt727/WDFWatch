/**
 * API routes for managing external API keys
 * 
 * Handles secure storage and retrieval of API keys for:
 * - Twitter/X API
 * - Gemini API
 * - Other external services
 * 
 * Related files:
 * - /web/app/(dashboard)/settings/api-keys/page.tsx (UI component)
 * - /web/lib/crypto.ts (Encryption utilities)
 * - /src/wdf/web_bridge.py (Python integration)
 */

import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { encrypt, decrypt, maskApiKey } from '@/lib/crypto'
import { getCurrentUserId } from '@/lib/auth'
import { z } from 'zod'

// Schema for API keys configuration
const ApiKeysSchema = z.object({
  twitter: z.object({
    apiKey: z.string().optional(),
    apiSecret: z.string().optional(),
    bearerToken: z.string().optional(),
    accessToken: z.string().optional(),
    accessTokenSecret: z.string().optional(),
  }).optional(),
  gemini: z.object({
    apiKey: z.string().optional(),
  }).optional(),
  openai: z.object({
    apiKey: z.string().optional(),
  }).optional(),
})

export type ApiKeysConfig = z.infer<typeof ApiKeysSchema>

const SETTINGS_KEY = 'api_keys'

/**
 * GET /api/settings/api-keys
 * Returns masked API keys for display
 */
export async function GET() {
  try {
    // Fetch API keys from database
    const setting = await prisma.setting.findUnique({
      where: { key: SETTINGS_KEY }
    })

    if (!setting) {
      // Return empty configuration if none exist
      return NextResponse.json({
        twitter: {},
        gemini: {},
        openai: {},
      })
    }

    // Decrypt and mask API keys for display
    const encryptedConfig = setting.value as any
    const maskedConfig: any = {}

    // Process each service
    for (const service of ['twitter', 'gemini', 'openai']) {
      if (encryptedConfig[service]) {
        maskedConfig[service] = {}
        
        for (const [key, value] of Object.entries(encryptedConfig[service])) {
          if (value && typeof value === 'string') {
            try {
              const decrypted = decrypt(value)
              maskedConfig[service][key] = maskApiKey(decrypted)
              // Add a flag to indicate the key is set
              maskedConfig[service][`${key}Set`] = true
            } catch (error) {
              // If decryption fails, the value might not be encrypted
              maskedConfig[service][key] = maskApiKey(value as string)
              maskedConfig[service][`${key}Set`] = true
            }
          }
        }
      } else {
        maskedConfig[service] = {}
      }
    }

    return NextResponse.json(maskedConfig)
  } catch (error) {
    console.error('Failed to fetch API keys:', error)
    return NextResponse.json(
      { error: 'Failed to fetch API keys' },
      { status: 500 }
    )
  }
}

/**
 * PUT /api/settings/api-keys
 * Updates API keys (only updates provided fields)
 */
export async function PUT(request: NextRequest) {
  try {
    const body = await request.json()
    const validatedKeys = ApiKeysSchema.parse(body)

    // Fetch existing settings
    const existingSetting = await prisma.setting.findUnique({
      where: { key: SETTINGS_KEY }
    })

    let existingConfig: any = {}
    if (existingSetting) {
      existingConfig = existingSetting.value as any
    }

    // Encrypt new API keys and merge with existing
    const encryptedConfig: any = { ...existingConfig }

    for (const service of ['twitter', 'gemini', 'openai'] as const) {
      if (validatedKeys[service]) {
        if (!encryptedConfig[service]) {
          encryptedConfig[service] = {}
        }

        for (const [key, value] of Object.entries(validatedKeys[service])) {
          if (value && value !== '' && !value.includes('...')) {
            // Only update if a new value is provided (not masked)
            encryptedConfig[service][key] = encrypt(value)
          }
          // If value is empty string, remove the key
          else if (value === '') {
            delete encryptedConfig[service][key]
          }
          // Otherwise keep existing value (for masked values)
        }
      }
    }

    // Upsert settings in database
    const setting = await prisma.setting.upsert({
      where: { key: SETTINGS_KEY },
      update: {
        value: encryptedConfig,
        updatedAt: new Date(),
        updatedBy: 'system', // TODO: Get from auth context
      },
      create: {
        key: SETTINGS_KEY,
        value: encryptedConfig,
        description: 'External API keys configuration',
        updatedBy: 'system',
      },
    })

    // Log audit event (without sensitive data)
    await prisma.auditLog.create({
      data: {
        action: 'UPDATE_API_KEYS',
        resourceType: 'setting',
        resourceId: null,
        metadata: {
          services: Object.keys(validatedKeys),
          timestamp: new Date().toISOString(),
        },
        userId: await getCurrentUserId(),
      },
    })

    // Return success without exposing sensitive data
    return NextResponse.json({ 
      success: true,
      message: 'API keys updated successfully'
    })
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid API keys format', details: error.errors },
        { status: 400 }
      )
    }

    console.error('Failed to update API keys:', error)
    return NextResponse.json(
      { error: 'Failed to update API keys' },
      { status: 500 }
    )
  }
}

/**
 * DELETE /api/settings/api-keys
 * Removes all API keys
 */
export async function DELETE() {
  try {
    await prisma.setting.delete({
      where: { key: SETTINGS_KEY }
    })

    // Log audit event
    await prisma.auditLog.create({
      data: {
        action: 'DELETE_API_KEYS',
        resourceType: 'setting',
        resourceId: null,
        metadata: {
          timestamp: new Date().toISOString(),
        },
        userId: await getCurrentUserId(),
      },
    })

    return NextResponse.json({ 
      success: true,
      message: 'API keys deleted successfully'
    })
  } catch (error) {
    console.error('Failed to delete API keys:', error)
    return NextResponse.json(
      { error: 'Failed to delete API keys' },
      { status: 500 }
    )
  }
}