# Script Organization

Scripts in WDFWatch are organized into two main directories:

## `/scripts/` - Web API Scripts

Scripts in this directory are called by Next.js API routes or web components.

**Keep in `/scripts/`:**
- Scripts called by web API routes (`web/app/api/`)
- Scripts used by web components
- Scripts that require database access via Prisma

## `/tools/` - Operational Scripts

Scripts in this directory are standalone operational tools, not called by the web UI.

### `/tools/ops/` - Operational Tools
- `estimate_api_cost.py` - Cost estimation
- `safe_twitter_reply.py` - Safe Twitter operations
- `manage_tweet_cache.py` - Cache management
- `post_alive.py` - Health checks

### `/tools/migrations/` - Migration Scripts
- `migrate_data.py` - Data migration utilities
- `validate_migration.py` - Migration validation

## Migration Plan

Scripts to move from `/scripts/` to `/tools/`:

1. **Operational scripts** (`/tools/ops/`):
   - `estimate_api_cost.py`
   - `safe_twitter_post.py`
   - `safe_twitter_reply.py`
   - `manage_tweet_cache.py`
   - `post_alive.py`
   - `get_quota_stats.py`
   - `validate_llm_models.py`

2. **Migration scripts** (`/tools/migrations/`):
   - `migrate_data.py`
   - `test_migration.py`
   - `validate_migration.py`

3. **Keep in `/scripts/`** (called by web API):
   - `claude_classifier.py` (if called by API)
   - `claude_summarizer.py` (if called by API)
   - `load_api_keys.py` (if called by API)
   - `load_llm_config.py` (if called by API)
   - `load_prompts.py` (if called by API)
   - `load_scraping_settings.py` (if called by API)
   - `generate_wdfwatch_tokens.py` (if called by API)
   - `refresh_wdfwatch_tokens.py` (if called by API)
   - `setup_oauth2.py` (if called by API)
   - `deploy-production.sh` (deployment script)

## Usage

After reorganization, update any references:

```bash
# Old path
python scripts/estimate_api_cost.py

# New path
python tools/ops/estimate_api_cost.py
```

Update Makefile targets and documentation accordingly.

