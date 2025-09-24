/**
 * Internal API route for Python pipeline to fetch decrypted API keys
 * 
 * This endpoint is protected by API key and should only be accessible
 * from the Python pipeline running on the same host.
 * 
 * Related files:
 * - /web/scripts/web_bridge.py (Python integration)
 * - /src/wdf/settings.py (Python settings)
 */

import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { decrypt } from '@/lib/crypto'

export const dynamic = 'force-dynamic';

const SETTINGS_KEY = 'api_keys'

/**
 * GET /api/internal/api-keys
 * Returns decrypted API keys for Python pipeline
 */
export async function GET(request: NextRequest) {
  try {
    // Verify internal API key
    const apiKey = request.headers.get('X-API-Key')
    const expectedKey = process.env.WEB_API_KEY || 'development'
    
    if (apiKey !== expectedKey) {
      return NextResponse.json(
        { error: 'Unauthorized' },
        { status: 401 }
      )
    }

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

    // Decrypt API keys
    const encryptedConfig = setting.value as any
    const decryptedConfig: any = {}

    // Process each service
    for (const service of ['twitter', 'gemini', 'openai']) {
      if (encryptedConfig[service]) {
        decryptedConfig[service] = {}
        
        for (const [key, value] of Object.entries(encryptedConfig[service])) {
          if (value && typeof value === 'string') {
            try {
              decryptedConfig[service][key] = decrypt(value)
            } catch (error) {
              // If decryption fails, the value might not be encrypted (legacy data)
              console.warn(`Failed to decrypt ${service}.${key}, using raw value`)
              decryptedConfig[service][key] = value
            }
          }
        }
      } else {
        decryptedConfig[service] = {}
      }
    }

    return NextResponse.json(decryptedConfig)
  } catch (error) {
    console.error('Failed to fetch API keys:', error)
    return NextResponse.json(
      { error: 'Failed to fetch API keys' },
      { status: 500 }
    )
  }
}