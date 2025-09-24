#!/usr/bin/env node

/**
 * Script to verify API keys stored in the database
 *
 * This script retrieves and decrypts the API keys to verify
 * they were stored correctly.
 *
 * Usage: node scripts/verify_api_keys.js
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

/**
 * Mask an API key for display
 */
function maskApiKey(apiKey) {
  if (!apiKey || apiKey.length < 12) {
    return '****'
  }

  const start = apiKey.substring(0, 6)
  const end = apiKey.substring(apiKey.length - 4)
  return `${start}...${end}`
}

async function verifyApiKeys() {
  try {
    console.log('Verifying API keys in database...\n')

    // Fetch API keys from database
    const setting = await prisma.setting.findUnique({
      where: { key: 'api_keys' }
    })

    if (!setting) {
      console.log('❌ No API keys found in database')
      return
    }

    console.log('✅ Found API keys setting in database')
    console.log('   Created:', setting.createdAt)
    console.log('   Updated:', setting.updatedAt)
    console.log('   Updated by:', setting.updatedBy)
    console.log('\n')

    const encryptedConfig = setting.value

    // Decrypt and display each service's keys
    for (const [service, keys] of Object.entries(encryptedConfig)) {
      console.log(`${service.toUpperCase()} API Keys:`)
      console.log('=' .repeat(50))

      for (const [key, value] of Object.entries(keys)) {
        if (value && typeof value === 'string') {
          try {
            const decrypted = decrypt(value)
            const masked = maskApiKey(decrypted)
            console.log(`  ${key}: ${masked} (${decrypted.length} chars)`)

            // Show full value for verification (comment out in production)
            if (key === 'apiKey' || key === 'bearerToken') {
              console.log(`    Full: ${decrypted.substring(0, 25)}...`)
            }
          } catch (error) {
            console.log(`  ${key}: ❌ Failed to decrypt`)
          }
        }
      }
      console.log()
    }

    // Test that we can fetch them via the internal API endpoint logic
    console.log('Testing decryption for Python pipeline:')
    console.log('=' .repeat(50))

    if (encryptedConfig.twitter) {
      const twitter = encryptedConfig.twitter
      const decryptedKeys = {}

      if (twitter.apiKey) {
        decryptedKeys.API_KEY = decrypt(twitter.apiKey)
        decryptedKeys.CLIENT_ID = decryptedKeys.API_KEY
        console.log('  API_KEY/CLIENT_ID: ✅ Ready')
      }

      if (twitter.apiSecret) {
        decryptedKeys.API_KEY_SECRET = decrypt(twitter.apiSecret)
        decryptedKeys.CLIENT_SECRET = decryptedKeys.API_KEY_SECRET
        console.log('  API_KEY_SECRET/CLIENT_SECRET: ✅ Ready')
      }

      if (twitter.bearerToken) {
        decryptedKeys.BEARER_TOKEN = decrypt(twitter.bearerToken)
        console.log('  BEARER_TOKEN: ✅ Ready')
      }

      if (twitter.accessToken) {
        decryptedKeys.WDFWATCH_ACCESS_TOKEN = decrypt(twitter.accessToken)
        console.log('  WDFWATCH_ACCESS_TOKEN: ✅ Ready')
      }

      console.log('\n✅ All keys can be decrypted successfully!')
      console.log('   Keys are ready to be used by the Python pipeline.')
    }

  } catch (error) {
    console.error('❌ Failed to verify API keys:', error)
    process.exit(1)
  } finally {
    await prisma.$disconnect()
  }
}

verifyApiKeys()