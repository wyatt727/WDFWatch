# Database Setup Guide

## Fix for DATABASE_URL Environment Variable Error

To fix the Prisma database connection errors, you need to create a `.env.local` file in the web directory with the following content:

```bash
# Database - matching docker-compose configuration
DATABASE_URL=postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5432/wdfwatch

# Redis  
REDIS_URL=redis://localhost:6379/0

# Authentication
NEXTAUTH_SECRET=dev-secret-change-in-production
NEXTAUTH_URL=http://localhost:3000

# Feature flags
NEXT_PUBLIC_ENABLE_REALTIME=true
NEXT_PUBLIC_ENABLE_ANALYTICS=true

# Integration with Python backend
PYTHON_API_URL=http://localhost:8000
WDF_DUAL_MODE=true

# Encryption key for API keys (32 bytes)
ENCRYPTION_KEY=development-encryption-key-32byt

# Internal API key for Python<->Web communication
WEB_API_KEY=development-internal-api-key
```

## Setup Steps:

1. **Copy the environment file:**
   ```bash
   cd /Users/pentester/Tools/WDFWatch/web
   cp env.local.txt .env.local
   ```

2. **Start the database (if not already running):**
   ```bash
   cd /Users/pentester/Tools/WDFWatch
   docker-compose up postgres -d
   ```

3. **Initialize Prisma client:**
   ```bash
   cd web
   npx prisma generate
   ```

4. **Restart the development server:**
   ```bash
   npm run dev
   ```

This should resolve all the DATABASE_URL errors in your build output.