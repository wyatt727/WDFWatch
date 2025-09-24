#!/usr/bin/env node

/**
 * Test script to verify API keys are available for Twitter posting
 * Simulates what happens when the approve route tries to post to Twitter
 */

const { PrismaClient } = require('@prisma/client')
const crypto = require('crypto')
const path = require('path')
const dotenv = require('dotenv')
const { exec } = require('child_process')
const { promisify } = require('util')

const execAsync = promisify(exec)

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

/**
 * Load API keys from database with .env fallback (same as in approve route)
 */
async function loadApiKeys() {
  const apiEnvVars = {}

  try {
    // First, try to load from database
    const setting = await prisma.setting.findUnique({
      where: { key: 'api_keys' }
    })

    if (setting && setting.value) {
      const encryptedConfig = setting.value

      // Decrypt Twitter API keys
      if (encryptedConfig.twitter) {
        try {
          if (encryptedConfig.twitter.apiKey) {
            apiEnvVars.API_KEY = decrypt(encryptedConfig.twitter.apiKey)
            apiEnvVars.CLIENT_ID = apiEnvVars.API_KEY
            apiEnvVars.TWITTER_API_KEY = apiEnvVars.API_KEY
          }
          if (encryptedConfig.twitter.apiSecret) {
            apiEnvVars.API_KEY_SECRET = decrypt(encryptedConfig.twitter.apiSecret)
            apiEnvVars.CLIENT_SECRET = apiEnvVars.API_KEY_SECRET
            apiEnvVars.TWITTER_API_KEY_SECRET = apiEnvVars.API_KEY_SECRET
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
          console.error('Failed to decrypt Twitter API keys from database:', error)
        }
      }
    }
  } catch (error) {
    console.error('Failed to load API keys from database:', error)
  }

  // Fallback to environment variables if not found in database
  if (!apiEnvVars.API_KEY) {
    const envApiKey = process.env.API_KEY || process.env.CLIENT_ID || process.env.TWITTER_API_KEY
    if (envApiKey) {
      apiEnvVars.API_KEY = envApiKey
      apiEnvVars.CLIENT_ID = envApiKey
      apiEnvVars.TWITTER_API_KEY = envApiKey
    }
  }

  if (!apiEnvVars.API_KEY_SECRET) {
    const envApiSecret = process.env.API_KEY_SECRET || process.env.CLIENT_SECRET || process.env.TWITTER_API_KEY_SECRET
    if (envApiSecret) {
      apiEnvVars.API_KEY_SECRET = envApiSecret
      apiEnvVars.CLIENT_SECRET = envApiSecret
      apiEnvVars.TWITTER_API_KEY_SECRET = envApiSecret
    }
  }

  if (!apiEnvVars.BEARER_TOKEN && process.env.BEARER_TOKEN) {
    apiEnvVars.BEARER_TOKEN = process.env.BEARER_TOKEN
  }

  if (!apiEnvVars.WDFWATCH_ACCESS_TOKEN && process.env.WDFWATCH_ACCESS_TOKEN) {
    apiEnvVars.WDFWATCH_ACCESS_TOKEN = process.env.WDFWATCH_ACCESS_TOKEN
  }

  if (!apiEnvVars.WDFWATCH_ACCESS_TOKEN_SECRET && process.env.WDFWATCH_ACCESS_TOKEN_SECRET) {
    apiEnvVars.WDFWATCH_ACCESS_TOKEN_SECRET = process.env.WDFWATCH_ACCESS_TOKEN_SECRET
  }

  console.log('API Keys loaded:', {
    hasApiKey: !!apiEnvVars.API_KEY,
    hasApiSecret: !!apiEnvVars.API_KEY_SECRET,
    hasBearerToken: !!apiEnvVars.BEARER_TOKEN,
    hasAccessToken: !!apiEnvVars.WDFWATCH_ACCESS_TOKEN,
    source: apiEnvVars.API_KEY ? 'database/env' : 'none'
  })

  return apiEnvVars
}

async function testPostingEnvironment() {
  console.log('Testing API Key Loading for Twitter Posting')
  console.log('=' .repeat(60))

  // Step 1: Load API keys (as approve route does)
  console.log('\n1. Loading API keys from database/env...')
  const apiKeys = await loadApiKeys()

  // Step 2: Display what we have
  console.log('\n2. Available environment variables:')
  console.log('   From Database:')
  const dbKeys = Object.keys(apiKeys).filter(k => apiKeys[k])
  if (dbKeys.length > 0) {
    dbKeys.forEach(key => {
      const value = apiKeys[key]
      const masked = value.length > 12
        ? `${value.substring(0, 6)}...${value.substring(value.length - 4)}`
        : '****'
      console.log(`     ${key}: ${masked}`)
    })
  } else {
    console.log('     (none)')
  }

  console.log('\n   From .env:')
  const envKeys = ['API_KEY', 'CLIENT_ID', 'API_KEY_SECRET', 'CLIENT_SECRET', 'BEARER_TOKEN', 'WDFWATCH_ACCESS_TOKEN']
  envKeys.forEach(key => {
    const value = process.env[key]
    if (value) {
      const masked = value.length > 12
        ? `${value.substring(0, 6)}...${value.substring(value.length - 4)}`
        : '****'
      console.log(`     ${key}: ${masked}`)
    }
  })

  // Step 3: Test Python script environment
  console.log('\n3. Testing Python script environment...')
  const pythonPath = process.env.PYTHON_PATH || 'python3'

  // Create a simple test script that checks environment
  const testCommand = `${pythonPath} -c "
import os
print('Python sees:')
print(f'  API_KEY: {\\"Present\\" if os.getenv(\\"API_KEY\\") else \\"Missing\\"}')
print(f'  CLIENT_ID: {\\"Present\\" if os.getenv(\\"CLIENT_ID\\") else \\"Missing\\"}')
print(f'  API_KEY_SECRET: {\\"Present\\" if os.getenv(\\"API_KEY_SECRET\\") else \\"Missing\\"}')
print(f'  BEARER_TOKEN: {\\"Present\\" if os.getenv(\\"BEARER_TOKEN\\") else \\"Missing\\"}')
print(f'  WDFWATCH_ACCESS_TOKEN: {\\"Present\\" if os.getenv(\\"WDFWATCH_ACCESS_TOKEN\\") else \\"Missing\\"}')
"`

  // Clean environment to avoid conflicts (as approve route does)
  const cleanEnv = { ...process.env }
  delete cleanEnv.DEBUG
  delete cleanEnv.ACCESS_TOKEN
  delete cleanEnv.ACCESS_TOKEN_SECRET
  delete cleanEnv.TWITTER_TOKEN
  delete cleanEnv.TWITTER_TOKEN_SECRET
  delete cleanEnv.WDFSHOW_ACCESS_TOKEN
  delete cleanEnv.WDFSHOW_ACCESS_TOKEN_SECRET

  try {
    const { stdout, stderr } = await execAsync(testCommand, {
      env: {
        ...cleanEnv,
        ...apiKeys,  // Include loaded API keys
        WDFWATCH_MODE: 'true',
        WDF_DEBUG: 'false',
        WDF_WEB_MODE: 'true'
      }
    })

    console.log(stdout)

    if (stderr) {
      console.log('Stderr:', stderr)
    }
  } catch (error) {
    console.error('Failed to execute test command:', error)
  }

  // Step 4: Verify critical requirements
  console.log('\n4. Critical Requirements Check:')
  console.log('=' .repeat(60))

  const requirements = [
    { key: 'API_KEY', name: 'Twitter API Key (OAuth 1.0a)', present: !!apiKeys.API_KEY },
    { key: 'API_KEY_SECRET', name: 'Twitter API Secret', present: !!apiKeys.API_KEY_SECRET },
    { key: 'BEARER_TOKEN', name: 'Twitter Bearer Token', present: !!apiKeys.BEARER_TOKEN },
    { key: 'WDFWATCH_ACCESS_TOKEN', name: 'WDFwatch Access Token', present: !!apiKeys.WDFWATCH_ACCESS_TOKEN }
  ]

  let allPresent = true
  requirements.forEach(req => {
    console.log(`   ${req.present ? '✅' : '❌'} ${req.name}: ${req.present ? 'Present' : 'MISSING'}`)
    if (!req.present) allPresent = false
  })

  console.log('\n5. Overall Status:')
  console.log('=' .repeat(60))
  if (allPresent) {
    console.log('✅ All required API keys are available for Twitter posting!')
    console.log('   The approve & post functionality should work correctly.')
  } else {
    console.log('❌ Some API keys are missing!')
    console.log('   Twitter posting will fail without these keys.')
    console.log('\n   To fix:')
    console.log('   1. Add keys via Web UI at /settings/api-keys')
    console.log('   2. Or ensure they are in your .env file')
    console.log('   3. Or run: node scripts/add_wdfwatch_keys.js')
  }

  await prisma.$disconnect()
}

testPostingEnvironment().catch(console.error)