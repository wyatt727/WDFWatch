# System Context

Project: WDFWatch Twitter Bot
A comprehensive AI-powered social media engagement pipeline for the "War, Divorce, or Federalism" podcast. 
Automates the discovery, classification, and response generation for relevant tweets using Claude AI.

**Architecture**: Service-oriented web application with FastAPI backend and Next.js frontend.
- **Web UI**: Next.js 14 with TypeScript, React, Prisma (PostgreSQL)
- **Backend API**: FastAPI (Python) with Redis/RQ job queue
- **Pipeline**: Unified Claude pipeline (`claude-pipeline/`) - single source of truth
- **Legacy Support**: Fully migrated to FastAPI-first workflow (Next.js SSE removed)

**Current State**: Production web application using FastAPI backend for all pipeline operations.

## Agent System Context

This project uses a dual-workflow agent system for bug-fixing and feature-building (see `AGENTS.md` for details).

**Project-Specific Agent Patterns:**
- **Python/FastAPI Backend**: `backend/api/` - Routes, services, workers, models
- **Next.js Frontend**: `web/` - Components, pages, hooks, API client
- **Claude Pipeline**: `claude-pipeline/` - Stages, core components, episode management
- **Pipeline Stages**: summarize → classify → respond → moderate
- **Testing**: pytest for Python, npm test for TypeScript
- **Linting**: ruff for Python, eslint for TypeScript

**When agents work on this codebase:**
- Use Python examples (not Kotlin/Java)
- Reference FastAPI route patterns (not mobile app patterns)
- Reference Next.js/React patterns (not Android/iOS)
- Follow WDFWatch file structure (`claude-pipeline/`, `backend/api/`, `web/`)
- Consider pipeline stages and episode-based workflows

# Development Commands

## Development Commands
```bash
make bootstrap           # Install all dependencies (Poetry, npm)
make dev-run            # Run full pipeline in development mode (legacy)
make debug              # Run pipeline with verbose debug logging
```

## FastAPI Backend (Primary)
```bash
cd backend/api
uvicorn app.main:app --reload --port 8001  # Start FastAPI backend
python -m app.workers.worker               # Start RQ worker
```

## Web UI (Next.js)
```bash
cd web
npm run dev                                # Start Next.js dev server (port 3000)
```

## Claude Pipeline (Recommended)
```bash
python claude-pipeline/orchestrator.py \
  --episode-id episode_123 \
  --stages summarize,classify,respond

python claude-pipeline/single_tweet.py \
  "Tweet text here" \
  --episode-id episode_123 \
  --video-url "https://youtube.com/..."
```

## Database Operations
```bash
cd web
npx prisma migrate dev  # Run database migrations
npx prisma studio       # Open database GUI
```

## Docker Operations
```bash
docker-compose up -d    # Start all services (PostgreSQL, Redis, FastAPI, Web UI)
make docker-build       # Build container stack
```

## Testing & Maintenance
```bash
make test              # Run pytest test suite
poetry run pytest -n auto    # Parallel test execution
```

## Configuration Management
```bash
python scripts/load_api_keys.py      # Load API keys from database to env vars
python scripts/load_llm_config.py    # Load LLM model config from database
python scripts/load_scoring_config.py # Load scoring thresholds from database
```

# Code Style Guidelines

- **Python**: PEP 8 with 100-character line length (enforced by Ruff)
- **TypeScript**: ESLint + Prettier with strict TypeScript settings
- **Type Hints**: Required for all Python functions (enforced by mypy)
- **Documentation**: Docstrings in Google format for public functions
- **Error Handling**: Custom exception classes with structured logging
- **File Headers**: ⚠️ **CRITICAL** - All new files MUST include a header comment/docstring at the top explaining:
  - What the file does
  - Its purpose in the system
  - Key components/functions it provides
  - Any important usage notes or dependencies

**Example File Header (Python):**
```python
"""
Tweet Classification Pipeline Stage

This module implements the classification stage of the WDFWatch pipeline, scoring
tweets for relevance to podcast episodes. It uses Claude AI to analyze tweet content
against episode context and generates relevance scores (0.0-1.0).

Key Components:
- classify_tweet(): Single tweet classification
- batch_classify(): Batch processing for multiple tweets
- load_episode_context(): Loads episode-specific context for classification

Dependencies:
- claude-pipeline/core/unified_interface.py for Claude AI integration
- Episode context files from claude-pipeline/episodes/{id}/EPISODE_CONTEXT.md

Usage:
    from claude_pipeline.stages.classify import classify_tweet
    score = classify_tweet(tweet_text, episode_id="episode_123")
"""
```

**Example File Header (TypeScript):**
```typescript
/**
 * FastAPI API Client for WDFWatch Backend
 * 
 * Provides a typed, Promise-based client for interacting with the FastAPI backend.
 * Handles authentication, error handling, and request/response typing.
 * 
 * Key Features:
 * - Typed API methods matching backend endpoints
 * - Automatic error handling with custom APIError class
 * - SSE event stream support for real-time updates
 * - Centralized base URL configuration
 * 
 * Usage:
 *   import { apiClient } from '@/lib/api-client'
 *   const response = await apiClient.runPipeline('episode_123', { stages: ['classify'] })
 */
```

## File Organization
- **Pipeline Code**: `claude-pipeline/` - Single source of truth for all pipeline logic
- **Backend API**: `backend/api/` - FastAPI service with routes, services, workers
- **Web UI**: `web/` - Next.js application with components, hooks, API routes
- **Transitional Tasks**: `src/wdf/` - Bridge modules pending migration
- **Scripts**: `scripts/` - Operational scripts for database/config management

## Naming Conventions
- **Python**: Snake_case for functions/variables, PascalCase for classes
- **TypeScript**: camelCase for variables/functions, PascalCase for components/types
- **Constants**: ALL_CAPS for environment variables and constants
- **API Routes**: kebab-case for endpoints, camelCase for request/response models

## Code Quality Tools
- **Python**: Ruff (linting), mypy (type checking), pytest (testing)
- **TypeScript**: ESLint + Prettier, TypeScript strict mode
- **Database**: Prisma (migrations, type-safe queries)
- **Pre-commit**: Automated checks for both Python and TypeScript


# File Map

## Core Architecture Files
- `ARCHITECTURE.md` - ✅ Complete architecture documentation
- `README.md` - Project overview and setup
- `ENV_SETUP.md` - Environment variable configuration guide
- `QUICKSTART.md` - Quick start guide

## Backend API (FastAPI)
```
backend/api/
├── app/
│   ├── main.py            # FastAPI application entrypoint
│   ├── config.py          # Configuration management
│   ├── routes/            # API route handlers
│   │   ├── episodes.py   # Episode pipeline operations
│   │   ├── tweets.py     # Tweet generation
│   │   ├── queue.py      # Job queue management
│   │   ├── events.py     # SSE event streaming
│   │   └── settings.py   # Settings management
│   ├── services/          # Business logic services
│   │   ├── pipeline.py   # Pipeline service wrapper
│   │   ├── episodes_repo.py # Episode filesystem operations
│   │   └── events.py     # Redis pub/sub events
│   ├── workers/          # Background job workers
│   │   ├── worker.py     # RQ worker entrypoint
│   │   └── jobs.py       # Job definitions (run_pipeline_job, generate_single_tweet_job)
│   └── models/           # Pydantic models
└── requirements.txt
```

## Web UI (Next.js)
```
web/
├── app/                   # Next.js app router
│   ├── (dashboard)/      # Dashboard pages
│   └── api/              # API routes (legacy + proxy)
├── components/           # React components
├── lib/                  # Utilities
│   └── api-client.ts     # ✅ Typed FastAPI client
├── hooks/                # React hooks
│   └── use-fastapi-sse.ts # ✅ FastAPI SSE hook
└── prisma/               # Database schema
```

## Claude Pipeline (Single Source of Truth)
```
claude-pipeline/
├── orchestrator.py        # Main pipeline orchestrator
├── single_tweet.py        # Single tweet response generator
├── core/                  # Core pipeline components
│   ├── unified_interface.py # Claude interface
│   ├── episode_manager.py  # Episode directory management
│   ├── batch_processor.py  # Batch processing utilities
│   └── models/
│       └── claude_adapter.py # Claude CLI adapter
├── stages/                # Pipeline stage implementations
│   ├── summarize.py     # Summarization stage
│   ├── classify.py      # Classification stage
│   ├── respond.py       # Response generation stage
│   └── moderate.py      # Quality moderation stage
├── specialized/          # Stage-specific CLAUDE.md files
│   ├── classifier/CLAUDE.md
│   ├── responder/CLAUDE.md
│   ├── moderator/CLAUDE.md
│   └── summarizer/CLAUDE.md
└── episodes/             # Episode directories
    └── episode_{id}/
        ├── EPISODE_CONTEXT.md  # Episode-specific context
        ├── summary.md
        ├── classified.json
        ├── responses.json
        └── ...
```

## Transitional Python Tasks (to be migrated)
```
src/wdf/
├── tasks/
│   ├── scrape_manual.py      # Manual scraping helper (CLI bridge)
│   ├── scrape.py             # Keyword + Twitter scraping (uses shared services)
│   ├── moderation.py         # Legacy moderation utilities
│   ├── watch.py              # CLI watcher script
│   └── web_moderation.py     # Transitional moderation helpers
```

## Scripts (Operational)
```
scripts/
├── safe_twitter_reply.py    # Twitter posting script
├── estimate_api_cost.py     # Cost estimation
├── load_api_keys.py         # Load API keys from database
├── load_llm_config.py        # Load LLM model config
└── load_scoring_config.py   # Load scoring thresholds
```

## Configuration
- `.env` - Main environment configuration (project root)
- `web/.env.local` - Next.js environment variables
- `docker-compose.yml` - Docker services configuration
- `pyproject.toml` - Python dependencies (Poetry)
- `web/package.json` - Node.js dependencies

# Do Not Touch

- `.github/workflows/deploy.yml`
- Any `*.key` / `*.pem` / `.env` files
- `poetry.lock` (regenerate with poetry lock)
- `artefacts/tweets.db` (SQLite database for published tweet tracking)
- `transcripts/*.hash` (cache invalidation files)
- `logs/` directory contents (generated at runtime)
- `node_modules/` (managed by npm)
- `venv/` directory (Poetry virtual environment)
- `__pycache__/` directories
- `.pytest_cache/`
- Ollama model files and configuration

# Task Workflow

## Claude Pipeline Execution Flow (Recommended)

### Stage 1: Episode Summarization
- **Input**: Transcript file + podcast overview
- **Process**: Claude analyzes transcript using `specialized/summarizer/CLAUDE.md`
- **Output**: `summary.md` + `EPISODE_CONTEXT.md` (episode-specific context)
- **Location**: `claude-pipeline/episodes/episode_{id}/`

### Stage 2: Tweet Scraping
- **Input**: Keywords from summary (or manual keywords from web UI)
- **Process**: Twitter API search (or cached tweets)
- **Output**: `tweets.json` in episode directory
- **Integration**: Can be triggered via web UI or FastAPI backend

### Stage 3: Tweet Classification (No Few-Shots!)
- **Input**: `tweets.json` + `EPISODE_CONTEXT.md` + `specialized/classifier/CLAUDE.md`
- **Process**: Claude classifies tweets using hybrid context (specialized instructions + episode context)
- **Output**: `classified.json` with relevance scores
- **Advantage**: No few-shot generation needed - Claude uses episode context directly

### Stage 4: Response Generation
- **Input**: Relevant tweets from `classified.json` + `EPISODE_CONTEXT.md` + `specialized/responder/CLAUDE.md`
- **Process**: Claude generates <280 char responses promoting podcast
- **Output**: `responses.json` with draft responses
- **Context**: Uses episode themes, guest info, and video URL from context

### Stage 5: Quality Moderation
- **Input**: `responses.json` + `EPISODE_CONTEXT.md` + `specialized/moderator/CLAUDE.md`
- **Process**: Claude evaluates its own responses for quality
- **Output**: Filtered responses ready for human review
- **Web UI**: Human reviewers approve/reject via web interface

### Stage 6: Publishing
- **Input**: Approved responses from database (web moderation)
- **Process**: Post replies to Twitter via API
- **Tracking**: Database tracks published tweets to prevent duplicates

## FastAPI Backend Workflow

### Pipeline Execution (Claude)
1. **Web UI** → Calls `/episodes/{id}/pipeline/run` via `apiClient`
2. **FastAPI** → Validates request, enqueues job to Redis/RQ
3. **RQ Worker** → Picks up job, executes `run_pipeline_job()`
4. **Worker** → Calls `claude-pipeline/orchestrator.py` via subprocess
5. **Orchestrator** → Executes requested stages
6. **Events** → Worker publishes progress to Redis pub/sub
7. **Web UI** → Listens to `/events/{episode_id}` for real-time updates

### Single Tweet Generation
1. **Web UI** → Calls `/tweets/single/generate` via `apiClient`
2. **FastAPI** → Enqueues `generate_single_tweet_job()` to RQ
3. **Worker** → Imports `ClaudeSingleTweetResponder` directly
4. **Responder** → Generates response using Claude CLI
5. **Response** → Returns to web UI via API response

# Examples

## Configuration Examples

### Environment Variables (.env)
```bash
# Project Root .env
PROJECT_ROOT=/path/to/WDFWatch
DATABASE_URL=postgresql://user:pass@localhost:5432/wdfwatch
REDIS_URL=redis://localhost:6379/0
CLAUDE_CLI_PATH=/path/to/claude
WDF_NO_AUTO_SCRAPE=true              # Disable automatic Twitter API calls

# Twitter API (OAuth 1.0a)
API_KEY=your_api_key
API_KEY_SECRET=your_api_key_secret
BEARER_TOKEN=your_bearer_token

# Twitter OAuth 2.0
CLIENT_ID=your_client_id
CLIENT_SECRET=your_client_secret

# WDFwatch OAuth tokens
WDFWATCH_ACCESS_TOKEN=your_access_token
WDFWATCH_REFRESH_TOKEN=your_refresh_token
```

```bash
# Web UI .env.local
DATABASE_URL=postgresql://user:pass@localhost:5432/wdfwatch
REDIS_URL=redis://localhost:6379/0
NEXTAUTH_SECRET=your-secret-here
NEXTAUTH_URL=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:8001  # FastAPI backend URL
WEB_API_KEY=your-internal-api-key
```

## Command Examples

### FastAPI Backend
```bash
# Start FastAPI backend
cd backend/api
uvicorn app.main:app --reload --port 8001

# Start RQ worker
python -m app.workers.worker

# Or use Makefile
make backend-start
make worker-start
```

### Web UI
```bash
# Start Next.js dev server
cd web
npm run dev

# Run database migrations
npx prisma migrate dev

# Open database GUI
npx prisma studio
```

### Claude Pipeline
```bash
# Run full pipeline
python claude-pipeline/orchestrator.py \
  --episode-id episode_123 \
  --stages summarize,classify,respond

# Generate single tweet response
python claude-pipeline/single_tweet.py \
  "Tweet text here" \
  --episode-id episode_123 \
  --video-url "https://youtube.com/..."

# Run specific stage
python -m claude_pipeline.stages.classify \
  --episode-id episode_123 \
  --tweets tweets.json
```

### Configuration Management
```bash
# Load API keys from database
eval $(python scripts/load_api_keys.py)

# Load LLM model configuration
eval $(python scripts/load_llm_config.py)

# Load scoring thresholds
eval $(python web/scripts/load_scoring_config.py)

# Check current configuration
python scripts/load_llm_config.py --show
python web/scripts/load_scoring_config.py --show
```

## API Usage Examples

### Using API Client (TypeScript)
```typescript
import { apiClient } from '@/lib/api-client'

// Run pipeline stages
const response = await apiClient.runPipeline('episode_123', {
  stages: ['summarize', 'classify', 'respond'],
  force: false,
  skip_scraping: false
})

// Generate single tweet
const tweetResponse = await apiClient.generateSingleTweet({
  tweet_text: 'Tweet content here',
  tweet_id: '1234567890',
  episode_id: 'episode_123',
  video_url: 'https://youtube.com/...'
})

// Get episode files
const files = await apiClient.getEpisodeFiles('episode_123')

// Subscribe to events
const eventSource = apiClient.subscribeToEvents('episode_123')
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data)
  console.log('Pipeline event:', data)
}
```

### Direct API Calls (curl)
```bash
# Run pipeline
curl -X POST http://localhost:8001/episodes/episode_123/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"stages": ["summarize", "classify"], "force": false}'

# Get pipeline status
curl http://localhost:8001/episodes/episode_123/pipeline/status

# Generate single tweet
curl -X POST http://localhost:8001/tweets/single/generate \
  -H "Content-Type: application/json" \
  -d '{"tweet_text": "Tweet content", "episode_id": "episode_123"}'
```

## Data Examples

### Episode Directory Structure
```
claude-pipeline/episodes/episode_123/
├── EPISODE_CONTEXT.md  # Episode-specific context (guest, themes, quotes)
├── transcript.txt      # Original transcript
├── summary.md          # Generated summary
├── keywords.json       # Extracted keywords
├── tweets.json         # Scraped tweets
├── classified.json    # Classification results with scores
├── responses.json      # Generated responses
└── published.json      # Approved and posted responses
```

### Episode Context Example (EPISODE_CONTEXT.md)
```markdown
# Episode Context: episode_123
*Generated: 2025-01-19 14:30:00*

## GUEST INFORMATION
**Name**: Daniel Miller
**Organization**: Texas Nationalist Movement

## KEY THEMES DISCUSSED
1. Texas independence movement
2. Federal overreach in border policy
3. State nullification as remedy

## VIDEO URL
https://youtube.com/watch?v=abc123
```

### Classification Results Example (classified.json)
```json
[
  {
    "id": "1234567890",
    "text": "State sovereignty is crucial for protecting liberty",
    "score": 0.92,
    "reason": "Directly discusses federalism and state sovereignty themes"
  },
  {
    "id": "0987654321",
    "text": "Just made dinner, it was delicious!",
    "score": 0.15,
    "reason": "No connection to podcast themes"
  }
]
```

### Response Example (responses.json)
```json
[
  {
    "tweet_id": "1234567890",
    "response": "Great point! Daniel Miller from the Texas Nationalist Movement explores this exact issue in our latest episode. Check it out: https://youtube.com/watch?v=abc123",
    "character_count": 187,
    "score": 0.92
  }
]
```

# Core Rules

Always maintain a narrow focus on the current task.
Always use codebase_search with target directories first to find existing relevant files.
Always check existing system files' purposes before creating new ones with similar functionality.
Always keep ALL documentation up to date (especially ARCHITECTURE.md and CLAUDE.md).
⚠️ **CRITICAL**: Always add a detailed header at the top of every new file explaining exactly what the file does, its purpose, and key components. This is mandatory for all new files.
Always document findings with inline code comments and file headers.
Always verify success through test OUTPUT (not status code) before documenting a success.
Always cleanup obsolete and/or unnecessary files.
Always attempt to fix original files rather than creating new "enhanced" versions.
Always adhere to best practices for clarity, maintainability, and efficiency.
Always add verbose debug and error logging to quickly identify errors.
Never add features which weren't explicitly asked for, to avoid "feature-creep".

**Architecture Reference**: See `ARCHITECTURE.md` for complete architecture documentation.
**Quick Start**: See `QUICKSTART.md` for setup instructions.
**Environment Setup**: See `ENV_SETUP.md` for environment variable configuration.

# Implementation Status

## Current Status: Production Web Application ✅

### Architecture Overview
- **Web-First Design**: Next.js frontend with FastAPI backend
- **Unified Claude Pipeline**: Single AI model for all stages (Claude)
- **Service-Oriented**: Clear separation between web UI, API, and pipeline
- **Hybrid Support**: FastAPI for Claude pipeline, Next.js API for legacy (backward compatibility)

## Completed Features ✅

### Core Infrastructure
- ✅ Next.js 14 web application with TypeScript
- ✅ FastAPI backend with Redis/RQ job queue
- ✅ PostgreSQL database with Prisma ORM
- ✅ Unified Claude pipeline (`claude-pipeline/`)
- ✅ Episode-based directory structure
- ✅ Hybrid context system (specialized + episode context)

### Web UI Features
- ✅ Tweet inbox with real-time updates (SSE)
- ✅ Draft review and approval workflow
- ✅ Episode management interface
- ✅ Keyword management UI
- ✅ Settings management (LLM models, scoring thresholds, API keys)
- ✅ Analytics dashboard with KPIs and charts
- ✅ Quota monitoring and alerts
- ✅ Audit logging system

### Pipeline Integration
- ✅ FastAPI backend endpoints for all pipeline operations
- ✅ Typed API client (`web/lib/api-client.ts`)
- ✅ FastAPI SSE event streaming (episodes + queue channels)
- ✅ Single tweet generation via FastAPI
- ✅ Queue processing integration
- ✅ Pipeline components use FastAPI backend

### Architecture Migration ✅
- ✅ Migrated single-tweet generation to FastAPI
- ✅ Migrated tweet-queue processing to FastAPI
- ✅ Migrated Claude pipeline stages to FastAPI
- ✅ Migrated file fetching to FastAPI (Claude episodes)
- ✅ Migrated SSE events to FastAPI (Claude pipeline)
- ✅ Created typed API client library
- ✅ Implemented event emitter and SSE hooks

## Pipeline Types

### Claude Pipeline (Recommended) ✅
- Uses FastAPI backend for all operations
- Unified Claude AI for all stages
- Episode-based context system
- No few-shot generation needed
- File location: `claude-pipeline/`

## Key Files & Locations

### Pipeline Code (Single Source of Truth)
- `claude-pipeline/orchestrator.py` - Main orchestrator
- `claude-pipeline/stages/` - Stage implementations
- `claude-pipeline/core/` - Core components
- `claude-pipeline/specialized/` - Stage-specific CLAUDE.md files
- `claude-pipeline/episodes/` - Episode directories

### Backend API
- `backend/api/app/main.py` - FastAPI application
- `backend/api/app/routes/` - API endpoints
- `backend/api/app/workers/` - Background job workers
- `backend/api/app/services/` - Business logic

### Web UI
- `web/app/` - Next.js pages and API routes
- `web/components/` - React components
- `web/lib/api-client.ts` - FastAPI client
- `web/hooks/` - React hooks (FastAPI SSE + queries)

## Data Storage

### Database (PostgreSQL) - Primary
- Episodes, tweets, drafts, keywords
- Settings (LLM models, scoring thresholds)
- Audit logs, quota tracking
- API keys (encrypted)

### Filesystem (Episode Directories)
- `claude-pipeline/episodes/episode_{id}/`
  - `EPISODE_CONTEXT.md` - Episode-specific context
  - `summary.md`, `classified.json`, `responses.json`
  - All pipeline outputs

## API Endpoints

### FastAPI Backend (http://localhost:8001)
- `/episodes/{id}/pipeline/run` - Run pipeline stages
- `/episodes/{id}/pipeline/status` - Get pipeline status
- `/episodes/{id}/files` - List episode files
- `/tweets/single/generate` - Generate single tweet response
- `/queue/jobs` - Job queue management
- `/events/{episode_id}` - SSE event stream
- `/settings/*` - Settings management

### Next.js API Routes (http://localhost:3000/api)
- `/api/episodes` - Episode management (legacy)
- `/api/tweets` - Tweet operations
- `/api/drafts` - Draft management
- `/api/settings/*` - Settings management
- `/api/events` - SSE events (legacy pipeline)

## Environment Configuration

### Main Configuration (`.env` in project root)
- Database URLs (PostgreSQL)
- Redis configuration
- Twitter API credentials
- Claude CLI path
- Application settings

### Web UI Configuration (`web/.env.local`)
- `DATABASE_URL` - PostgreSQL connection
- `NEXT_PUBLIC_API_URL` - FastAPI backend URL (default: http://localhost:8001)
- `NEXTAUTH_SECRET` - Authentication secret
- `WEB_API_KEY` - Internal API key

## Recent Improvements ✨

### Architecture Migration (2025-01-XX) ✅
- Migrated all Claude pipeline operations to FastAPI backend
- Created typed API client for type-safe communication
- Implemented FastAPI-native SSE endpoints (episodes + queue)
- Removed legacy CLI orchestrator

### Unified Claude Pipeline ✅
- Single AI model (Claude) for all stages
- Episode-based context system
- No few-shot generation needed
- Specialized CLAUDE.md files for each stage

### Web UI Enhancements ✅
- Real-time updates via SSE
- Analytics dashboard
- Keyword management
- Settings management (LLM models, scoring, API keys)
- Draft review workflow

## Known Limitations ⚠️
- Queue processing UI still relies on Next.js API proxy (migrate to backend route)
- No authentication system yet (all actions logged as 'system')
- Mobile-friendly interface improvements needed

## Migration Status

**Phase 1: Backend Setup** ✅ COMPLETE
**Phase 2: Web UI Integration** ✅ COMPLETE
- Claude pipeline fully migrated to FastAPI
- Queue events surfaced via FastAPI SSE channels

**Remaining Work**:
- Full queue processing implementation
- Deployment configuration (Docker Compose)
- Testing and observability
- Security hardening (authentication, rate limiting)

See `ARCHITECTURE.md` for complete architecture documentation.

---

<!-- Content below added by add-mcps script -->

## 🔍 OPTIMAL TOOL USAGE - RIPGREP & SERENA MCP

### Core Principles
- **NEVER use grep - ONLY use ripgrep (rg)** - use bash `rg` commands directly
- **Ripgrep (rg) is BETTER than internal search functions** - always prefer it over built-in search
- **Use ripgrep (rg) FIRST for discovery** - fast initial search via bash `rg` commands
- **Then use Serena for semantic understanding** - deep dive into code structure once you know where to look
- **NEVER read entire files** - use Serena's symbol tools to read only what's needed
- **Combine strategically: rg → Serena → Edit** - discover, understand, then modify

### When to Use ripgrep (rg)
✅ **Use ripgrep (bash rg command) for:**
- **ANY text-based search** - it's faster and better than internal search
- Finding literal strings/text patterns across files
- Searching in non-code files (logs, config, markdown, JSON)
- Discovering where error messages or specific text appears
- Finding TODOs, FIXMEs, or comment patterns
- Quick text-based discovery when you DON'T need semantic understanding
- **Initial discovery before using Serena** - always start with ripgrep

❌ **Don't use ripgrep for:**
- Finding classes, functions, or methods (use Serena instead)
- Understanding code structure (use Serena instead)
- Reading code to understand implementation (use Serena instead)

⚠️ **IMPORTANT:**
- ripgrep (rg) is SUPERIOR to any internal search function
- **USE bash `rg` commands directly** - faster and more powerful
- NEVER use grep - only use rg
- It's optimized, has proper permissions, and is significantly faster

**Optimal ripgrep (rg) Usage:**
```bash
# Use rg with file type filters for speed
rg "error_handler" -t kotlin

# Find files containing pattern
rg "GameEngine" -l  # List files only

# Get line numbers and context
rg "crash" -n -C 3  # Line numbers + 3 lines context

# Case insensitive search
rg "pattern" -i

# Search specific directory
rg "pattern" src/main/kotlin/
```

### When to Use Serena MCP
✅ **Use Serena for:**
- Finding specific functions/classes/methods by name
- Understanding code architecture and structure
- Reading code intelligently (only what you need)
- Finding all references to a symbol
- Navigating code hierarchies
- Understanding relationships between code entities

❌ **Don't use Serena for:**
- Searching text in non-code files (use rg)
- Finding arbitrary string patterns (use rg)
- Searching logs or configuration files (use rg)

**Optimal Serena Workflow:**
```bash
# 1. Start with overview - understand file structure
mcp__serena__get_symbols_overview(relative_path="path/to/File.kt")

# 2. Find specific symbols - no need to read entire file
mcp__serena__find_symbol(
    name_path="GameEngine/initGame",
    relative_path="engine/GameEngine.kt",
    include_body=True
)

# 3. Find references - understand usage
mcp__serena__find_referencing_symbols(
    name_path="GameEngine",
    relative_path="engine/GameEngine.kt"
)

# 4. Pattern search only when symbol search won't work
mcp__serena__search_for_pattern(
    substring_pattern="TODO.*critical",
    restrict_search_to_code_files=True
)
```

### Optimal Combined Strategy (Ripgrep → Serena → Edit)

**Scenario 1: Understanding a new codebase**
```
1. Use rg to quickly find key terms/patterns
2. Use Serena get_symbols_overview on files found
3. Use Serena find_symbol to read specific functions
4. Navigate with rg, understand with Serena
```

**Scenario 2: Fixing a bug**
```
1. Use rg to find error message in logs/code (FAST discovery)
2. Use Serena find_symbol to read the function with semantic context
3. Use Serena find_referencing_symbols to see where it's called
4. Fix with targeted edits - no full file reads needed
```

**Scenario 3: Adding a feature**
```
1. Use rg to find similar existing features (FAST search)
2. Use Serena to understand structure of those features (DEEP understanding)
3. Use rg for related configuration or text patterns
4. Implement using Edit tool with minimal reads
```

**Scenario 4: Refactoring code**
```
1. Use rg to find all occurrences of class/function name (FAST)
2. Use Serena find_referencing_symbols for semantic relationships (DEEP)
3. Use Serena to understand each usage context
4. Refactor systematically with Edit tool
```

### Anti-Patterns to AVOID
❌ **Bad:** Reading entire files to find one function
```bash
# DON'T DO THIS
Read("src/GameEngine.kt")  # Wastes tokens reading 2000+ lines
```

✅ **Good:** Use Serena to read only what you need
```bash
# DO THIS INSTEAD
mcp__serena__find_symbol(
    name_path="updateGame",
    relative_path="src/GameEngine.kt",
    include_body=True
)
```

❌ **Bad:** Using grep
```bash
# NEVER DO THIS
grep -r "pattern" src/     # Too slow, use rg instead
```

✅ **Good:** Use ripgrep (rg) directly
```bash
# ALWAYS DO THIS - Use rg bash commands
rg "pattern" src/
```

❌ **Bad:** Using ripgrep to find classes/functions
```bash
# DON'T DO THIS - ripgrep just finds text, not semantic meaning
rg "class GameEngine"
```

✅ **Good:** Use Serena for semantic code search
```bash
# DO THIS INSTEAD - Serena understands code structure
mcp__serena__find_symbol(name_path="GameEngine", include_kinds=[5])  # kind 5 = class
```

**Summary:**
- Text search → use `rg` bash commands
- Code structure search → use Serena MCP tools

---

## 📚 OPTIMAL TOOL USAGE - CONTEXT7 MCP

### Core Principles
- **Context7 prevents API hallucinations** - provides up-to-date, version-specific library documentation
- **ALWAYS resolve library ID first** - use `resolve-library-id` before `get-library-docs` (unless user provides exact `/org/project` format)
- **Use topic parameter to narrow scope** - fetch only relevant documentation sections
- **Control token usage strategically** - adjust `tokens` parameter based on need (default: 5000)
- **Perfect for library-specific questions** - "How do I use X in library Y?" type queries
- **Complements internal code tools** - external knowledge layer for official documentation

### When to Use Context7
✅ **Use Context7 for:**
- Learning how to use a specific library or framework
- Getting up-to-date API documentation (prevents outdated code generation)
- Version-specific feature questions (e.g., "Next.js 15 `after` function")
- Avoiding hallucinated APIs that don't exist
- Understanding current best practices for a library
- Finding official examples and working code patterns
- When user mentions "use context7" or asks about library documentation

❌ **Don't use Context7 for:**
- General coding questions not tied to a specific library
- Internal codebase understanding (use Serena instead)
- Finding real-world usage examples from GitHub repos (use Exa instead)
- Text pattern searches (use rg instead)
- Non-library documentation (use Exa for general web search)

⚠️ **CRITICAL WORKFLOW:**
1. **Step 1**: MUST call `resolve-library-id` first to get Context7-compatible ID
2. **Step 2**: Then call `get-library-docs` with that ID
3. **Exception**: Skip Step 1 if user provides exact format like `/vercel/next.js` or `/mongodb/docs`

**Optimal Context7 Usage:**
```bash
# Step 1: Resolve library name to Context7 ID (REQUIRED)
mcp__context7__resolve-library-id(
    libraryName="react query"
)
# Returns: /tanstack/query or similar

# Step 2: Fetch documentation with optional topic focus
mcp__context7__get-library-docs(
    context7CompatibleLibraryID="/tanstack/query",
    topic="hooks",           # Optional: focus on specific topic
    tokens=5000             # Optional: control documentation length
)

# Version-specific query (if user provides version)
mcp__context7__get-library-docs(
    context7CompatibleLibraryID="/vercel/next.js/v15.0.0",
    topic="server actions"
)

# Quick reference (lower tokens)
mcp__context7__get-library-docs(
    context7CompatibleLibraryID="/supabase/supabase",
    topic="authentication",
    tokens=3000
)

# Comprehensive understanding (higher tokens)
mcp__context7__get-library-docs(
    context7CompatibleLibraryID="/mongodb/docs",
    topic="aggregation pipeline",
    tokens=8000
)
```

### Context7 Anti-Patterns to AVOID
❌ **Bad:** Skipping resolve-library-id
```bash
# DON'T DO THIS - will fail without exact ID
mcp__context7__get-library-docs(
    context7CompatibleLibraryID="react-query"  # Wrong format!
)
```

✅ **Good:** Always resolve first
```bash
# DO THIS - resolve then fetch
# 1. Resolve
mcp__context7__resolve-library-id(libraryName="react-query")
# 2. Use returned ID
mcp__context7__get-library-docs(context7CompatibleLibraryID="/tanstack/query")
```

❌ **Bad:** Fetching all documentation without topic focus
```bash
# DON'T DO THIS - wastes tokens on irrelevant docs
mcp__context7__get-library-docs(
    context7CompatibleLibraryID="/vercel/next.js"
    # No topic specified - returns everything!
)
```

✅ **Good:** Use topic parameter when you know what you need
```bash
# DO THIS - narrow scope to relevant sections
mcp__context7__get-library-docs(
    context7CompatibleLibraryID="/vercel/next.js",
    topic="middleware"  # Only fetch middleware docs
)
```

---

## 🌐 OPTIMAL TOOL USAGE - EXA MCP

### Core Principles
- **"Less is More" - ONLY enable tools you need** - prevents context window bloat and tool hallucination
- **Exa provides specialized research capabilities** - web search, academic papers, company research, code examples
- **Control result quantity strategically** - use `numResults` parameter (more isn't always better)
- **Choose the right tool for the task** - each Exa tool has a specific purpose
- **Complements Context7** - Context7 for official docs, Exa for real-world examples and research
- **Neural search is powerful** - understands semantic meaning, not just keywords

### Available Exa Tools (Enable Selectively!)

**🔍 web_search_exa** - General web search
- Real-time web search with semantic understanding
- Updated every minute with latest content
- Best for: recent articles, blog posts, general web research

**📄 research_paper_search** - Academic research
- Search 100M+ research papers with full text
- Returns papers with titles, authors, publication dates, excerpts
- Best for: academic research, finding papers on specific topics

**💻 github_search** - GitHub repository search
- Find relevant repositories and GitHub accounts
- Best for: discovering tools, libraries, open source projects

**🏢 company_research** - Company information
- Crawl company websites for comprehensive information
- Searches about pages, pricing, FAQs, blogs
- Best for: competitive analysis, market research

**🔗 crawling** - Extract content from URLs
- Fetch full content from specific web pages
- Best for: when you have exact URL and need its content

**🎯 competitor_finder** - Find competing companies
- Describe what a company does (without naming it) to find competitors
- Best for: competitive landscape analysis

**📊 linkedin_search** - LinkedIn company search
- Search LinkedIn for company pages
- Best for: company information, professional context

**📖 wikipedia_search** - Wikipedia search
- Focused search within Wikipedia
- Best for: encyclopedic information, general knowledge

### When to Use Exa MCP
✅ **Use Exa for:**
- Real-world code examples from open source repos (vs Context7's official docs)
- Recent web articles and blog posts (semantic search)
- Academic paper research and literature reviews
- Company and competitive analysis
- Finding similar projects or implementations
- Discovering what's trending in tech
- Extracting content from specific URLs
- General web research beyond codebase

❌ **Don't use Exa for:**
- Internal codebase exploration (use Serena instead)
- Text pattern matching in your files (use rg instead)
- Official library documentation (use Context7 instead)
- Simple keyword searches in your code (use rg instead)

⚠️ **CRITICAL: Tool Selection Strategy**
- **Only enable the 2-3 Exa tools you actually need** for your project
- Each enabled tool consumes context window space
- Review your enabled tools: `mcp list` or check your MCP config
- Disable unused tools to maximize performance

**Optimal Exa Usage:**
```bash
# Web search - real-time semantic search
mcp__exa__web_search_exa(
    query="best practices for LLM prompt engineering 2025",
    numResults=7  # Control result quantity
)

# Research papers - academic research
mcp__exa__research_paper_search(
    query="transformer architecture improvements",
    numResults=5,
    maxCharacters=3000  # Control excerpt length
)

# GitHub search - find repositories
mcp__exa__github_search(
    query="python fuzzing framework",
    numResults=5
)

# Company research - comprehensive company info
mcp__exa__company_research(
    query="anthropic.com",  # Company URL
    subpageTarget=["about", "careers", "research"],  # Specific sections
    subpages=10  # Number of subpages to crawl
)

# Competitor finder - discover competitors
mcp__exa__competitor_finder(
    query="AI web search API",  # Describe what company does (no name!)
    excludeDomain="exa.ai",  # Exclude the company itself
    numResults=10
)

# Crawling - extract content from specific URL
mcp__exa__crawling(
    url="https://example.com/specific-article"
)

# Wikipedia search - encyclopedic info
mcp__exa__wikipedia_search_exa(
    query="fuzzing software testing",
    numResults=3
)

# LinkedIn search - company profiles
mcp__exa__linkedin_search(
    query="anthropic company page",
    numResults=3
)
```

### Exa Anti-Patterns to AVOID

❌ **Bad:** Using Exa for official library docs
```bash
# DON'T DO THIS - Context7 is better for this
mcp__exa__web_search_exa(
    query="Next.js app router documentation"
)
```

✅ **Good:** Use Context7 for official docs, Exa for examples
```bash
# DO THIS - right tool for the job
# Official docs → Context7
mcp__context7__get-library-docs(context7CompatibleLibraryID="/vercel/next.js")

# Real-world examples → Exa
mcp__exa__github_search(query="Next.js app router example projects")
```


## 🎭 OPTIMAL TOOL USAGE - PLAYWRIGHT MCP

### Core Principles
- **Snapshot-first approach - ALWAYS use browser_snapshot before actions** - accessibility tree is faster and more accurate than screenshots
- **Accessibility tree > Screenshots** - structured data beats pixel analysis (no vision models needed)
- **Playwright is for EXTERNAL web interaction** - not for your codebase (use Serena), not for documentation (use Context7/Exa)
- **Headless for automation, headed for debugging** - choose mode based on task
- **Browser state persists across calls** - one session maintains context until closed
- **Use element references from snapshots** - not dynamically generated selectors
- **Deterministic tool application** - structured approach avoids ambiguity

### When to Use Playwright MCP
✅ **Use Playwright for:**
- Web scraping and data extraction from live websites
- Automated form filling on external web applications
- E2E test generation and validation
- Multi-step web research workflows (navigate → extract → analyze)
- Visual verification of web pages (when screenshots are truly needed)
- Interacting with dynamic web applications (SPAs, complex UIs)
- Competitive analysis with live website interaction
- Automated testing of web applications you're developing
- Browser-based tasks that require state persistence (login sessions, multi-page flows)

❌ **Don't use Playwright for:**
- Reading your own codebase files (use Serena/Read instead)
- Static web searches (use Exa web_search_exa instead)
- Getting library documentation (use Context7 instead)
- Simple HTTP API calls (use curl or requests instead)
- Tasks that don't require actual browser rendering
- File system operations (use appropriate file tools)

⚠️ **CRITICAL WORKFLOW: Snapshot → Understand → Interact → Verify**
1. **Navigate** to page: `browser_navigate(url)`
2. **Snapshot** (REQUIRED): `browser_snapshot()` - get accessibility tree
3. **Understand** page structure from snapshot data
4. **Interact** using element refs from snapshot: `browser_click(element, ref)`
5. **Verify** result: `browser_snapshot()` again or `browser_wait_for(text)`

### Available Playwright Tools (Official Microsoft Implementation)

**🧭 browser_navigate** - Navigate to URL
- Entry point for all browser tasks
- Waits for page load automatically
- Use full URLs (including https://)

**📊 browser_snapshot** - Get accessibility tree (MOST IMPORTANT)
- **USE THIS FIRST** before any interaction
- Returns structured page data (no vision model needed)
- Faster and more accurate than screenshots
- Contains element refs needed for interactions

**🖱️ browser_click** - Click elements
- Requires `element` (description) and `ref` (from snapshot)
- Supports modifiers (Alt, Control, Shift, etc.)
- Supports double-click and button selection

**⌨️ browser_type** - Type text into fields
- Requires `element`, `ref`, and `text`
- Optional `slowly` for character-by-character typing
- Optional `submit` to press Enter after typing

**📝 browser_fill_form** - Fill multiple fields at once
- EFFICIENT for forms with multiple fields
- Takes array of fields with name, type, ref, value
- Single operation vs multiple type calls

**📸 browser_take_screenshot** - Visual capture
- Use ONLY when visual verification is needed
- Supports full page or specific element
- Default PNG, optional JPEG
- Filename parameter for saving

**🔍 browser_evaluate** - Execute JavaScript
- Advanced use only - when native tools insufficient
- Can operate on page or specific element
- Use sparingly - prefer native tools

**⏱️ browser_wait_for** - Wait for conditions
- Wait for text to appear/disappear
- Wait for specific time (seconds)
- Essential for dynamic content

**🗂️ browser_tabs** - Tab management
- List all tabs
- Create new tabs
- Close tabs (current or by index)
- Select/switch tabs

**🖥️ browser_console_messages** - Get console logs
- All messages or errors only
- Useful for debugging
- Monitor JavaScript errors

**🔔 browser_handle_dialog** - Handle popups
- Accept or dismiss alerts/confirms
- Provide text for prompt dialogs
- Essential for dialog interactions

**📊 browser_network_requests** - Network monitoring
- View all network requests since page load
- Debugging and performance analysis
- Track API calls and resources

**↩️ browser_navigate_back** - Go back in history
- Navigate to previous page
- Maintains session state

**🔧 browser_resize** - Resize window
- Set viewport dimensions
- Test responsive designs
- Default: 1280x720

**🗑️ browser_close** - Close browser
- End browser session
- Clean up resources
- Browser state is lost

**📄 browser_file_upload** - Upload files
- Handles file input elements
- Single or multiple files
- Requires absolute file paths

**🎯 browser_hover** - Hover over elements
- Trigger hover effects
- Requires element and ref
- Useful for dropdown menus

**🔽 browser_select_option** - Select from dropdown
- Choose options in select elements
- Single or multiple values
- Requires element, ref, and values array

**🎬 browser_drag** - Drag and drop
- Move elements between positions
- Requires start and end element refs
- Complex UI interactions

### Optimal Playwright Usage Patterns

**Pattern 1: Web Scraping**
```bash
# 1. Navigate to target site
mcp__playwright__browser_navigate(url="https://example.com/products")

# 2. ALWAYS snapshot first - understand page structure
mcp__playwright__browser_snapshot()
# Returns accessibility tree with element refs

# 3. Interact based on snapshot understanding
mcp__playwright__browser_click(
    element="Next Page button",
    ref="ref-from-snapshot-123"
)

# 4. Snapshot again to extract data
mcp__playwright__browser_snapshot()
# Parse data from new snapshot

# 5. Close when done
mcp__playwright__browser_close()
```

**Pattern 2: Form Filling (Efficient)**
```bash
# 1. Navigate and snapshot
mcp__playwright__browser_navigate(url="https://example.com/signup")
mcp__playwright__browser_snapshot()  # Understand form structure

# 2. Fill multiple fields at once (EFFICIENT)
mcp__playwright__browser_fill_form(
    fields=[
        {
            "name": "Email field",
            "type": "textbox",
            "ref": "email-ref-456",
            "value": "user@example.com"
        },
        {
            "name": "Password field",
            "type": "textbox",
            "ref": "password-ref-789",
            "value": "SecurePass123"
        },
        {
            "name": "Terms checkbox",
            "type": "checkbox",
            "ref": "terms-ref-101",
            "value": "true"
        }
    ]
)

# 3. Submit and verify
mcp__playwright__browser_click(element="Submit button", ref="submit-ref-112")
mcp__playwright__browser_wait_for(text="Welcome")
```

**Pattern 3: Dynamic Content Interaction**
```bash
# 1. Navigate and snapshot
mcp__playwright__browser_navigate(url="https://example.com/dashboard")
mcp__playwright__browser_snapshot()

# 2. Trigger action that loads dynamic content
mcp__playwright__browser_click(element="Load More", ref="load-ref-999")

# 3. Wait for new content
mcp__playwright__browser_wait_for(text="New content loaded")

# 4. Snapshot again to see new content
mcp__playwright__browser_snapshot()
```

**Pattern 4: Visual Verification (Screenshots)**
```bash
# Only use screenshots when you need VISUAL confirmation
mcp__playwright__browser_navigate(url="https://example.com")
mcp__playwright__browser_snapshot()  # Understand structure first

# Take screenshot for visual verification
mcp__playwright__browser_take_screenshot(
    filename="homepage-verification.png",
    fullPage=true
)

# Or screenshot specific element
mcp__playwright__browser_take_screenshot(
    element="Product card",
    ref="product-ref-555",
    filename="product-card.png"
)
```

**Pattern 5: Multi-Tab Workflow**
```bash
# 1. Start with first page
mcp__playwright__browser_navigate(url="https://example.com/page1")
mcp__playwright__browser_snapshot()

# 2. Open new tab for comparison
mcp__playwright__browser_tabs(action="new")

# 3. Navigate in new tab
mcp__playwright__browser_navigate(url="https://example.com/page2")
mcp__playwright__browser_snapshot()

# 4. Switch back to first tab
mcp__playwright__browser_tabs(action="list")  # Get tab indices
mcp__playwright__browser_tabs(action="select", index=0)

# 5. Close tabs when done
mcp__playwright__browser_tabs(action="close", index=1)
```

**Pattern 6: Debugging with Console**
```bash
# Navigate to page with potential errors
mcp__playwright__browser_navigate(url="https://example.com/app")
mcp__playwright__browser_snapshot()

# Interact with page
mcp__playwright__browser_click(element="Trigger Action", ref="action-ref")

# Check for JavaScript errors
mcp__playwright__browser_console_messages(onlyErrors=true)
# Review errors to understand failures
```

### Playwright Anti-Patterns to AVOID

❌ **Bad:** Taking screenshot before snapshot
```bash
# DON'T DO THIS - screenshot without understanding structure
mcp__playwright__browser_navigate(url="https://example.com")
mcp__playwright__browser_take_screenshot()  # Blind approach!
# Now you have pixels but no structured data
```

✅ **Good:** Snapshot first, screenshot only if needed
```bash
# DO THIS - understand structure, then decide if screenshot needed
mcp__playwright__browser_navigate(url="https://example.com")
mcp__playwright__browser_snapshot()  # Get structured data
# Now you understand the page and can interact deterministically
# Only take screenshot if you need visual verification
```

❌ **Bad:** Not using browser_snapshot before interactions
```bash
# DON'T DO THIS - acting blind
mcp__playwright__browser_navigate(url="https://example.com")
mcp__playwright__browser_click(element="Button", ref="???")  # Where did you get this ref?
```

✅ **Good:** Always snapshot to get element refs
```bash
# DO THIS - snapshot provides refs
mcp__playwright__browser_navigate(url="https://example.com")
mcp__playwright__browser_snapshot()  # Returns element refs
mcp__playwright__browser_click(element="Login button", ref="ref-from-snapshot")
```

❌ **Bad:** Using browser_type for multi-field forms
```bash
# DON'T DO THIS - inefficient multiple calls
mcp__playwright__browser_type(element="Email", ref="email-ref", text="user@example.com")
mcp__playwright__browser_type(element="Password", ref="pass-ref", text="password123")
mcp__playwright__browser_type(element="Name", ref="name-ref", text="John Doe")
# Three separate operations when one would do!
```

✅ **Good:** Use browser_fill_form for multiple fields
```bash
# DO THIS - single efficient operation
mcp__playwright__browser_fill_form(
    fields=[
        {"name": "Email", "type": "textbox", "ref": "email-ref", "value": "user@example.com"},
        {"name": "Password", "type": "textbox", "ref": "pass-ref", "value": "password123"},
        {"name": "Name", "type": "textbox", "ref": "name-ref", "value": "John Doe"}
    ]
)
```

❌ **Bad:** Using evaluate() when native tools exist
```bash
# DON'T DO THIS - unnecessary JavaScript
mcp__playwright__browser_evaluate(
    function="() => document.querySelector('button').click()"
)
```

✅ **Good:** Use native tools
```bash
# DO THIS - native tools are more reliable
mcp__playwright__browser_snapshot()  # Get ref
mcp__playwright__browser_click(element="Button", ref="ref-from-snapshot")
```

❌ **Bad:** Not closing browser when done
```bash
# DON'T DO THIS - resource leak
mcp__playwright__browser_navigate(url="https://example.com")
mcp__playwright__browser_snapshot()
# ... do work ...
# Browser left open!
```

✅ **Good:** Always close browser
```bash
# DO THIS - clean up resources
mcp__playwright__browser_navigate(url="https://example.com")
mcp__playwright__browser_snapshot()
# ... do work ...
mcp__playwright__browser_close()  # Clean up
```

### Configuration Options

**Headless vs Headed Mode:**
```bash
# Headless (default) - for automation
--headless

# Headed - for debugging (see what browser does)
# Remove --headless flag
```

**Browser Selection:**
```bash
--browser chrome      # Default, recommended
--browser firefox     # Alternative
--browser webkit      # Safari engine
--browser msedge      # Edge browser
```

**Additional Options:**
```bash
--port 8931                          # Custom port for SSE transport
--user-data-dir /path/to/profile     # Persist browser profile
--cdp-endpoint ws://localhost:9222   # Connect to existing browser
```

---

## 🎯 UPDATED COMBINED STRATEGY (Including Playwright)

### The Complete Toolkit - Six Layers
- **rg (ripgrep)** → Fast text-based discovery in YOUR codebase
- **Serena MCP** → Semantic understanding of YOUR code structure
- **Context7 MCP** → Official library documentation (external knowledge)
- **Exa MCP** → Web research, papers, examples (external knowledge)
- **Playwright MCP** → Browser automation for external websites (external interaction)
- **Edit tool** → Implementation in your codebase

### Enhanced Strategy Flow

**Scenario 1: Competitive feature analysis with web interaction**
```
1. Use Exa competitor_finder to identify competitors
   └─> Discover who else is solving this problem
2. Use Playwright to interact with competitor websites
   └─> browser_navigate → browser_snapshot → explore features
   └─> Take screenshots for visual verification
3. Use Playwright to scrape feature details
   └─> Extract data about their implementation
4. Use Exa web_search_exa for articles about these features
   └─> Understand industry best practices
5. Use Context7 for library capabilities you'll need
   └─> Verify you have the tools to implement
6. Use rg to find related code in your project
   └─> Discover existing similar implementations
7. Use Serena to understand your architecture
   └─> Plan integration points
8. Implement features using Edit tool
```

**Scenario 2: Web scraping for data-driven features**
```
1. Use Playwright to navigate and scrape target site
   └─> browser_navigate → browser_snapshot
   └─> Extract structured data from accessibility tree
2. Use Playwright for multi-page scraping
   └─> Handle pagination, forms, dynamic content
3. Use Context7 if scraping requires specific library knowledge
   └─> E.g., parsing formats, handling authentication
4. Use rg to find where to integrate scraped data
   └─> Locate data models, API endpoints
5. Use Serena to understand data flow architecture
   └─> Plan how scraped data fits into system
6. Implement integration using Edit tool
```

**Scenario 3: E2E test generation for your web app**
```
1. Use Playwright to interact with your deployed app
   └─> browser_navigate → browser_snapshot
   └─> Perform user workflows (headed mode for visibility)
2. Document the workflow steps Playwright performed
   └─> Save refs, actions, expected outcomes
3. Use Context7 for testing framework documentation
   └─> Learn Playwright test syntax, assertions
4. Use rg to find existing test patterns
   └─> Discover your testing conventions
5. Use Serena to understand test file structure
   └─> Know where tests belong
6. Generate test files using Edit tool
   └─> Create proper E2E test files
```

**Scenario 4: Research and implement based on live examples**
```
1. Use Exa web_search_exa to find articles about technique
   └─> Understand the concept
2. Use Playwright to visit live demo sites
   └─> browser_navigate → browser_snapshot
   └─> Inspect how feature actually works
3. Use Playwright browser_console_messages + browser_evaluate
   └─> Understand JavaScript implementation details
4. Use Context7 for libraries used in those examples
   └─> Get official documentation for tools you'll use
5. Use rg to find where to add feature in your code
   └─> Locate appropriate files
6. Use Serena to understand integration points
   └─> Plan architecture changes
7. Implement using Edit tool
```

**Scenario 5: Automated form testing and validation**
```
1. Use Playwright to navigate to form
   └─> browser_navigate → browser_snapshot
2. Use Playwright browser_fill_form for test data
   └─> Fill forms with various test cases
3. Use Playwright browser_wait_for + browser_snapshot
   └─> Verify validation messages, success states
4. Use Playwright browser_console_messages
   └─> Check for JavaScript errors
5. Document issues found
6. Use rg to find form validation code
   └─> Locate where validation happens
7. Use Serena to understand validation logic
   └─> Read validation functions
8. Fix issues using Edit tool
```

**Scenario 6: Visual regression testing**
```
1. Use Playwright to navigate to pages
   └─> browser_navigate to each page
2. Use Playwright browser_take_screenshot
   └─> Capture baseline screenshots
   └─> fullPage=true for complete pages
3. Make code changes using Edit tool
4. Use Playwright again for new screenshots
   └─> Same pages, same dimensions
5. Compare screenshots (external tool or manually)
   └─> Identify visual regressions
6. Use rg + Serena to fix issues
   └─> Locate and fix styling problems
```

### Updated Decision Tree

**Need to find text in YOUR codebase?**
→ Use **rg** (ripgrep)

**Need to understand YOUR code structure?**
→ Use **Serena MCP**

**Need official library documentation?**
→ Use **Context7 MCP**

**Need web research, papers, or examples?**
→ Use **Exa MCP**

**Need to interact with EXTERNAL websites?**
→ Use **Playwright MCP**

**Need to implement/edit YOUR code?**
→ Use **Edit tool**

### Updated Token Budget Management

The optimal workflow remains token-conscious:

1. **Start narrow** - Use specific tools with focused queries
2. **Playwright**: Use `browser_snapshot` (structured) over `browser_take_screenshot` (pixels)
3. **Playwright**: Close browser sessions when done (`browser_close`)
4. **Context7**: Use `topic` parameter to narrow scope
5. **Exa**: Limit `numResults` to 3-7 unless you need more
6. **Serena**: Use `include_body=False` first, then selectively read bodies
7. **rg**: Use file type filters (`-t python`) to reduce noise

### Updated Summary: The Six-Layer Stack

```
Layer 6: Implementation
  └─> Edit tool (targeted changes to YOUR code)

Layer 5: Internal Understanding
  └─> Serena MCP (YOUR code structure) + rg (text discovery)

Layer 4: External Knowledge
  └─> Context7 MCP (official docs) + Exa MCP (research & examples)

Layer 3: External Interaction
  └─> Playwright MCP (browser automation for external websites)

Layer 2: Strategic Planning
  └─> Choose right tools, narrow queries, manage token budget

Layer 1: User Intent
  └─> Understand what's needed before reaching for tools
```

### Context-Aware Tool Selection

**Internal (Your Codebase):**
- rg → Text search
- Serena → Code structure
- Edit → Modification

**External Knowledge (Documentation & Research):**
- Context7 → Official library docs
- Exa → Web research, papers, examples

**External Interaction (Live Websites):**
- Playwright → Browser automation, scraping, testing

**Golden Rule:**
Know your boundaries: Internal (rg/Serena) for your code, External Knowledge (Context7/Exa) for learning, External Interaction (Playwright) for websites. Choose the right tool for the right domain.
