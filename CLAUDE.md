<system_context>
Project: WDFWatch Twitter Bot
A comprehensive AI-powered social media engagement pipeline for the "War, Divorce, or Federalism" podcast. 
Automates the discovery, classification, and response generation for relevant tweets using configurable LLMs.
Features human-in-the-loop moderation, quota management, and metrics tracking.
Tech stack: Python + Next.js Web UI migration planned. Currently CLI-based with basic HTML viewer.
</system_context>

<commands>
# Core Pipeline Commands
make bootstrap           # Install all dependencies (Poetry, npm, gemini-cli)
make dev-run            # Run full pipeline in development mode
make debug              # Run pipeline with verbose debug logging
python main.py          # Main orchestrator with CLI options

# Individual Task Scripts
python src/wdf/tasks/fewshot.py --run-id=test-123    # Generate few-shot examples
python src/wdf/tasks/scrape.py --run-id=test-123     # Scrape tweets by keywords
python src/wdf/tasks/classify.py --run-id=test-123   # Classify tweets with configured model
python src/wdf/tasks/deepseek.py --run-id=test-123   # Generate responses with configured model
python src/wdf/tasks/moderation.py --run-id=test-123 # Interactive moderation TUI

# Direct Model Scripts
python tweet_classifier.py --input-file tweets.txt --summary-file summary.md --workers 8    # Tweet classifier
python tweet_response_generator.py <tweet-text>                      # Tweet response generator
node scripts/transcript_summarizer.js                # Transcript summarizer

# Web Interface
npm run twitter-feed    # Basic HTML viewer (port 3001)
node server.js          # Serve static HTML for tweet viewing

# Docker Operations
make docker-build       # Build container stack
make docker-run         # Start ollama + redis + pipeline services
docker-compose up -d    # Alternative Docker startup

# Testing & Maintenance
make test              # Run pytest test suite
make clean             # Clear artefacts and cache files
poetry run pytest -n auto    # Parallel test execution

# API Key & Safety Features
eval $(python scripts/load_api_keys.py)      # Load API keys from database to env vars
python scripts/generate_sample_tweets.py      # Generate mock tweets for testing
python scripts/manage_tweet_cache.py stats    # Show tweet cache statistics
python scripts/manage_tweet_cache.py preview  # Preview cached tweets
python scripts/manage_tweet_cache.py import artefacts/*/tweets.json  # Import tweets to cache
WDF_NO_AUTO_SCRAPE=false python main.py      # Override automatic scraping protection (use with caution)

# Scoring Configuration
eval $(python web/scripts/load_scoring_config.py)          # Load scoring thresholds from database
python web/scripts/load_scoring_config.py --show           # Display current thresholds
python web/scripts/load_scoring_config.py --set-threshold 0.75  # Set relevancy threshold
python web/scripts/load_scoring_config.py --reset          # Reset to default thresholds
</commands>

<code_style>
# Python Style Guidelines
- Follow PEP 8 with 100-character line length (enforced by Ruff)
- Use pydantic-settings for configuration management
- Structured logging with structlog + Prometheus metrics
- Type hints required for all functions (enforced by mypy)
- Docstrings in Google format for public functions
- Error handling with custom exception classes

# File Organization
- Task modules in src/wdf/tasks/ (one file per pipeline stage)
- Pydantic models for data validation and serialization
- Settings centralized in src/wdf/settings.py
- Test files mirror source structure in tests/

# Naming Conventions
- Snake_case for functions, variables, and modules
- PascalCase for classes and type definitions
- ALL_CAPS for constants and environment variables
- Prefixed metrics: TASK_LATENCY, TASK_ERRORS, TASK_SUCCESS

# Code Quality Tools
- Ruff for linting and formatting (configured in pyproject.toml)
- mypy for static type checking
- pytest for unit and integration testing
- Pre-commit hooks for automated checks
</code_style>

<file_map>
# Core Pipeline Files
main.py                     # Pipeline orchestrator with Rich UI and Prometheus metrics
src/wdf/settings.py         # Pydantic settings with environment variable support
src/wdf/twitter_client.py   # Twitter API abstraction with mock implementation
src/wdf/flow.py             # Prefect workflow orchestration
src/wdf/tweet_cache.py      # Tweet cache manager for testing without API calls

# Task Modules (Pipeline Stages)
src/wdf/tasks/fewshot.py     # Generate few-shot examples using Gemini CLI
src/wdf/tasks/scrape.py      # Tweet scraping based on extracted keywords  
src/wdf/tasks/classify.py    # Binary classification using configured model
src/wdf/tasks/deepseek.py    # Response generation using configured model
src/wdf/tasks/moderation.py  # Rich TUI for human approval workflow
src/wdf/tasks/summarise.py   # Wrapper for Node.js Gemini summarization
src/wdf/tasks/watch.py       # Transcript file monitoring and change detection

# Direct Model Scripts
tweet_classifier.py         # Standalone tweet classifier with multithreading
tweet_response_generator.py # Standalone tweet response generator
scripts/transcript_summarizer.js # Node.js LLM client for transcript summarization
scripts/generate_sample_tweets.py  # Mock tweet generator for testing
scripts/load_api_keys.py    # Load API keys from database to environment
scripts/manage_tweet_cache.py  # CLI for managing tweet cache

# Web Interface (Basic)
server.js                   # Express server for static HTML viewer
twitter_feed.html           # Basic tweet display with edit/approve UI
styles.css                  # CSS styling for web interface
scripts.js                  # Frontend JavaScript for interaction

# Data Storage (File-based)
transcripts/                # Input files and pipeline outputs
├── latest.txt             # Latest podcast transcript
├── podcast_overview.txt   # Podcast description/context
├── summary.md             # Generated episode summary
├── keywords.json          # Extracted keywords for search
├── tweets.json            # Scraped tweet data
├── classified.json        # Classified tweet results
├── responses.json         # Generated responses awaiting moderation
├── published.json         # Approved and posted responses
└── *.hash                 # Cache invalidation hashes

artefacts/                  # Run-specific outputs with timestamps
├── 20250628-134120/       # Timestamped run directories
│   ├── tweets.json        # Tweets for this run
│   ├── classified.json    # Classifications for this run
│   └── responses.json     # Responses for this run
├── tweets.db              # SQLite database for publish tracking
└── tweet_cache.json       # Cached tweets for testing without API calls

# Web UI Components (Next.js)
web/app/api/settings/api-keys/  # API key management endpoints
web/app/api/internal/api-keys/  # Internal endpoint for Python integration
web/app/(dashboard)/settings/    # Settings pages (keywords, scraping, api-keys)
web/components/settings/         # Settings UI components
web/lib/crypto.ts               # Encryption utilities for API keys

# Configuration & Infrastructure  
pyproject.toml             # Poetry dependencies and tool configuration
docker-compose.yml         # Ollama + Redis + Pipeline container stack
Dockerfile                 # Multi-stage build (Node.js + Python)
Makefile                   # Development workflow automation
pytest.ini                 # Test configuration and markers

# Testing Infrastructure
tests/unit/                # Unit tests for individual components
tests/integration/         # Integration tests for full workflows
tests/snapshots/           # Snapshot testing for prompt validation
logs/                      # Structured logs and timing data
├── pipeline.log          # Main application logs
└── stage_times.json      # Performance metrics per stage

# Documentation
README.md                  # Project overview and setup instructions
docs/Web-UI/              # Web UI migration planning documentation
docs/PRD.md               # Product requirements document
IMPROVEMENTS.md           # Known issues and enhancement ideas
</file_map>

<do_not_touch>
  • .github/workflows/deploy.yml  
  • any *.key / *.pem / .env files
  • poetry.lock (regenerate with poetry lock)
  • artefacts/tweets.db (SQLite database for published tweet tracking)
  • transcripts/*.hash (cache invalidation files)
  • logs/ directory contents (generated at runtime)
  • node_modules/ (managed by npm)
  • venv/ directory (Poetry virtual environment)
  • __pycache__/ directories
  • .pytest_cache/
  • Ollama model files and configuration
</do_not_touch>

<task_workflow>
# Pipeline Execution Flow
1. **Transcript Analysis** (Gemini 2.5-Pro via Node.js)
   - Input: transcripts/latest.txt + podcast_overview.txt
   - Output: summary.md (comprehensive analysis) + keywords.json (search terms)
   - Caching: Uses SHA256 hash to skip regeneration if unchanged

2. **Few-shot Generation** (Gemini 2.5-Pro via CLI)
   - Input: summary.md + podcast_overview.txt  
   - Output: fewshots.json (40 example tweets with RELEVANT/SKIP labels)
   - Validation: Ensures ≥20% relevant examples with proper formatting

3. **Tweet Scraping** (Twitter API or Mock)
   - Input: keywords.json
   - Output: tweets.json (raw tweet data with metadata)
   - Rate limiting: Respects Twitter API quotas with Redis token bucket

4. **Tweet Classification** (Configured model via Ollama)
   - Input: tweets.json + fewshots.json + summary.md
   - Process: Binary classification using 5 random few-shot examples 
   - Output: classified.json (tweets labeled RELEVANT/SKIP)
   - Performance: 8 worker threads for parallel processing

5. **Response Generation** (Configured model via Ollama)
   - Input: relevant tweets from classified.json + summary.md + VIDEO_URL.txt
   - Process: Generate <280 char responses introducing WDF podcast
   - Output: responses.json (draft responses awaiting human review)
   - Features: Automatic retry with exponential backoff

6. **Human Moderation** (Rich TUI)
   - Input: responses.json
   - Interface: Terminal-based approval system with edit capabilities
   - Actions: Approve, Edit, Reject each response individually
   - Output: published.json (approved responses) + audit trail

7. **Publishing** (Twitter API or Mock)
   - Input: approved responses from moderation step
   - Process: Post replies to Twitter with rate limiting
   - Tracking: SQLite database prevents duplicate posting
   - Metrics: Success/failure counts via Prometheus

# Development Workflow
- Use `make dev-run` for full pipeline execution
- Individual task testing via direct script execution
- Mock mode available for development without API calls
- Comprehensive logging and metrics collection at each stage
- Artefact preservation with timestamped run directories
</task_workflow>


<examples>
# Configuration Examples
## Environment Variables (.env)
```bash
WDF_MOCK_MODE=true
WDF_OLLAMA_HOST=http://localhost:11434
WDF_REDIS_URL=redis://localhost:6379/0
WDF_LLM_MODELS__GEMINI=gemini-2.5-pro
WDF_LLM_MODELS__GEMMA=gemma3n:e4b
WDF_LLM_MODELS__DEEPSEEK=deepseek-r1:latest
WDF_WEB_MODE=true                    # Enable web UI integration
WDF_NO_AUTO_SCRAPE=true              # Disable automatic Twitter API calls
WDF_GENERATE_SAMPLES=true            # Generate sample tweets when scraping is disabled
ENCRYPTION_KEY=your-32-byte-key-here # For API key encryption (production only)
WEB_API_KEY=your-internal-api-key    # For Python<->Web communication
# Note: Twitter API keys can now be configured via Web UI at /settings/api-keys
```

# Command Examples
## Full Pipeline Execution
```bash
# Basic pipeline run
python main.py

# Debug mode with verbose logging
python main.py --debug --force

# Non-interactive mode (skip moderation TUI)
python main.py --non-interactive

# Custom worker count for DeepSeek
python main.py --workers 4
```

## Individual Task Testing
```bash
# Generate few-shot examples
python src/wdf/tasks/fewshot.py --run-id=test-$(date +%s)

# Test tweet classification 
echo "This is a tweet about federalism" > test.txt
python tweet_classifier.py --input-file test.txt --summary-file transcripts/summary.md

# Generate response for a specific tweet
python tweet_response_generator.py "Interesting point about state sovereignty!"

# Interactive moderation of existing responses
python src/wdf/tasks/moderation.py --run-id=existing-run-123
```

# Data Examples
## Few-shot Examples Format (fewshots.json)
```json
[
  ["State sovereignty is crucial for protecting liberty", "RELEVANT"],
  ["Just made dinner, it was delicious! #foodie", "SKIP"],
  ["The Supreme Court ruling on federal overreach concerns me", "RELEVANT"],
  ["My cat is sleeping on my keyboard again", "SKIP"]
]
```

## Response Generation Output (responses.json)
```json
[
  {
    "id": "1234567890",
    "text": "Original tweet about federalism...",
    "user": "@constitutional_voter",
    "created_at": "2025-01-19T10:30:00Z",
    "classification": "RELEVANT",
    "response": "Great point! Rick Becker explores this exact issue in the WDF podcast. Check out our latest episode on constitutional federalism: https://youtu.be/example",
    "response_length": 156,
    "model": "deepseek-r1:latest"
  }
]
```

# Testing Examples
## Unit Test
```python
def test_settings_environment_override():
    os.environ["WDF_MOCK_MODE"] = "false"
    settings = WDFSettings()
    assert settings.mock_mode is False
```

## Integration Test  
```bash
# Test full pipeline with mock mode
WDF_MOCK_MODE=true python main.py --non-interactive
```
</examples>

<rule_∞>
  Re‑emit all rules from &lt;system_context&gt; through &lt;implementation_status&gt; at the top of every response.
  Always maintain a narrow focus.
  Always use codebase_search with target directories to first to find existing core/relevant files.
  Always keep track of all decisions and keep ALL documentation up to date.
  Always document findings with inline code comments.
  Always add headers to the file to indicate the file's purpose and to document which other files it interacts with.
  Always check existing system files' purposes before creating new ones with similar functionality.
  Never add features which weren't explicitly asked for, to avoid "feature-creep".
  Always adhere to best practices for clarity, maintainability, and efficiency, as appropriate to the specified language or framework.
  Always add logging/debugging to the code to quickly identify errors in the future.
</rule_∞>

<implementation_status>
# Current Status: Production CLI Pipeline ✅
- **Core Pipeline**: Fully functional end-to-end automation 
- **LLM Integration**: Configurable models for summarization, classification, and response generation
- **Human-in-the-Loop**: Rich TUI moderation system operational
- **Infrastructure**: Docker compose stack with Ollama + Redis
- **Monitoring**: Prometheus metrics and structured logging
- **Testing**: Unit tests, integration tests, snapshot tests for prompts
- **Data Storage**: File-based with artefact preservation

# In Progress: Web UI Migration 🚧
## Phase 1 Progress (Week 1) - COMPLETED ✅
- ✅ **Database Schema**: PostgreSQL with pgvector extension configured
  - Created tables: episodes, tweets, drafts, keywords, quota, audit logs
  - Implemented triggers for updated_at timestamps
  - Added indexes for performance optimization
- ✅ **Next.js Structure**: App Router with TypeScript setup complete
  - Created dashboard layout with navigation
  - Implemented React Query providers
  - Added Tailwind CSS with shadcn/ui components
- ✅ **Migration Scripts**: Python scripts for data migration ready
  - `scripts/migrate_data.py`: Moves JSON data to PostgreSQL
  - `scripts/validate_migration.py`: Validates data consistency
  - `scripts/test_migration.py`: Validates JSON structure without DB
- ✅ **Docker Integration**: Updated docker-compose.yml with PostgreSQL
  - Added pgvector/pgvector:pg16 image
  - Configured database initialization
  - Added web service configuration
- ✅ **Environment Setup**: Database connection and pooling configured
  - Prisma ORM integrated
  - Connection pooling via Prisma client
  - Environment variables documented
- ✅ **API Routes**: Basic CRUD operations implemented
  - `/api/tweets`: List tweets with pagination and filtering
  - `/api/drafts`: Create and list draft responses
  - `/api/drafts/[id]`: Individual draft operations
  - `/api/drafts/[id]/approve`: Approve draft workflow
  - `/api/drafts/[id]/reject`: Reject draft workflow
- ✅ **Data Migration Testing**: Successfully validated sample data
  - Created test data structure in `test_data/` directory
  - Validated JSON format and relationships
  - Test migration script works with mock data
- ✅ **Seed Data**: Development seed script created
  - `prisma/seed.ts`: Comprehensive seed data for all tables
  - Sample episodes, tweets, drafts, and audit logs
  - Ready for development environment setup

## Phase 2 Progress (Week 2) - COMPLETED ✅
- ✅ **Tweet List Components**: Real-time tweet inbox with filtering
  - `TweetInboxList`: Main list component with infinite scroll
  - `TweetRow`: Individual tweet display with status indicators
  - `TweetFilters`: Status and search filtering
  - `TweetDrawer`: Detailed tweet view with context
- ✅ **SSE Event System**: Server-Sent Events for real-time updates
  - `/api/events`: SSE endpoint for client connections
  - `/api/internal/events`: Internal API for Python bridge
  - `web_bridge.py`: Python integration for pipeline events
  - Type-safe event emission with `sse-events.ts`
- ✅ **Draft Review Interface**: Human approval workflow
  - `DraftReviewPanel`: Side-by-side tweet and draft review
  - `DraftEditor`: Character-limited text editor with helpers
  - `TweetContext`: Full tweet display with thread context
  - Review page with approve/reject workflow
- ✅ **Quota Monitoring**: Twitter API usage visualization
  - `QuotaMeter`: Visual quota display with warnings
  - Real-time updates via SSE
  - Breakdown by API endpoint usage
  - Projected exhaustion date calculation
- ✅ **UI Components**: Additional shadcn/ui components
  - Input, Sheet, Tabs, Tooltip, Skeleton, Toast
  - Navigation sidebar with active states
  - Dashboard layout with integrated quota meter

## Phase 3: Workflow Integration (Week 3-4) - COMPLETED ✅
- ✅ **Pipeline Integration**: Added web_bridge calls to all pipeline tasks
  - Modified scrape.py to sync tweets to PostgreSQL
  - Modified classify.py to update tweet classifications in database
  - Modified deepseek.py to create drafts in database
  - Created web_moderation.py for database-driven approval workflow
- ✅ **Human-in-the-Loop Approval**: Web-based moderation system
  - Integrated main.py to use web moderation when WDF_WEB_MODE=true
  - Automated polling for approved drafts and Twitter posting
  - Maintains backward compatibility with CLI moderation
- ✅ **Episode Management Interface**: Full CRUD operations
  - EpisodeUploadCard for transcript upload with metadata
  - EpisodeList with real-time processing status updates
  - API routes for episode creation and pipeline triggering
  - Integration with Python pipeline via subprocess
- ✅ **Audit Logging System**: Comprehensive activity tracking
  - Middleware for automatic API action logging
  - AuditLogViewer with filtering and pagination
  - Tracks all CRUD operations across entities
  - Detailed action history with user and timestamp data

## Phase 4: Production Deployment (Week 5-6) - COMPLETED ✅
- [x] **Performance optimization** - COMPLETED ✅
  - Implemented virtual scrolling with react-window for tweet lists
  - Created optimized API routes with caching and pagination
  - Added database query optimization with parallel queries
  - Implemented code splitting with loading states
- [x] **Advanced analytics dashboard** - COMPLETED ✅
  - Created comprehensive analytics API route with multiple metrics
  - Implemented KPI cards with trend indicators
  - Built interactive charts: ApprovalTrendChart, ModelPerformanceChart, PipelineMetricsChart
  - Added visual quota usage monitoring with warnings
  - Integrated with existing database schema for real-time metrics
- [x] **Production infrastructure setup** - COMPLETED ✅
  - Created docker-compose.prod.yml with full production stack
  - Added nginx configuration with SSL, caching, and rate limiting
  - Implemented monitoring with Prometheus and Grafana
  - Created automated deployment script with backup/restore
- [x] **CLI deprecation and migration guide** - COMPLETED ✅
  - Created comprehensive CLI_Migration_Guide.md
  - Documented feature comparison and workflow changes
  - Added troubleshooting and rollback procedures
  - Included step-by-step migration instructions
- [x] **Keyword Management Integration** - COMPLETED ✅ (2025-01-19)
  - Implemented full keyword CRUD UI at `/settings/keywords`
  - Created scraping configuration UI at `/settings/scraping`
  - Added database integration for Python pipeline keyword loading
  - Created `sync_keywords.py` for database-to-JSON synchronization
  - Updated `scrape.py` to read keywords from database in web mode
  - Integrated keyword sync into main pipeline workflow
  - Manual scraping trigger with custom keywords via `/api/scraping/trigger`
- **Target Stack**: Next.js 14 + PostgreSQL + pgvector + TanStack Query

# Known Issues & Limitations ⚠️
- File-based storage limits concurrent access (mitigated by dual-write mode)
- CLI moderation doesn't scale to multiple operators (resolved with web UI)
- ~~No real-time status updates during long-running tasks~~ (resolved with SSE)
- ~~Twitter quota management requires manual monitoring~~ (resolved with visual meter)
- ~~Limited analytics and reporting capabilities~~ (resolved with analytics dashboard)
- No mobile-friendly interface for approvals
- No authentication system (all actions logged as 'system' user)

# Recent Improvements ✨
- **Response Persistence Strategy (2025-01-21)** ✅
  - Fixed database accumulation issue: Old pending drafts are now auto-deleted before creating new ones
  - File-based `responses.json`: Already overwrites on each generation run (no accumulation)
  - Database `draft_replies` table: Now includes cleanup of old pending drafts
  - Only the latest response generation is kept for each tweet
  - Approved/rejected drafts are preserved (only pending drafts are cleaned up)
  - Prevents accumulation of unused tweet responses across multiple generation runs
- **Simplified Search Strategy (2025-01-20)** ✅
  - Removed complex volume weighting (Counts API limited to 5 req/15min)
  - Focus on classification stage for relevance determination
  - Batch keywords into combined queries for efficiency
  - Always use max_results=100 (10x more tweets per request)
  - Let the LLM handle relevance during classification
- Completed Phase 1 of Web UI Migration (Database & API foundation)
- Completed Phase 2 of Web UI Migration (Core UI Components)
- Completed Phase 3 of Web UI Migration (Workflow Integration)
- **Completed Phase 4 of Web UI Migration (Production & Enhancement)** ✅
  - Implemented performance optimizations:
    - Virtual scrolling for large tweet lists
    - Optimized API routes with caching
    - Database query optimization
    - Code splitting for better load times
  - Created advanced analytics dashboard:
    - Real-time KPI tracking
    - Interactive charts and visualizations
    - Quota usage monitoring with alerts
  - Set up production infrastructure:
    - Production Docker configuration
    - Nginx with SSL and caching
    - Monitoring stack (Prometheus + Grafana)
    - Automated deployment scripts
  - Documented CLI deprecation path:
    - Comprehensive migration guide
    - Feature comparison matrix
    - Step-by-step instructions
- **Completed Keyword Management Integration (2025-01-19)** ✅
  - Full UI for keyword management with CRUD operations
  - Scraping configuration interface with parameter controls
  - Database-first keyword loading in Python pipeline
  - Automatic keyword sync from database to JSON files
  - Manual scraping trigger with custom keywords
  - Maintains backward compatibility with file-based mode
- **Implemented API Safety & Key Management (2025-01-19)** ✅
  - **Disabled automatic Twitter API calls** - Pipeline no longer makes API calls unless manually triggered
  - Added `WDF_NO_AUTO_SCRAPE` environment variable to enforce manual-only scraping
  - **Tweet Cache System** for testing without API calls:
    - Automatically caches all scraped tweets for future use
    - Pipeline uses cached tweets when API calls are disabled
    - Intelligent cache with age-based cleanup (90 days retention)
    - Keyword filtering support for relevant cached tweets
    - `manage_tweet_cache.py` CLI for cache management
    - Falls back to sample generation only if cache is empty
  - Created sample tweet generator as last resort fallback
  - **API Key Management UI** at `/settings/api-keys`:
    - Secure configuration for Twitter/X, Gemini, and OpenAI keys
    - Encryption before database storage using AES-256-CBC
    - Masked display of existing keys with update capability
    - Internal API endpoint for Python pipeline to fetch decrypted keys
  - Updated scraping flow to require manual trigger from web UI
  - Added `load_api_keys.py` script for environment variable injection
  - Clear warnings in pipeline output about API usage policy
- Integrated Python pipeline with web UI database via web_bridge module
- Added web-based moderation task that monitors database for approved drafts
- Created episode management interface with upload and processing features
- Implemented comprehensive audit logging with middleware and UI
- Maintained backward compatibility with CLI-only mode
- All pipeline tasks now support dual-write mode (file + database)
- **Completed LLM Model Management (2025-01-19)** ✅
  - Web UI for configuring models per task at `/settings/llm-models`
  - Database-driven model configuration with environment variable fallback
  - Python script to load models from database
  - All pipeline tasks updated to use configurable models
  - Automatic model loading in web mode

# LLM Model Management (2025-01-19) ✅

## Completed: Unified LLM Configuration Interface

### Design Overview
Creating a unified interface to manage which LLM models are used for each pipeline task, making it easy to switch models without code changes.

### Task-to-Model Mapping
Each pipeline task will have a configurable model assignment:
- **summarization**: Generate podcast summary and keywords (default: gemini-2.5-pro)
- **fewshot**: Generate classification examples (default: gemini-2.5-pro)  
- **classification**: Classify tweets as relevant/skip (default: gemma3n:e4b)
- **response**: Generate tweet responses (default: deepseek-r1:latest)

### Available Model Options
1. **Gemini Models** (via API):
   - gemini-2.5-pro
   - gemini-2.5-flash
   - gemini-pro
   
2. **Ollama Models** (local):
   - gemma3n:e4b (classification optimized)
   - deepseek-r1:latest (reasoning model)
   - llama3.3:70b
   - qwen2.5-coder:32b
   - mixtral:8x7b

### Database Schema
Using existing Settings table with key 'llm_models':
```json
{
  "summarization": "gemini-2.5-pro",
  "fewshot": "gemini-2.5-pro", 
  "classification": "gemma3n:e4b",
  "response": "deepseek-r1:latest"
}
```

### Web UI Interface
- Settings page at `/settings/llm-models`
- Dropdown selectors for each task
- Model descriptions and capabilities
- Test functionality to validate models
- Save/reset buttons

### Python Integration
- `scripts/load_llm_config.py`: Load model config from database
- Environment variable fallback: `WDF_LLM_MODEL_<TASK>`
- Tasks check database first, then env vars, then defaults
- Model validation before use

### Implementation Progress
- [x] Create API endpoint `/api/settings/llm-models` ✅
- [x] Build Web UI settings page ✅
- [x] Create Python config loader script (`scripts/load_llm_config.py`) ✅
- [x] Update task files to use dynamic models ✅
  - Updated `src/wdf/settings.py` to support task-specific models
  - Updated `src/wdf/tasks/fewshot.py` to use `settings.llm_models.fewshot`
  - Updated `tweet_classifier.py` to check environment variables for classification model
  - Updated `tweet_response_generator.py` to check environment variables for response model
  - Updated `scripts/transcript_summarizer.js` to check environment variables for summarization model
  - Updated `main.py` to automatically load LLM config from database in web mode
- [x] Add model validation ✅
  - Created validation API endpoint `/api/settings/llm-models/validate`
  - Added "Test Models" button to UI with visual status indicators
  - Created `scripts/validate_llm_models.py` for CLI validation
  - Models are validated for availability before use
- [x] Document usage ✅

### Usage Instructions

#### For Users
1. Navigate to Web UI Settings → LLM Models
2. Select desired model for each task from dropdowns
3. Click "Save Configuration"
4. Models will be used for all subsequent pipeline runs

#### For Developers
1. **Load models in Python pipeline**:
   ```bash
   # Before running pipeline
   eval $(python scripts/load_llm_config.py)
   python main.py
   ```

2. **Check current configuration**:
   ```bash
   python scripts/load_llm_config.py --show
   ```

3. **Environment variable fallback**:
   ```bash
   # Override specific task models
   export WDF_LLM_MODEL_SUMMARIZATION="gemini-2.5-flash"
   export WDF_LLM_MODEL_CLASSIFICATION="llama3.3:70b"
   ```

4. **Validate model availability**:
   ```bash
   # Validate all configured models
   python scripts/validate_llm_models.py
   
   # Validate specific model
   python scripts/validate_llm_models.py --model deepseek-r1:latest --provider ollama
   
   # Pre-flight check before pipeline
   python scripts/validate_llm_models.py --quiet && python main.py
   ```

### Model Compatibility Notes
- **Summarization/Fewshot**: Requires Gemini API models (via gemini CLI)
- **Classification/Response**: Requires Ollama models (local)
- Ensure selected models are available before switching

# Scoring Configuration (2025-01-20) ✅

## Completed: Configurable Relevancy Thresholds

### Design Overview
Users can now configure the relevancy score thresholds through the Web UI, allowing fine-tuning of what scores are considered "relevant" without code changes.

### Configurable Thresholds
- **Relevancy Threshold**: Minimum score for a tweet to be considered relevant (default: 0.70)
- **Priority Threshold**: Score above which tweets get priority processing (default: 0.85)
- **Review Threshold**: Score below relevancy but above this might need manual review (default: 0.50)

### Web UI Interface
- Settings page at `/settings/scoring`
- Interactive sliders for threshold adjustment
- Visual preview of score ranges
- Example scores showing classification
- Save/reset functionality

### Python Integration
- `web/scripts/load_scoring_config.py`: Load thresholds from database
- Environment variable support: `WDF_RELEVANCY_THRESHOLD`, etc.
- Dynamic score ranges based on configured thresholds
- Backward compatible with hardcoded defaults

### Implementation Details
- [x] Created API endpoint `/api/settings/scoring` ✅
- [x] Built Web UI with threshold sliders and visual feedback ✅
- [x] Created Python config loader script ✅
- [x] Updated constants.py to use environment variables ✅
- [x] Integrated with main pipeline for automatic loading ✅

### Usage Instructions

#### For Users
1. Navigate to Web UI Settings → Scoring Thresholds
2. Adjust thresholds using the sliders
3. View example scores to understand impact
4. Click "Save Configuration"
5. New thresholds apply to future classifications

#### For Developers
1. **Load thresholds in Python pipeline**:
   ```bash
   # Automatically loaded in web mode
   python main.py  # (with WDF_WEB_MODE=true)
   
   # Or manually load
   eval $(python web/scripts/load_scoring_config.py)
   ```

2. **Check current configuration**:
   ```bash
   python web/scripts/load_scoring_config.py --show
   ```

3. **Set threshold via CLI**:
   ```bash
   python web/scripts/load_scoring_config.py --set-threshold 0.75
   ```

4. **Reset to defaults**:
   ```bash
   python web/scripts/load_scoring_config.py --reset
   ```

### Score Range Definitions
Based on configured thresholds, tweets are categorized as:
- **Highly Relevant**: Score ≥ Priority Threshold
- **Relevant**: Score ≥ Relevancy Threshold
- **Maybe Relevant**: Review Threshold ≤ Score < Relevancy Threshold
- **Not Relevant**: Score < Review Threshold

### Notes
- Changes only affect future classifications
- Previously scored tweets retain their original scores
- Thresholds are validated for logical consistency
- Score ranges automatically adjust based on thresholds

# CLAUDE.md Prompt Customization (2025-08-27) ✅

## Completed: Web UI for CLAUDE.md Editing

### Design Overview
Users can now customize and edit the CLAUDE.md files used for each pipeline stage directly from the Web UI, with full version control and backup capabilities.

### Features
- **Monaco Editor**: Rich markdown editing experience with syntax highlighting
- **Version History**: Track all changes with timestamps and optional notes
- **Diff Viewer**: Compare current version with original
- **Rollback**: One-click restore to any previous version
- **Reset to Original**: Always able to restore factory defaults
- **Auto-sync**: Changes saved to database are automatically written to filesystem
- **Permanent Backups**: Original files backed up as `CLAUDE.md.original`

### Pipeline Stages
Customizable CLAUDE.md files for:
- **Classifier**: Classifies tweets as relevant or irrelevant
- **Moderator**: Reviews and moderates generated responses
- **Responder**: Generates engaging responses to relevant tweets
- **Summarizer**: Creates comprehensive summaries of podcast episodes

### Web UI Access
- Navigate to Settings → Prompts & Context
- Click on "CLAUDE.md" tab
- Select the pipeline stage to edit
- Edit in Monaco editor with full markdown support
- Save with optional version notes

### File Structure
```
claude-pipeline/specialized/
├── classifier/
│   ├── CLAUDE.md         # Active prompt (synced from DB)
│   └── CLAUDE.md.original # Permanent backup
├── moderator/
│   ├── CLAUDE.md
│   └── CLAUDE.md.original
├── responder/
│   ├── CLAUDE.md
│   └── CLAUDE.md.original
└── summarizer/
    ├── CLAUDE.md
    └── CLAUDE.md.original
```

### Database Schema
- `prompt_templates`: Stores active prompts with versioning
- `prompt_history`: Full version history for rollback
- `prompt_originals`: Permanent backup of original prompts

### Usage Instructions

#### For Users
1. Navigate to **Settings → Prompts & Context**
2. Click the **CLAUDE.md** tab
3. Select the stage you want to customize
4. Edit the prompt in the Monaco editor
5. Add an optional note about your changes
6. Click **Save Changes**
7. Changes are immediately active for new pipeline runs

#### For Developers
- Prompts are automatically initialized from filesystem on first run
- Database is source of truth for active prompts
- Files are synced to filesystem on every save
- Pipeline continues reading from files (no changes needed)
- Original files preserved as `.original` for recovery

### API Endpoints
- `POST /api/prompts/init` - Initialize from filesystem
- `GET /api/prompts` - Get all prompts with history
- `POST /api/prompts` - Save new version
- `POST /api/prompts/[stage]/rollback` - Rollback to version
- `POST /api/prompts/[stage]/reset` - Reset to original

### Notes
- Changes take effect immediately for new pipeline runs
- Full audit trail maintained with user and timestamp
- Version numbers automatically increment on save
- Compare feature shows side-by-side diff with original
- Rollback preserves all version history
</implementation_status>

