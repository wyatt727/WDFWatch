#!/usr/bin/env node

/**
 * Test script to verify API key loading from the trigger route
 *
 * This simulates what happens when the scraping trigger route
 * loads API keys from the database.
 */

const { PrismaClient } = require('@prisma/client')
const crypto = require('crypto')
const path = require('path')
const dotenv = require('dotenv')

// Load environment variables from .env file
dotenv.config({ path: path.join(__dirname, '../../.env') })

// Initialize Prisma client
const prisma = new PrismaClient()

// Encryption key from environment or default for dev
const ENCRYPTION_KEY = process.env.ENCRYPTION_KEY ||
  crypto.createHash('sha256').update('dev-key-change-in-production').digest()

/**
 * Decrypt a string value (same as web/lib/crypto.ts)
 */
function decrypt(text) {
  const parts = text.split(':')
  if (parts.length !== 2) {
    throw new Error('Invalid encrypted format')
  }

  const iv = Buffer.from(parts[0], 'hex')
  const encryptedText = parts[1]

  const decipher = crypto.createDecipheriv(
    'aes-256-cbc',
    ENCRYPTION_KEY,
    iv
  )

  let decrypted = decipher.update(encryptedText, 'hex', 'utf8')
  decrypted += decipher.final('utf8')

  return decrypted
}

// Helper to load API keys (same as in trigger route)
async function loadApiKeys() {
  try {
    const setting = await prisma.setting.findUnique({
      where: { key: 'api_keys' }
    })

    if (!setting || !setting.value) {
      return {}
    }

    const encryptedConfig = setting.value
    const apiEnvVars = {}

    // Decrypt Twitter API keys
    if (encryptedConfig.twitter) {
      try {
        if (encryptedConfig.twitter.apiKey) {
          apiEnvVars.API_KEY = decrypt(encryptedConfig.twitter.apiKey)
          apiEnvVars.CLIENT_ID = apiEnvVars.API_KEY // Alias for compatibility
        }
        if (encryptedConfig.twitter.apiSecret) {
          apiEnvVars.API_KEY_SECRET = decrypt(encryptedConfig.twitter.apiSecret)
          apiEnvVars.CLIENT_SECRET = apiEnvVars.API_KEY_SECRET // Alias
        }
        if (encryptedConfig.twitter.bearerToken) {
          apiEnvVars.BEARER_TOKEN = decrypt(encryptedConfig.twitter.bearerToken)
        }
        if (encryptedConfig.twitter.accessToken) {
          apiEnvVars.WDFWATCH_ACCESS_TOKEN = decrypt(encryptedConfig.twitter.accessToken)
        }
        if (encryptedConfig.twitter.accessTokenSecret) {
          apiEnvVars.WDFWATCH_ACCESS_TOKEN_SECRET = decrypt(encryptedConfig.twitter.accessTokenSecret)
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

async function testApiKeyLoading() {
  console.log('Testing API key loading (as scraping trigger would)...\n')

  const apiKeys = await loadApiKeys()

  console.log('Loaded environment variables:')
  console.log('=' .repeat(50))

  const keyCount = Object.keys(apiKeys).length
  console.log(`✅ Found ${keyCount} API key environment variables\n`)

  for (const [key, value] of Object.entries(apiKeys)) {
    // Mask the value for display
    const masked = value.length > 12
      ? `${value.substring(0, 6)}...${value.substring(value.length - 4)}`
      : '****'

    console.log(`  ${key}: ${masked} (${value.length} chars)`)
  }

  console.log('\nThese environment variables would be passed to the Python subprocess.')
  console.log('The Python scraping script would receive them via os.getenv()')

  // Test what the subprocess would see
  console.log('\n\nSimulating Python subprocess environment:')
  console.log('=' .repeat(50))

  const processEnv = {
    ...process.env,
    ...apiKeys,
    WDF_WEB_MODE: 'true',
    WDF_MOCK_MODE: 'false',
    WDF_NO_AUTO_SCRAPE: 'false'
  }

  console.log('Python would see:')
  console.log(`  os.getenv("API_KEY"): ${processEnv.API_KEY ? '✅ Available' : '❌ Not found'}`)
  console.log(`  os.getenv("CLIENT_ID"): ${processEnv.CLIENT_ID ? '✅ Available' : '❌ Not found'}`)
  console.log(`  os.getenv("BEARER_TOKEN"): ${processEnv.BEARER_TOKEN ? '✅ Available' : '❌ Not found'}`)
  console.log(`  os.getenv("WDFWATCH_ACCESS_TOKEN"): ${processEnv.WDFWATCH_ACCESS_TOKEN ? '✅ Available' : '❌ Not found'}`)

  await prisma.$disconnect()
}

testApiKeyLoading()