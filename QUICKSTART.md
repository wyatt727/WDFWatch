# Quick Start Guide

## Environment Setup (Simplified)

WDFWatch needs environment variables. Here's the **simple way**:

### 1. Create your main environment file

```bash
cp .env.example .env
```

### 2. Edit `.env` with your credentials

Open `.env` and fill in:
- Twitter API keys (from https://developer.twitter.com/en/portal/dashboard)
- Twitter account credentials
- Database URLs (if using custom setup)
- Other settings

### 3. Generate OAuth tokens (if needed)

```bash
python scripts/generate_wdfwatch_tokens.py
```

This will add `WDFWATCH_ACCESS_TOKEN` to your `.env` file (or create `.env.wdfwatch` if you prefer).

### 4. Setup web app (if using web UI)

```bash
cd web
cp env.example .env.local
# Edit .env.local with database credentials
cd ..
```

## That's It!

You only need **2 files**:
- ✅ `.env` - All your credentials (main file)
- ✅ `web/.env.local` - Next.js web app config (if using web UI)

## Optional: Extra Safety

If you want extra safety by separating WDFwatch tokens:

```bash
cp .env.wdfwatch.example .env.wdfwatch
# Put WDFWATCH tokens in .env.wdfwatch, everything else in .env
```

But this is **completely optional** - everything works fine with just `.env`!

## Production

For production deployments:

```bash
cp .env.production.example .env.production
# Edit .env.production with production values
```

## Need More Help?

See `ENV_SETUP.md` for detailed documentation on all environment files.

