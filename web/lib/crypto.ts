/**
 * Cryptography utilities for secure storage of sensitive data
 * 
 * Uses Node.js crypto module to encrypt/decrypt API keys and other secrets
 * before storing them in the database.
 */

import crypto from 'crypto'

// Get encryption key from environment variable or generate a default one (for dev only)
const ENCRYPTION_KEY = process.env.ENCRYPTION_KEY || 
  crypto.createHash('sha256').update('dev-key-change-in-production').digest()

// Initialization vector length
const IV_LENGTH = 16

/**
 * Encrypt a string value
 * @param text The plain text to encrypt
 * @returns Encrypted string in format: iv:encryptedData (hex encoded)
 */
export function encrypt(text: string): string {
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

/**
 * Decrypt a string value
 * @param text The encrypted string in format: iv:encryptedData
 * @returns Decrypted plain text
 */
export function decrypt(text: string): string {
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
 * Mask an API key for display purposes
 * Shows only the first 4 and last 4 characters
 * @param apiKey The API key to mask
 * @returns Masked string like "abcd...wxyz"
 */
export function maskApiKey(apiKey: string): string {
  if (!apiKey || apiKey.length < 12) {
    return '****'
  }
  
  const start = apiKey.substring(0, 4)
  const end = apiKey.substring(apiKey.length - 4)
  return `${start}...${end}`
}