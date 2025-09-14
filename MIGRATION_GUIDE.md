# WDFWatch Server Migration Guide

## Prerequisites on New Server
```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y git python3 python3-pip nodejs npm docker docker-compose postgresql-client

# Clone the WDFWatch repository
cd ~
git clone https://github.com/yourusername/WDFWatch.git
cd WDFWatch
```

## Step 1: Extract Migration Package
```bash
# Copy the migration package to new server (from your local machine)
scp wdfwatch_migration_20250913.tar.gz user@newserver:~/WDFWatch/

# On the new server, extract the package
cd ~/WDFWatch
tar -xzf wdfwatch_migration_20250913.tar.gz
```

## Step 2: Place Database Files
```bash
# Create required directories if they don't exist
mkdir -p artefacts
mkdir -p claude-pipeline
mkdir -p web

# Move SQLite database (required for tracking published tweets)
mv migration_package/tweets.db artefacts/tweets.db

# Move cache files (required for API optimization and learning)
mv migration_package/tweet_cache.json artefacts/tweet_cache.json
mv migration_package/learned_keyword_weights.json artefacts/learned_keyword_weights.json
mv migration_package/quota_state.json artefacts/quota_state.json
mv migration_package/search_boundaries.json artefacts/search_boundaries.json
mv migration_package/response_cache.json claude-pipeline/cache/response_cache.json
```

## Step 3: Place Episode Data
```bash
# Move all episode data (contains all processing history)
mv migration_package/episodes claude-pipeline/episodes

# Verify episode data is in place
ls -la claude-pipeline/episodes/
# Should show: episode_1_-_larry_sharpe, episode_10_calexit, etc.
```

## Step 4: Place Transcript Files
```bash
# Move current working transcripts (active episode data)
mv migration_package/transcripts/* transcripts/

# Verify transcript files
ls -la transcripts/
# Should show: latest.txt, summary.md, keywords.json, tweets.json, etc.
```

## Step 5: Configure Environment Variables
```bash
# Move web configuration (contains encrypted API keys)
mv migration_package/web_data/.env.local web/.env.local

# Create main .env file (copy from .env.example and modify)
cp .env.example .env

# Edit .env file with your settings
nano .env
```

### Required .env Configuration:
```bash
# Core Settings
WDF_MOCK_MODE=false  # Set to true if no Twitter API access
WDF_WEB_MODE=true    # Enable web UI integration
WDF_NO_AUTO_SCRAPE=true  # Disable automatic Twitter scraping

# Ollama Configuration
WDF_OLLAMA_HOST=http://localhost:11434

# Redis Configuration
WDF_REDIS_URL=redis://localhost:6379/0

# Model Configuration
WDF_LLM_MODELS__GEMINI=gemini-2.5-pro
WDF_LLM_MODELS__GEMMA=gemma3n:e4b
WDF_LLM_MODELS__DEEPSEEK=deepseek-r1:latest

# Database URLs (if using Web UI)
DATABASE_URL=postgresql://wdf:password@localhost:5432/wdfwatch
WEB_API_KEY=generate-a-secure-key-here
ENCRYPTION_KEY=your-32-byte-encryption-key-here
```

## Step 6: PostgreSQL Database (if using Web UI)
```bash
# OPTION A: If you have a PostgreSQL dump from old server
# First, dump from old server:
# pg_dump -h localhost -U wdf -d wdfwatch > wdfwatch_backup.sql
# scp wdfwatch_backup.sql user@newserver:~/

# On new server, restore the database
sudo -u postgres createdb wdfwatch
sudo -u postgres createuser wdf
sudo -u postgres psql -c "ALTER USER wdf WITH PASSWORD 'your-password';"
psql -h localhost -U wdf -d wdfwatch < wdfwatch_backup.sql

# OPTION B: If starting fresh with Web UI
cd web
npm install
npx prisma db push  # Create schema
npx prisma db seed  # Load initial data
```

## Step 7: Install Dependencies
```bash
# Install Python dependencies
cd ~/WDFWatch
pip install poetry
poetry install

# Install Node dependencies for web UI
cd web
npm install

# Install Docker services (Ollama + Redis)
docker-compose up -d
```

## Step 8: Download Ollama Models
```bash
# Pull required models
docker exec -it wdfwatch-ollama ollama pull gemma3n:e4b
docker exec -it wdfwatch-ollama ollama pull deepseek-r1:latest
```

## Step 9: Verify Installation
```bash
# Check that all cache files are in place
ls -la artefacts/*.json artefacts/*.db
# Should show: tweets.db, tweet_cache.json, learned_keyword_weights.json, etc.

# Check episodes are available
ls -la claude-pipeline/episodes/ | head -5
# Should show episode directories

# Test pipeline in mock mode (no Twitter API needed)
WDF_MOCK_MODE=true python main.py --non-interactive

# Check web UI (if configured)
cd web
npm run dev
# Access at http://localhost:3000
```

## Step 10: Load API Keys (if available)
```bash
# If you have Twitter API credentials, add them via Web UI:
# 1. Navigate to http://localhost:3000/settings/api-keys
# 2. Enter your Twitter/X API credentials
# 3. Save configuration

# Or load from environment
eval $(python scripts/load_api_keys.py)
```

## What You're Getting

### Critical Data Files:
- **tweets.db**: SQLite database tracking which tweets have been responded to (prevents duplicates)
- **tweet_cache.json**: 3.2MB of cached real tweets for testing without API calls
- **episodes/**: Complete history of all processed episodes with transcripts, classifications, and responses
- **learned_keyword_weights.json**: ML optimization data for keyword effectiveness
- **quota_state.json**: API rate limit tracking to prevent exceeding limits
- **search_boundaries.json**: Optimized search parameters for each keyword
- **response_cache.json**: Claude API response cache to avoid repeated calls

### Why Each File Matters:
- Without `tweets.db`: System might reply to same tweets multiple times
- Without `tweet_cache.json`: Need live Twitter API for any testing
- Without `episodes/`: Lose all historical processing and responses
- Without cache files: Lose all ML optimizations and API cost savings

## Troubleshooting

### Issue: "No module named 'wdf'"
```bash
poetry install
poetry shell
```

### Issue: "Cannot connect to Ollama"
```bash
docker-compose up -d
docker ps  # Verify ollama container is running
```

### Issue: "Database connection failed"
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection
psql -h localhost -U wdf -d wdfwatch -c "SELECT 1;"
```

### Issue: "Missing episodes or transcripts"
```bash
# Verify files were copied correctly
find claude-pipeline/episodes -name "*.json" | wc -l
# Should show many JSON files

ls -la transcripts/*.json
# Should show keywords.json, tweets.json, etc.
```

## Final Verification Checklist
- [ ] tweets.db is in artefacts/
- [ ] tweet_cache.json is in artefacts/
- [ ] All episode directories are in claude-pipeline/episodes/
- [ ] Transcript files are in transcripts/
- [ ] .env.local is in web/ (if using Web UI)
- [ ] .env is configured with correct settings
- [ ] Dependencies installed (poetry install, npm install)
- [ ] Docker services running (ollama, redis)
- [ ] Models downloaded (gemma3n:e4b, deepseek-r1:latest)
- [ ] Pipeline runs successfully in mock mode

## Support Commands
```bash
# View current cache statistics
python scripts/manage_tweet_cache.py stats

# Test classification on cached tweets
python tweet_classifier.py --input-file transcripts/tweets.json --summary-file transcripts/summary.md

# Run full pipeline with cached data
WDF_MOCK_MODE=true python main.py

# Monitor logs
tail -f logs/pipeline.log
```