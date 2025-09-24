#!/usr/bin/env node

/**
 * Script to add WDFWATCH API keys to the database
 *
 * This script encrypts and stores the WDFWATCH API credentials
 * in the same format as the settings page would.
 *
 * Usage: node scripts/add_wdfwatch_keys.js
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

const IV_LENGTH = 16

/**
 * Encrypt a string value (same as web/lib/crypto.ts)
 */
function encrypt(text) {
  const iv = crypto.randomBytes(IV_LENGTH)
  const cipher = crypto.createCipheriv(
    'aes-256-cbc',
    ENCRYPTION_KEY,
    iv
  )

  let encrypted = cipher.update(text, 'utf8', 'hex')
  encrypted += cipher.final('hex')

  // Return iv and encrypted data separated by colon
  return iv.toString('hex') + ':' + encrypted
}

async function addApiKeys() {
  try {
    console.log('Adding WDFWATCH API keys to database...')

    // API keys from .env file
    const apiKeys = {
      twitter: {
        apiKey: 'oTUkJX3gVRS41KXT7FkBBJbY1',
        apiSecret: 'JElqalwa0z3BkjaoLRF9nxrh3mwzvu90uz61TRQQfyJdI46KPg',
        bearerToken: 'AAAAAAAAAAAAAAAAAAAAAIEp3gEAAAAAxuH3urDWSc0ukGOAeZD4Pr%2FhsAo%3DXXkWT2gW9qhUSjPRqo5KbrRl5G8H9TIGJ9OM2hzRE3gsxr9jK2',
        accessToken: 'TkRWZWI4MWFKeEhuTy01YVUzcTdoZTR4NW5WNjJ0cjdIT1JhUXhBbFJ0SVMwOjE3NTgwNzI3NzYyNzU6MToxOmF0OjE',
        accessTokenSecret: '' // We don't have the access token secret for OAuth2.0
      },
      gemini: {
        // Add if you have a Gemini API key
      },
      openai: {
        // Add if you have an OpenAI API key
      }
    }

    // Note: For OAuth 2.0, we're using:
    // - CLIENT_ID as the apiKey (c0R5SUZvbFFYUkxmcFBkbEUza1A6MTpjaQ)
    // - CLIENT_SECRET as the apiSecret (UqMTOa9PDHWJ8f3hQE2dYlTfqyfXppfeVCrJKLltJGVch3tbpy)
    // But the .env shows API_KEY and API_KEY_SECRET which are likely the OAuth 1.0a credentials
    // Let's use both sets for maximum compatibility

    // Alternative: Use CLIENT_ID and CLIENT_SECRET (OAuth 2.0 App credentials)
    const oauth2Keys = {
      twitter: {
        apiKey: 'c0R5SUZvbFFYUkxmcFBkbEUza1A6MTpjaQ',  // CLIENT_ID
        apiSecret: 'UqMTOa9PDHWJ8f3hQE2dYlTfqyfXppfeVCrJKLltJGVch3tbpy',  // CLIENT_SECRET
        bearerToken: 'AAAAAAAAAAAAAAAAAAAAAIEp3gEAAAAAxuH3urDWSc0ukGOAeZD4Pr%2FhsAo%3DXXkWT2gW9qhUSjPRqo5KbrRl5G8H9TIGJ9OM2hzRE3gsxr9jK2',
        accessToken: 'TkRWZWI4MWFKeEhuTy01YVUzcTdoZTR4NW5WNjJ0cjdIT1JhUXhBbFJ0SVMwOjE3NTgwNzI3NzYyNzU6MToxOmF0OjE',
        accessTokenSecret: ''
      }
    }

    // Use OAuth 1.0a credentials (API_KEY/API_KEY_SECRET) as primary
    const encryptedConfig = {}

    // Encrypt each service's keys
    for (const [service, keys] of Object.entries(apiKeys)) {
      if (Object.keys(keys).length > 0) {
        encryptedConfig[service] = {}

        for (const [key, value] of Object.entries(keys)) {
          if (value && value !== '') {
            encryptedConfig[service][key] = encrypt(value)
            console.log(`  Encrypted ${service}.${key}`)
          }
        }
      }
    }

    // Upsert settings in database
    const setting = await prisma.setting.upsert({
      where: { key: 'api_keys' },
      update: {
        value: encryptedConfig,
        updatedAt: new Date(),
        updatedBy: 'system',
      },
      create: {
        key: 'api_keys',
        value: encryptedConfig,
        description: 'External API keys configuration (added via script)',
        updatedBy: 'system',
      },
    })

    console.log('✅ Successfully added API keys to database')
    console.log('Settings ID:', setting.id)
    console.log('Services configured:', Object.keys(encryptedConfig))

    // Create audit log entry
    await prisma.auditLog.create({
      data: {
        action: 'UPDATE_API_KEYS',
        resourceType: 'setting',
        resourceId: null,
        metadata: {
          services: Object.keys(encryptedConfig),
          method: 'script',
          timestamp: new Date().toISOString(),
        },
        userId: 'system',
      },
    })

    console.log('✅ Audit log entry created')

  } catch (error) {
    console.error('❌ Failed to add API keys:', error)
    process.exit(1)
  } finally {
    await prisma.$disconnect()
  }
}

// Ask for confirmation
console.log('This script will add WDFWATCH API keys to the database.')
console.log('The keys will be encrypted using the same method as the settings page.')
console.log('\nKeys to be added:')
console.log('  - Twitter API Key (OAuth 1.0a)')
console.log('  - Twitter API Secret')
console.log('  - Twitter Bearer Token')
console.log('  - WDFWATCH Access Token (OAuth 2.0)')
console.log('\nPress Ctrl+C to cancel, or wait 3 seconds to continue...\n')

setTimeout(() => {
  addApiKeys()
}, 3000)