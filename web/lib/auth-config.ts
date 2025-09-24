/**
 * Authentication configuration
 * Stores password hash directly to avoid env var parsing issues with $ characters
 */

// Password: Queueone1
// Generated with: bcrypt.hashSync("Queueone1", 10)
export const AUTH_CONFIG = {
  // Hardcoded hash for "Queueone1"
  ADMIN_PASSWORD_HASH: "$2b$10$sVkKtnbHK/tSaUHUfCLQY.vRue4WVeCkgBczYDfdBS9pAkckU3VkK",
  
  // For production, you can set a different password by:
  // 1. Generate hash: node -e "console.log(require('bcryptjs').hashSync('YourPassword', 10))"
  // 2. Replace the hash above
  // 3. Deploy to VPS
} as const;

// Alternative: Store base64 encoded in env var to avoid $ issues
// const encoded = Buffer.from(hash).toString('base64')
// const decoded = Buffer.from(process.env.ADMIN_PASSWORD_HASH_B64 || '', 'base64').toString()