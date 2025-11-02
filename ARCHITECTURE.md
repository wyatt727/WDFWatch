# WDFWatch Architecture Documentation

## Overview

WDFWatch has been refactored from a mixed Node.js/Python CLI application into a clean, service-oriented web application with clear separation of concerns.

## Architecture Principles

1. **Service Boundaries**: Clear separation between web UI, API service, and pipeline execution
2. **Async Processing**: Long-running operations use background job queues
3. **Single Source of Truth**: Pipeline code lives in `claude-pipeline/` only
4. **Type Safety**: Typed API contracts between services
5. **Observability**: Structured logging, metrics, and real-time events

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Web UI (Next.js)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Pages      │  │  Components  │  │   Hooks     │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│         │                 │                 │                  │
│         └─────────────────┼─────────────────┘                  │
│                           │                                     │
│                    ┌──────▼──────┐                             │
│                    │ API Client  │                             │
│                    │   (fetch)   │                             │
│                    └──────┬──────┘                             │
└───────────────────────────┼─────────────────────────────────────┘
                            │ HTTP/REST
┌───────────────────────────▼─────────────────────────────────────┐
│                   FastAPI Backend (Python)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Routes     │  │   Services   │  │    Models    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│         │                 │                 │                  │
│         └─────────────────┼─────────────────┘                  │
│                           │                                     │
│                    ┌──────▼──────┐                             │
│                    │  RQ Queue   │                             │
│                    └──────┬──────┘                             │
└───────────────────────────┼─────────────────────────────────────┘
                            │ Job Enqueue
┌───────────────────────────▼─────────────────────────────────────┐
│                      Redis (Job Queue)                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Queues     │  │ Pub/Sub      │  │   Results    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Job Dequeue
┌───────────────────────────▼─────────────────────────────────────┐
│                    RQ Worker (Python)                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Jobs       │  │   Events     │  │   Pipeline   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                           │                                     │
│                    ┌──────▼──────┐                             │
│                    │ Orchestrator │                             │
│                    │  (subprocess)│                             │
│                    └──────┬──────┘                             │
└───────────────────────────┼─────────────────────────────────────┘
                            │ CLI Invocation
┌───────────────────────────▼─────────────────────────────────────┐
│              Claude Pipeline (claude-pipeline/)                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Stages      │  │    Core      │  │  Episodes   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                           │                                     │
│                    ┌──────▼──────┐                             │
│                    │ Claude CLI  │                             │
│                    └─────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Web UI (`web/`)

**Technology**: Next.js 14, TypeScript, React, Prisma

**Responsibilities**:
- User interface and authentication
- Database access via Prisma (PostgreSQL)
- API client for backend communication
- Real-time updates via SSE

**Current State**: ✅ Fully Integrated
- UI components and pages implemented
- Database schema and migrations
- Typed API client library (`web/lib/api-client.ts`)
- FastAPI backend integration for Claude pipeline operations
- FastAPI SSE support for pipeline + queue updates

**Key Components**:
- `web/lib/api-client.ts` - Typed API client for FastAPI backend
- `web/hooks/use-fastapi-sse.ts` - FastAPI SSE hook for real-time updates
- `web/components/pipeline/PipelineVisualizer.tsx` - Pipeline visualizer using FastAPI SSE

### 2. FastAPI Backend (`backend/api/`)

**Technology**: FastAPI, Python 3.11+, Pydantic, RQ

**Responsibilities**:
- REST API endpoints for pipeline operations
- Job queue management
- Event publishing to Redis pub/sub
- Settings management
- Database operations for pipeline data

**Current State**: ✅ Implemented
- ✅ Health check endpoints
- ✅ Episode pipeline endpoints (run, status, files)
- ✅ Single tweet generation endpoint
- ✅ Queue management endpoints
- ✅ Settings endpoints (LLM models, scoring)
- ✅ SSE events endpoint

**Structure**:
```
backend/api/
├── app/
│   ├── main.py              # FastAPI app entrypoint
│   ├── config.py            # Configuration management
│   ├── routes/              # API route handlers
│   │   ├── health.py        # Health checks
│   │   ├── episodes.py      # Episode pipeline operations
│   │   ├── tweets.py        # Tweet generation
│   │   ├── queue.py         # Job queue management
│   │   ├── settings.py      # Settings management
│   │   └── events.py        # SSE event streaming
│   ├── services/            # Business logic services
│   │   ├── queue.py         # Redis/RQ queue management
│   │   ├── pipeline.py      # Pipeline service wrapper
│   │   ├── episodes_repo.py # Episode filesystem operations
│   │   ├── claude_cli.py    # Claude CLI invocation
│   │   ├── db.py            # Database operations
│   │   └── events.py        # Redis pub/sub events
│   ├── workers/             # Background job workers
│   │   ├── worker.py        # RQ worker entrypoint
│   │   └── jobs.py          # Job definitions
│   └── models/              # Pydantic models
│       ├── requests.py       # Request models
│       └── responses.py      # Response models
├── requirements.txt
├── Dockerfile
└── README.md
```

**API Endpoints**:

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/health` | GET | Health check | ✅ |
| `/health/ready` | GET | Readiness probe | ✅ |
| `/health/live` | GET | Liveness probe | ✅ |
| `/episodes/{id}/pipeline/run` | POST | Run pipeline stages | ✅ |
| `/episodes/{id}/pipeline/status` | GET | Get pipeline status | ✅ |
| `/episodes/{id}/files` | GET | List episode files | ✅ |
| `/episodes/{id}/files/{filename}` | GET | Get episode file content | ✅ |
| `/events/{episode_id}` | GET | SSE stream for events | ✅ |
| `/tweets/single/generate` | POST | Generate single tweet response | ✅ |
| `/queue/jobs` | GET | List jobs | ✅ |
| `/queue/jobs/{job_id}` | GET | Get job status | ✅ |
| `/queue/jobs/{job_id}` | DELETE | Cancel job | ✅ |
| `/settings/llm-models` | GET/PUT | LLM model configuration | ✅ |
| `/settings/scoring` | GET/PUT | Scoring configuration | ✅ |

### 3. Redis (`redis/`)

**Technology**: Redis 7+

**Responsibilities**:
- Job queue storage (RQ)
- Pub/sub for real-time events
- Job result caching

**Configuration**:
- Default: `redis://localhost:6379/0`
- Queue names: `default` (can be extended)
- Event channels: `wdfwatch:events:*`

### 4. RQ Workers (`backend/api/app/workers/`)

**Technology**: RQ (Redis Queue)

**Responsibilities**:
- Process background jobs from queue
- Execute pipeline orchestrator
- Publish events to Redis pub/sub
- Handle job errors and timeouts

**Current State**: ✅ Implemented
- Worker entrypoint ready
- Job definitions implemented
- Event publishing wired up

**Job Types**:
- `run_pipeline_job()` - Execute full pipeline stages ✅
- `generate_single_tweet_job()` - Generate single tweet response ✅

### 5. Claude Pipeline (`claude-pipeline/`)

**Technology**: Python 3.10+, Claude CLI

**Responsibilities**:
- Pipeline orchestration (orchestrator.py)
- Stage implementations (summarize, classify, respond, moderate)
- Episode management with CLAUDE.md memory
- Context file management

**Current State**: ✅ Self-contained and functional
- All stages implemented
- Episode directory structure established
- No dependencies on removed legacy code

**File Structure**:
```
claude-pipeline/
├── orchestrator.py          # Main pipeline orchestrator
├── single_tweet.py          # Single tweet response generator
├── core/                    # Core pipeline components
│   ├── unified_interface.py # Claude interface
│   ├── episode_manager.py   # Episode directory management
│   ├── batch_processor.py   # Batch processing utilities
│   └── ...
├── stages/                  # Pipeline stage implementations
│   ├── summarize.py        # Summarization stage
│   ├── classify.py         # Classification stage
│   ├── respond.py          # Response generation stage
│   └── moderate.py         # Quality moderation stage
├── specialized/             # Stage-specific CLAUDE.md files
│   ├── classifier/
│   ├── responder/
│   ├── summarizer/
│   └── moderator/
└── episodes/                # Episode directories (consolidated)
    └── episode_{id}/
        ├── CLAUDE.md        # Episode memory
        ├── summary.md
        ├── classified.json
        ├── responses.json
        └── ...
```

#### Specialized CLAUDE.md Files

**Location**: `claude-pipeline/specialized/{stage}/CLAUDE.md`

Each pipeline stage has its own specialized `CLAUDE.md` file that provides role-specific instructions to Claude CLI:

```
claude-pipeline/specialized/
├── classifier/
│   ├── CLAUDE.md         # Tweet classification instructions
│   └── CLAUDE.md.original
├── responder/
│   ├── CLAUDE.md         # Response generation instructions
│   └── CLAUDE.md.original
├── moderator/
│   ├── CLAUDE.md         # Quality moderation instructions
│   └── CLAUDE.md.original
└── summarizer/
    ├── CLAUDE.md         # Episode summarization instructions
    └── CLAUDE.md.original
```

**How It Works**:

1. **Stage Execution**: When a pipeline stage needs to invoke Claude CLI, the `claude_adapter.py` determines the operation mode (`summarize`, `classify`, `respond`, `moderate`).

2. **Working Directory Resolution**: The `_get_stage_working_directory()` method maps each mode to its specialized directory:
   - `summarize` → `claude-pipeline/specialized/summarizer/`
   - `classify` → `claude-pipeline/specialized/classifier/`
   - `respond` → `claude-pipeline/specialized/responder/`
   - `moderate` → `claude-pipeline/specialized/moderator/`

3. **CLI Execution**: The Claude CLI subprocess is executed with `cwd` set to the specialized directory. This ensures Claude CLI automatically discovers and reads the local `CLAUDE.md` file, which provides role-specific instructions and context.

4. **Hybrid Context System**: Claude receives instructions from two sources:
   - **Specialized CLAUDE.md**: Stage-specific role instructions (from `specialized/{stage}/CLAUDE.md`)
   - **Episode Context**: Episode-specific memory and context (from `episodes/episode_{id}/EPISODE_CONTEXT.md`)

**Implementation Details**:

The working directory is set in `claude-pipeline/core/models/claude_adapter.py`:

```python
def _get_stage_working_directory(self, mode: str) -> Path:
    """Get the working directory for a given stage mode."""
    mode_to_dir = {
        'summarize': 'summarizer',
        'classify': 'classifier',
        'respond': 'responder',
        'moderate': 'moderator'
    }
    # Returns specialized directory path or fallback to pipeline directory
```

The subprocess execution uses this directory:

```python
result = await asyncio.create_subprocess_exec(
    *cmd,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    cwd=working_dir  # Set to specialized directory
)
```

**Why This Matters**:

- **Specialized Precision**: Each stage gets instructions tailored to its specific task
- **Separation of Concerns**: Stage instructions are isolated and can be updated independently
- **CLI Convention**: Claude CLI reads `CLAUDE.md` from the current working directory, so executing from the specialized directory ensures it picks up the correct instructions
- **Maintainability**: Stage-specific instructions are easy to find and modify

**Note**: The orchestrator itself is invoked from the project root, but each stage's Claude CLI invocation runs from its specialized directory. This is the intended behavior and ensures proper context loading.

#### Prompt Structure and Usage

All prompts follow a consistent pattern:
1. **Specialized CLAUDE.md**: Automatically loaded via `cwd` (working directory)
2. **Episode Summary**: Added as `@summary.md` file reference in prompt text (if available)
3. **Prompt Instructions**: Task-specific instructions embedded in prompt text

**Important**: All prompts clarify that tweets can connect to either:
- The specific episode themes (if episode summary is available)
- OR the general themes of the WDF Podcast

This dual-context approach ensures relevance scoring and response generation work even when episode-specific context isn't available.

**Prompt Locations and Usage**:

| Stage | Method | Location | Purpose | Episode Context |
|-------|--------|----------|---------|----------------|
| **Summarize** | `summarize()` | `stages/summarize.py:120` | Generate episode summary from transcript | ❌ Not used (creates summary) |
| **Classify** | `batch_classify()` | `core/unified_interface.py:354/360` | Batch classify tweets for relevance | ✅ Via `@summary.md` reference |
| **Classify** | `classify_single()` | `stages/classify.py:167` | Single tweet classification | ✅ Via `call_async()` auto-append |
| **Respond** | `generate_response()` | `core/unified_interface.py:527` | Single tweet response generation | ✅ Via `@summary.md` reference |
| **Respond** | `generate_single_response()` | `stages/respond.py:118` | Single tweet response (stage-level) | ✅ Via `call()` wrapper |
| **Respond** | `batch_generate_responses()` | `stages/respond.py:229` | Batch response generation | ✅ Via `call()` wrapper |
| **Moderate** | `moderate_response()` | `core/unified_interface.py:612` | Quality moderation of responses | ✅ Via `@summary.md` reference |

**Prompt Examples**:

**1. Classification (Batch with Reasoning)**:
```python
# Location: core/unified_interface.py:354
prompt = f"""Using the Reasoning Mode format, classify these tweets:

Here is the episode summary for reference: @episodes/episode_123/summary.md
Note: Tweets can be relevant to either this specific episode OR the general themes of the WDF Podcast.

@{tweets_file.resolve()}

Output ONLY the scores and reasons in the exact format specified."""
```

**2. Classification (Batch without Reasoning)**:
```python
# Location: core/unified_interface.py:360
prompt = f"""Using the Batch Mode format, classify these tweets:

Here is the episode summary for reference: @episodes/episode_123/summary.md
Note: Tweets can be relevant to either this specific episode OR the general themes of the WDF Podcast.

@{tweets_file.resolve()}

Output ONLY one score per line, nothing else."""
```

**3. Single Tweet Classification**:
```python
# Location: stages/classify.py:167
prompt = f"""Score this tweet's relevance from 0.00 to 1.00 based on episode themes (if available) or general WDF Podcast themes.
Output only the numerical score.

TWEET:
{tweet_text}

SCORE:"""
```

**4. Response Generation (Unified Interface)**:
```python
# Location: core/unified_interface.py:527
prompt = f"""Generate a <200 character response to promote the WDF Podcast.
Connect the tweet to episode themes (if available) or general podcast themes, and include the video URL.

Here is the episode summary for reference: @episodes/episode_123/summary.md
Note: Connect the tweet to either this specific episode OR the general themes of the WDF Podcast.

TWEET TO RESPOND TO:
{tweet}

RESPONSE:"""
```

**5. Response Generation (Stage-Level Single)**:
```python
# Location: stages/respond.py:118
prompt = f"""You are the WDF Podcast Tweet Response Generator. Your ONLY function is to generate tweet responses that promote the podcast.

CRITICAL RULES:
- Output ONLY the tweet response - nothing else
- Maximum 240 characters
- NEVER use emojis
- NEVER explain what you're doing
- Include the URL/handle naturally
- Connect the tweet to either the specific episode themes (if available) OR the general themes of the WDF Podcast

TWEET TO RESPOND TO:
{tweet_text}

Generate a response:"""
```

**6. Response Generation (Stage-Level Batch)**:
```python
# Location: stages/respond.py:229
prompt = f"""You are the WDF Podcast Tweet Response Generator. Your ONLY function is to generate tweet responses that promote the podcast.

CRITICAL RULES:
- You ONLY output tweet responses - nothing else
- Maximum 240 characters per response
- NEVER use emojis
- NEVER explain what you're doing
- Include the provided URL/handle in each response
- For multiple tweets, separate responses with ---
- Connect each tweet to either the specific episode themes (if available) OR the general themes of the WDF Podcast

URL/HANDLE TO INCLUDE: {video_url}

TWEETS TO RESPOND TO:
{tweets_formatted}

Generate exactly {len(tweets)} responses separated by ---:"""
```

**7. Quality Moderation**:
```python
# Location: core/unified_interface.py:612
prompt = f"""Evaluate this response for quality and appropriateness.

Here is the episode summary for reference: @episodes/episode_123/summary.md

ORIGINAL TWEET:
{tweet}

GENERATED RESPONSE:
{response}

Evaluate on these criteria (0-10 each):
1. Relevance to tweet
2. Engagement potential
3. Episode connection
4. Tone appropriateness

Also check:
- Character count (must be <200)
- URL included (required)
- No emojis (required)

OUTPUT FORMAT:
RELEVANCE: [0-10]
ENGAGEMENT: [0-10]
CONNECTION: [0-10]
TONE: [0-10]
CHAR_COUNT: [actual count]
URL_INCLUDED: [YES/NO]
NO_EMOJIS: [YES/NO]
OVERALL: [APPROVE/REJECT]
FEEDBACK: [One line of feedback if rejected]"""
```

**8. Summarization**:
```python
# Location: stages/summarize.py:120
prompt = f"""Stay in your role and output in the exact format shown in CLAUDE.md.

VIDEO URL: {safe_video_url}

Summarize this transcript: @{transcript_file}"""
```

**9. Single Tweet Tool**:
```python
# Location: single_tweet.py:91
prompt = f"""TWEET TO RESPOND TO:
{tweet_text}

{f"VIDEO URL TO INCLUDE: {video_url}" if video_url else ""}
{f"ADDITIONAL CONTEXT: {custom_context}" if custom_context else ""}

Generate a response following the guidelines in your context. Output ONLY the response text:"""
```

**Episode Context Injection**:

The `call_async()` method in `unified_interface.py` automatically appends episode context to prompts that don't already include it:

```python
# Location: core/unified_interface.py:137-143
if self.current_episode_context and self.current_episode_context.exists():
    episode_ref = f"@{self.current_episode_context.resolve()}"
    if episode_ref not in prompt:
        # Append episode context reference to prompt
        prompt = f"{prompt}\n\nHere is the episode summary for reference: {episode_ref}\nNote: Tweets can be relevant to either this specific episode OR the general themes of the WDF Podcast."
```

This ensures backward compatibility with stages that construct their own prompts while still providing episode context when available.

## Data Flow

### Pipeline Execution Flow

#### Claude Pipeline (FastAPI Backend)

1. **User Request** → Web UI calls FastAPI endpoint via `apiClient`
2. **API Validation** → FastAPI validates request, checks dependencies
3. **Job Enqueue** → API enqueues job to Redis queue
4. **Job Response** → API returns job ID immediately (non-blocking)
5. **Worker Picks Up** → RQ worker dequeues job
6. **Worker Executes** → Worker calls orchestrator.py via subprocess OR imports `ClaudeSingleTweetResponder` directly
7. **Pipeline Runs** → Orchestrator executes requested stages
8. **Events Published** → Worker publishes progress events to Redis pub/sub
9. **Web UI Subscribes** → Web UI listens to FastAPI SSE endpoint (`/events/{episode_id}`)
10. **Results Stored** → Pipeline writes results to episode directory
11. **Database Updated** → Worker updates database with results (if needed)

### Event Flow

```
Worker Job Execution
    │
    ├─→ Publish: job.started
    │   └─→ Redis pub/sub: wdfwatch:events:job:{job_id}
    │
    ├─→ For each stage:
    │   ├─→ Publish: pipeline.started (stage={stage})
    │   │   └─→ Redis pub/sub: wdfwatch:events:episode:{episode_id}
    │   │
    │   └─→ Publish: pipeline.completed (stage={stage})
    │       └─→ Redis pub/sub: wdfwatch:events:episode:{episode_id}
    │
    └─→ Publish: job.completed/failed
        └─→ Redis pub/sub: wdfwatch:events:job:{job_id}
```

### SSE Event Stream

#### Claude Pipeline (FastAPI Backend)

Web UI connects to FastAPI `/events/{episode_id}`:
- FastAPI subscribes to Redis channel: `wdfwatch:events:episode:{episode_id}`
- Events streamed to client in real-time
- Format: `data: {json}\n\n`
- Event types: `pipeline.started`, `pipeline.completed`, `job.started`, `job.completed`, `job.failed`
- Hook: `useFastAPISSE()` provides React integration

## Configuration Management

### Environment Variables

**Simplified Setup**: Most configuration goes in a single `.env` file in the project root. See `ENV_SETUP.md` and `QUICKSTART.md` for detailed setup instructions.

**Required Files**:
- **`.env`** (project root) - Main development configuration file
  - Twitter API credentials (OAuth 1.0a and OAuth 2.0)
  - Database URLs
  - Redis configuration
  - Application settings
  - WDFwatch OAuth tokens (can be in separate `.env.wdfwatch` if preferred)

- **`web/.env.local`** - Next.js web application variables
  - Database connection string
  - NextAuth configuration
  - API endpoints
  - Feature flags

**Optional Files**:
- **`.env.wdfwatch`** - Optional separate file for WDFwatch OAuth tokens (for extra safety)
  - If not present, tokens can be in `.env` instead
  - Code automatically falls back to `.env` if `.env.wdfwatch` doesn't exist

- **`.env.production`** - Production-specific variables (for Docker deployments)
  - Production database credentials
  - Production security keys
  - Production URLs

**Key Variables**:

**Backend API** (from `.env`):
```bash
PROJECT_ROOT=/path/to/repo
DATABASE_URL=postgresql://user:pass@host:5432/db
REDIS_URL=redis://localhost:6379/0
WDF_REDIS_URL=redis://localhost:6379/0
CLAUDE_CLI_PATH=/path/to/claude
WDF_OLLAMA_HOST=http://localhost:11434
WDF_MOCK_MODE=false
WDF_NO_AUTO_SCRAPE=true

# Twitter API (OAuth 1.0a)
API_KEY=your_api_key
API_KEY_SECRET=your_api_key_secret
BEARER_TOKEN=your_bearer_token

# Twitter OAuth 2.0
CLIENT_ID=your_client_id
CLIENT_SECRET=your_client_secret

# WDFwatch OAuth tokens (can be in .env or .env.wdfwatch)
WDFWATCH_ACCESS_TOKEN=your_access_token
WDFWATCH_REFRESH_TOKEN=your_refresh_token
```

**Web UI** (`web/.env.local`):
```bash
DATABASE_URL=postgresql://user:pass@host:5432/db
REDIS_URL=redis://localhost:6379/0
NEXTAUTH_SECRET=your-secret-here
NEXTAUTH_URL=http://localhost:3000
ENCRYPTION_KEY=your-32-character-key
WEB_API_KEY=your-internal-api-key
NEXT_PUBLIC_API_URL=http://localhost:8001  # FastAPI backend URL for api-client
```

**Documentation**:
- See `ENV_SETUP.md` for complete environment variable documentation
- See `QUICKSTART.md` for simplified setup instructions
- See `.env.example`, `.env.production.example`, and `.env.wdfwatch.example` for templates

### Settings Storage

- **Database**: PostgreSQL `settings` table stores:
  - `llm_models` - JSON configuration
  - `scoring_config` - JSON configuration
  - `pipeline_stages` - JSON configuration (future)

- **Filesystem**: Episode-specific files in `claude-pipeline/episodes/`

## Implementation Status

### ✅ Completed

1. **Backend API Structure**
   - FastAPI application setup
   - Configuration management
   - Route handlers for all endpoints
   - Service layer implementation
   - Worker setup with RQ
   - Event publishing system

2. **Pipeline Integration**
   - Job definitions for pipeline execution
   - Subprocess invocation of orchestrator
   - Event publishing during execution
   - Error handling and timeouts

3. **Episode Management**
   - Filesystem repository service
   - Episode directory operations
   - File reading/writing utilities

4. **Database Services**
   - Database connection management
   - Episode status updates
   - Settings read/write operations
   - Tweet syncing utilities

5. **Transitional Cleanup**
   - Removed legacy multi-LLM directories
   - Removed legacy top-level Python files
   - Removed multi-LLM task files
   - Consolidated episode directories
   - Removed legacy `main.py` CLI entrypoint

6. **Web UI Integration** ✅
   - [x] Create `web/lib/api-client.ts` with typed API client
   - [x] Replace `child_process.exec()` calls with API client (Claude pipeline)
   - [x] Update pipeline components to use FastAPI backend
   - [x] Remove Python script execution from Claude pipeline routes
   - [x] Update hooks to use FastAPI SSE endpoints exclusively

7. **Single Tweet Generation** ✅
   - [x] Implement `generate_single_tweet_job()` using `claude-pipeline/single_tweet.py`
   - [x] Add proper error handling and timeout
   - [x] Publish events during generation
   - [x] Migrate `/api/single-tweet/generate` to use FastAPI backend

8. **Tweet Queue Processing** 🚧
   - [x] Migrate auto-process trigger to use FastAPI backend
   - [ ] Implement full queue processing logic in backend
   - [ ] Connect to database tweet_queue table
   - [ ] Batch processing with configurable batch size

9. **Event System Improvements**
   - [ ] Add progress tracking during pipeline stages
   - [ ] Implement event replay for disconnected clients
   - [ ] Add event filtering (by type, stage, etc.)

10. **Docker Compose**
   - [ ] Add FastAPI service to docker-compose.yml
   - [ ] Add Redis service configuration
   - [ ] Add worker service configuration
   - [ ] Update environment variable sharing
   - [ ] Add health checks for all services

11. **Testing**
   - [ ] Unit tests for API endpoints
   - [ ] Integration tests for pipeline execution
   - [ ] Worker job execution tests
   - [ ] End-to-end tests for full pipeline

12. **Observability**
   - [ ] Add Prometheus metrics endpoint
   - [ ] Implement structured logging with correlation IDs
   - [ ] Add distributed tracing (optional)
   - [ ] Job execution metrics

13. **Security**
   - [ ] API key authentication for internal API calls
   - [ ] Rate limiting on API endpoints
   - [ ] Input validation and sanitization
   - [ ] CORS configuration refinement

14. **Documentation**
   - [ ] API documentation (OpenAPI/Swagger)
   - [ ] Deployment guide
   - [ ] Development setup guide
   - [ ] Architecture decision records

## Migration Path

### Phase 1: Backend Setup ✅
- [x] Create FastAPI backend structure
- [x] Implement all endpoints
- [x] Set up Redis and RQ
- [x] Create worker infrastructure

### Phase 2: Web UI Integration ✅
- [x] Create API client library (`web/lib/api-client.ts`)
- [x] Replace Python exec calls with API calls (Claude pipeline)
- [x] Update event handling to use FastAPI SSE endpoint
- [x] Hybrid approach: Maintain Next.js API for legacy pipelines
- [x] Migrate single-tweet generation to FastAPI
- [x] Migrate tweet-queue processing to FastAPI
- [x] Update pipeline components to use FastAPI backend

### Phase 3: Deployment
- [ ] Update docker-compose.yml
- [ ] Add environment configuration
- [ ] Set up production deployment
- [ ] Add monitoring and alerting

### Phase 4: Optimization
- [ ] Add job result caching
- [ ] Implement job retries
- [ ] Add progress tracking
- [ ] Performance optimization

## File Organization

### Current Structure

```
WDFWatch/
├── web/                      # Next.js frontend
│   ├── app/                 # Next.js app router
│   ├── components/         # React components
│   ├── lib/                # Utilities
│   │   └── api-client.ts   # ✅ Typed FastAPI client
│   ├── hooks/              # React hooks
│   │   └── use-fastapi-sse.ts # ✅ FastAPI SSE hook
│   └── prisma/             # Database schema
│
├── backend/api/             # FastAPI backend service
│   ├── app/
│   │   ├── main.py         # FastAPI app
│   │   ├── routes/         # API endpoints
│   │   ├── services/       # Business logic
│   │   ├── workers/        # Background jobs
│   │   └── models/         # Pydantic models
│   └── requirements.txt
│
├── claude-pipeline/         # Pipeline code (single source of truth)
│   ├── orchestrator.py     # Main orchestrator
│   ├── core/              # Core components
│   ├── stages/            # Stage implementations
│   └── episodes/          # Episode directories
│
├── scripts/                 # Operational scripts (keep for now)
│   ├── safe_twitter_reply.py
│   ├── estimate_api_cost.py
│   └── ...
│
├── src/wdf/                # Transitional Python helpers (pending migration)
│   ├── tasks/              # scrape.py, moderation.py, scrape_manual.py, watch.py, web_moderation.py
│   └── ...
│
├── tools/                   # Future: move operational scripts here
│
└── docker-compose.yml       # Needs update for new services
```

### Recommended Cleanup

**To Move**:
- Operational scripts from `scripts/` → `tools/` (scripts that aren't called by web UI)
- Keep only scripts called by web API routes in `scripts/`

**Cleanup Completed**:
- Removed `main.py` legacy CLI orchestrator
- Removed Next.js SSE emitter + routes

## API Client Implementation ✅

### TypeScript API Client (`web/lib/api-client.ts`)

**Status**: ✅ Implemented and in use

**Features**:
- Typed API methods for all FastAPI endpoints
- Error handling with custom `APIError` class
- Request/response types matching backend Pydantic models
- SSE event stream support via `subscribeToEvents()` method
- Centralized base URL configuration

**Implementation**:
```typescript
// web/lib/api-client.ts
export class WDFWatchAPI {
  async runPipeline(episodeId: string, request: EpisodeRunRequest): Promise<PipelineRunResponse>
  async getPipelineStatus(episodeId: string, jobId?: string): Promise<JobStatus>
  async generateSingleTweet(request: SingleTweetRequest): Promise<SingleTweetResponse>
  async getEpisodeFiles(episodeId: string): Promise<EpisodeFilesResponse>
  async getEpisodeFile(episodeId: string, filename: string): Promise<EpisodeFileContentResponse>
  async processQueue(request: QueueProcessRequest): Promise<any>
  async listJobs(status?: string, limit?: number): Promise<JobListResponse>
  async getJobStatus(jobId: string): Promise<QueueJobResponse>
  async cancelJob(jobId: string): Promise<{ message: string; job_id: string }>
  subscribeToEvents(episodeId: string): EventSource
  async healthCheck(): Promise<{ service: string; version: string; status: string }>
}
```

**Usage**: Import `apiClient` from `@/lib/api-client` for default instance, or instantiate `WDFWatchAPI` for custom configuration.

### FastAPI SSE Hook (`web/hooks/use-fastapi-sse.ts`)

**Status**: ✅ Implemented

**Features**:
- React hook for FastAPI Server-Sent Events
- Auto-reconnection with configurable attempts
- Event type handling (`pipeline.started`, `pipeline.completed`, `job.*`)
- Graceful fallback and error handling

**Usage**: Used by `PipelineVisualizer` component for Claude pipeline real-time updates.

## Deployment Architecture

### Development
- All services run locally
- Redis on localhost:6379
- PostgreSQL on localhost:5432
- FastAPI on localhost:8001
- Next.js on localhost:3000

### Production (Recommended)
- Web UI: Next.js standalone deployment
- API Service: FastAPI containerized
- Workers: Multiple RQ worker instances
- Redis: Managed Redis service
- PostgreSQL: Managed database
- Load balancer: For API service scaling

## Performance Considerations

### Job Queue
- **Timeout**: 1 hour default for pipeline jobs
- **Result TTL**: 24 hours (configurable)
- **Concurrency**: Multiple workers can run in parallel
- **Priority**: Can add priority queues for urgent jobs

### Event Streaming
- **SSE**: Server-Sent Events for real-time updates
- **Redis Pub/Sub**: Efficient event distribution
- **Channel Names**: `wdfwatch:events:episode:{episode_id}`

### Pipeline Execution
- **Subprocess**: Isolated execution environment
- **CWD**: Project root for consistent paths
- **Environment**: Controlled env vars passed to orchestrator
- **Timeout**: Configurable per job type

## Security Considerations

### Current State
- CORS configured for web UI origins
- Environment-based configuration
- No authentication yet (needs implementation)

### Needed
- API key authentication for internal API calls
- Rate limiting on public endpoints
- Input validation on all endpoints
- Secret management for API keys
- Secure Redis connection (password auth)

## Monitoring & Observability

### Current State
- Structured logging with Python logging
- Health check endpoints
- Basic error handling

### Needed
- Prometheus metrics endpoint (`/health/metrics`)
- Structured logging with correlation IDs
- Error tracking (Sentry or similar)
- Job execution metrics (duration, success rate)
- Pipeline stage metrics

## Future Enhancements

1. **Job Prioritization**: Priority queues for urgent jobs
2. **Job Scheduling**: Scheduled pipeline runs
3. **Progress Tracking**: Real-time progress updates during stages
4. **Job Retries**: Automatic retry with exponential backoff
6. **Multi-worker Scaling**: Horizontal scaling of workers
7. **WebSocket Support**: Alternative to SSE for events
8. **GraphQL API**: Optional GraphQL layer for flexible queries

## Troubleshooting

### Common Issues

**Jobs Not Processing**:
- Check Redis connection (`REDIS_URL` in `.env`)
- Verify worker is running
- Check worker logs for errors
- Verify environment variables are loaded correctly

**Events Not Streaming**:
- Verify Redis pub/sub is working
- Check SSE endpoint connection
- Verify event channel names match
- Check `WDF_REDIS_URL` is set correctly

**Pipeline Execution Fails**:
- Check orchestrator.py path
- Verify Claude CLI is accessible (`CLAUDE_CLI_PATH` in `.env`)
- Check episode directory permissions
- Review subprocess error output
- Verify environment variables are passed to subprocess

**Environment Variable Issues**:
- Ensure `.env` file exists in project root
- Check that `web/.env.local` exists if using web UI
- Verify no conflicting variables between files
- See `ENV_SETUP.md` for troubleshooting environment setup
- Remember: `.env.wdfwatch` is optional - everything can go in `.env`

## Related Documentation

- **`ENV_SETUP.md`** - Complete guide to environment variable configuration
- **`QUICKSTART.md`** - Simplified setup instructions
- **`backend/api/README.md`** - FastAPI backend API documentation
- **`web/README.md`** - Next.js web application documentation

## Conclusion

The new architecture provides:
- ✅ Clear service boundaries
- ✅ Async job processing
- ✅ Real-time event streaming
- ✅ Type-safe API contracts
- ✅ Scalable worker architecture
- ✅ Single source of truth for pipeline code
- ✅ Simplified configuration management (single `.env` file approach)

Remaining work focuses on:
- Queue processing full implementation
- Deployment configuration
- Testing and observability
- Security hardening

### Migration Summary

**Completed Migrations**:
- ✅ Single tweet generation → FastAPI backend
- ✅ Tweet queue processing → FastAPI backend (auto-process trigger)
- ✅ Pipeline run (Claude) → FastAPI backend
- ✅ File fetching (Claude) → FastAPI backend
- ✅ SSE events (Claude) → FastAPI SSE endpoint

**Unified Architecture**:
- All pipeline operations flow through the FastAPI backend, Redis queues, and RQ workers
- Frontend consumes FastAPI SSE channels for pipeline and queue updates

This architecture supports the current webapp-first approach while maintaining flexibility for future enhancements.

