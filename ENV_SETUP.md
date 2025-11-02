# Environment Variables Setup Guide

This document explains all the environment variable files used in WDFWatch and when/how they are loaded.

## Quick Start (Simplified)

**For most users, you only need ONE file:**

```bash
cp .env.example .env
# Edit .env with your real credentials - that's it!
```

The `.env.wdfwatch` file is **optional** - you can put everything in `.env` if you prefer simplicity.

## Overview

WDFWatch supports multiple `.env` files for different purposes:

1. **`.env`** - Main development environment file (contains everything)
2. **`.env.production`** - Production-specific variables (required for Docker)
3. **`.env.wdfwatch`** - **OPTIONAL** - Separate file for WDFwatch OAuth tokens (extra safety)
4. **`web/.env.local`** - Next.js web application variables (required by Next.js)

### Recommended Setup (Simple)

**Just use `.env`** - Put all your credentials in one file:
```bash
cp .env.example .env
# Edit .env with all your credentials
```

### Advanced Setup (Safer)

If you want extra safety to prevent accidentally posting to the wrong Twitter account, you can use a separate `.env.wdfwatch` file:
```bash
cp .env.example .env
cp .env.wdfwatch.example .env.wdfwatch
# Put WDFwatch tokens in .env.wdfwatch, everything else in .env
```

**Note**: The code automatically checks for `.env.wdfwatch` first, then falls back to `.env` if it doesn't exist. So `.env.wdfwatch` is purely optional.

### `.env.production` (Production)

**Location**: Project root  
**When Used**: Production deployments via Docker Compose  
**Status**: ❌ **NOT COMMITTED** (contains production secrets)

This file contains production-specific values:
- Production database credentials
- Production security keys (NEXTAUTH_SECRET, ENCRYPTION_KEY)
- Production URLs
- Production API keys

**Setup**:
```bash
cp .env.production.example .env.production
# Then edit .env.production with your production values
```

**How It's Loaded**:
- Docker Compose automatically loads `.env.production` when using `docker-compose.prod.yml`
- Referenced by `scripts/deploy-production.sh`
- Environment variables are injected into containers at runtime

### `.env.wdfwatch` (WDFwatch OAuth Tokens) - **OPTIONAL**

**Location**: Project root  
**When Used**: Only if you want extra safety when posting tweets  
**Status**: ❌ **NOT COMMITTED** (contains OAuth tokens)  
**⚠️ OPTIONAL**: You can put everything in `.env` instead!

This file is **completely optional**. It exists only if you want to separate WDFwatch OAuth tokens for extra safety.

**What it contains**:
- WDFWATCH_ACCESS_TOKEN
- WDFWATCH_REFRESH_TOKEN
- Token metadata (expires_in, scope, etc.)

**Why use a separate file?** (Optional)
- Extra safety: Prevents accidentally mixing tokens for @WDFwatch vs @WDF_Show
- Can be regenerated independently via `generate_wdfwatch_tokens.py`
- Some scripts prefer it for clarity

**But you don't need it!** Just put `WDFWATCH_ACCESS_TOKEN` and `WDFWATCH_REFRESH_TOKEN` in your `.env` file and everything will work fine.

**Setup** (only if you want this extra safety):
```bash
cp .env.wdfwatch.example .env.wdfwatch
# Then run: python scripts/generate_wdfwatch_tokens.py
# OR manually fill in OAuth tokens
```

**How It's Loaded**:
- Loaded AFTER `.env` with `override=True`, so it takes precedence
- If `.env.wdfwatch` doesn't exist, the code just uses `.env` instead
- Used by `token_manager.py` for automatic token refresh

### `web/.env.local` (Next.js Web App)

**Location**: `web/` directory  
**When Used**: Next.js development and production builds  
**Status**: ❌ **NOT COMMITTED** (contains database credentials)

Next.js-specific environment variables:
- Database connection string
- NextAuth configuration
- Feature flags
- API endpoints

**Setup**:
```bash
cd web
cp env.example .env.local
# OR use the template: cp env.local.txt .env.local
# Then edit .env.local with your values
```

**How It's Loaded**:
- Next.js automatically loads `.env.local` during development and build
- Uses Next.js environment variable loading order
- See `web/DATABASE_SETUP.md` for more details

## Environment Variable Loading Order

### Python Scripts

1. **Base `.env`** (if exists) - loads all variables
2. **`.env.wdfwatch`** (if exists) - **OPTIONAL** - overrides WDFWATCH_* variables from `.env`
   - If `.env.wdfwatch` doesn't exist, scripts just use `.env` instead
3. **`web/.env.local`** (if exists) - loads web-specific vars (some scripts only)

### Docker Compose (Production)

1. **`.env.production`** - loaded by docker-compose automatically
2. Environment variables passed to containers
3. Container-specific overrides in `docker-compose.prod.yml`

### Next.js Web App

1. **`.env.local`** - local development (highest priority)
2. **`.env.development`** - development defaults
3. **`.env.production`** - production defaults
4. System environment variables (override all)

## Security Best Practices

### ✅ DO:

- ✅ Use `.example` files as templates (they ARE committed)
- ✅ Keep actual `.env` files in `.gitignore`
- ✅ Use separate files for different environments
- ✅ Rotate secrets regularly
- ✅ Use strong, unique passwords for production

### ❌ DON'T:

- ❌ Commit actual `.env` files with real credentials
- ❌ Share `.env` files via insecure channels
- ❌ Use production credentials in development
- ❌ Store secrets in code or version control

## Example Files (Committed to Git)

These template files ARE committed and serve as documentation:

- ✅ `.env.example` - Development template
- ✅ `.env.production.example` - Production template
- ✅ `.env.wdfwatch.example` - WDFwatch tokens template
- ✅ `web/env.example` - Next.js template

## Quick Setup Commands

### Initial Development Setup (Simple - Recommended)

```bash
# 1. Copy main development env file
cp .env.example .env
# Edit .env with ALL your credentials (including WDFWATCH tokens)

# 2. Generate WDFwatch OAuth tokens (if you don't have them)
python scripts/generate_wdfwatch_tokens.py
# This will add tokens to .env (or create .env.wdfwatch if you prefer)

# 3. Setup web app env file
cd web
cp env.example .env.local
# Edit .env.local with your database credentials
cd ..
```

**That's it!** You only need `.env` and `web/.env.local`.

### Production Setup

```bash
# 1. Copy production template
cp .env.production.example .env.production
# Edit .env.production with production values

# 2. Verify production file exists
./scripts/deploy-production.sh status
```

## Troubleshooting

### "Environment variable not found" errors

1. **Python scripts**: Check that `.env` exists in project root
2. **Next.js**: Check that `web/.env.local` exists
3. **Docker**: Verify `.env.production` exists for production

### Token refresh issues

- Check that `.env.wdfwatch` exists and contains valid tokens
- Verify `CLIENT_ID` and `CLIENT_SECRET` are in `.env`
- Run `python scripts/refresh_wdfwatch_tokens.py` to refresh manually

### Wrong account posting tweets

- Verify `.env.wdfwatch` contains tokens for @WDFwatch, not @WDF_Show
- Check that `safe_twitter_post.py` loads `.env.wdfwatch` correctly
- Run `python scripts/generate_wdfwatch_tokens.py` to regenerate

## Related Documentation

- `scripts/generate_wdfwatch_tokens.py` - OAuth token generation
- `src/wdf/token_manager.py` - Token refresh logic
- `scripts/safe_twitter_post.py` - Safe posting implementation
- `web/DATABASE_SETUP.md` - Web app database setup
- `scripts/deploy-production.sh` - Production deployment script

