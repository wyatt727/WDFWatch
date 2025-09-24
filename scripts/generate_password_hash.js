#!/usr/bin/env node

/**
 * Generate a bcrypt hash for the admin password
 * Usage: node generate_password_hash.js <password>
 */

const bcrypt = require('bcryptjs');

const password = process.argv[2];

if (!password) {
  console.error('Usage: node generate_password_hash.js <password>');
  process.exit(1);
}

const hash = bcrypt.hashSync(password, 10);

console.log('\n=== WDFWatch Admin Password Configuration ===\n');
console.log('Add this to your .env file:');
console.log(`ADMIN_PASSWORD_HASH="${hash}"`);
console.log('\nAnd these for NextAuth:');
console.log(`NEXTAUTH_SECRET="${require('crypto').randomBytes(32).toString('base64')}"`);
console.log(`NEXTAUTH_URL="http://localhost:3000" # Change for production`);
console.log('\n===========================================\n');