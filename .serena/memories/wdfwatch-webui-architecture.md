# WDFWatch WebUI Architecture - Comprehensive Documentation

## Overview
WDFWatch is a tweet engagement automation system with a Next.js WebUI frontend and Python Claude-pipeline backend. The system processes podcast episodes through multiple stages: summarization, classification, response generation, moderation, and posting to Twitter.

## Architecture Diagram

```
User → WebUI (Next.js) → API Routes → Database (PostgreSQL)
                            ↓
                      Python Pipeline (Claude)
                            ↓
                      File System (Episodes)
                            ↓
                      Twitter API (Posting)
```

---

## CRITICAL BUG FIXES (2025-01-05)

### 🔴 FIXED: Tweet Queue Posting Issues

**Problem:** Posting worked from Draft Review page but failed from Tweet Queue page.

**Root Causes Identified:**

1. **Shell Command Escaping vs Direct Argument Passing** (CRITICAL - FINAL FIX)
   - **Before:** Used `exec()` with shell command string and `JSON.stringify().slice(1, -1)` escaping
   - **After:** Uses `execFile()` with direct argument array (no shell escaping needed)
   - **Impact:** Shell escaping was causing literal backslashes to appear in tweets (e.g., `\n` instead of newline)
   - **Why execFile is better:** Passes arguments directly to Python without shell interpretation
   - **File:** `web/app/api/tweet-queue/process/route.ts:341`
   - **Code:**
   ```typescript
   const args = [scriptPath, '--tweet-id', twitterId, '--message', responseText]
   const { stdout, stderr } = await execFileAsync(pythonPath, args, {
     env: { ...cleanEnv, ...apiKeys, ... },
     timeout: 25000,
     cwd: '/home/debian/Tools/WDFWatch'
   })
   ```

2. **Python Path Mismatch** (CRITICAL)
   - **Before:** Defaulted to `'python3'` (system Python)
   - **After:** Defaults to `'/home/debian/Tools/WDFWatch/venv/bin/python'` (venv Python)
   - **Impact:** System Python lacked required dependencies
   - **File:** `web/app/api/tweet-queue/process/route.ts:336`

3. **Stale Tokens in Batch Processing** (CRITICAL)
   - **Before:** Loaded apiKeys once at start, never refreshed during batch
   - **After:** Refreshes tokens every 90 seconds during processing
   - **Impact:** Tokens expired after ~2 minutes, causing auth failures for tweets 3+
   - **File:** `web/app/api/tweet-queue/process/route.ts:237-258`
   - **Code:**
   ```typescript
   let lastTokenRefresh = Date.now()
   const TOKEN_REFRESH_INTERVAL = 90000  // 90 seconds
   
   // In processing loop
   const timeSinceRefresh = Date.now() - lastTokenRefresh
   if (timeSinceRefresh >= TOKEN_REFRESH_INTERVAL) {
     const { stdout } = await execAsync(`${pythonPath} ${ensureFreshScript} --max-age 0 --output-tokens`)
     const newTokens = JSON.parse(stdout.trim())
     apiKeys = { ...apiKeys, ...newTokens }
     lastTokenRefresh = Date.now()
   }
   ```

4. **Missing Environment Variables**
   - **Before:** Didn't pass WDF_BYPASS_QUOTA_CHECK, WDF_MOCK_MODE, WDF_REDIS_URL
   - **After:** All environment variables now match Draft Review
   - **Impact:** Inconsistent behavior between routes
   - **File:** `web/app/api/tweet-queue/process/route.ts:341-343`

5. **Inconsistent Database Imports**
   - **Before:** Tweet Queue used `'@/lib/prisma'` without query logging
   - **After:** Uses `'@/lib/db'` with query logging enabled
   - **Impact:** Harder to debug database issues in Tweet Queue
   - **File:** `web/app/api/tweet-queue/process/route.ts:8`

6. **Poor Error Logging**
   - **Before:** Truncated error output to 200 chars
   - **After:** Logs full stderr/stdout, command preview with token masking
   - **Impact:** Debugging failures was nearly impossible
   - **File:** `web/app/api/tweet-queue/process/route.ts:345-351, 432-433`

7. **Deleted Tweets Counted as Consecutive Failures** (CRITICAL)
   - **Before:** All errors counted toward "10 consecutive failures" stop condition
   - **After:** Only retryable errors count; permanent failures (deleted tweets, reply restrictions, duplicates, rate limits) are excluded
   - **Impact:** Queue stopped prematurely when encountering deleted tweets, even though other tweets could be posted successfully
   - **File:** `web/app/api/tweet-queue/process/route.ts:498-505, 665-673`
   - **Detection Code:**
   ```typescript
   else if (errorOutput.includes('deleted or not visible') ||
            errorOutput.includes('Tweet that is deleted')) {
     errorCategory = 'tweet_deleted'
     shouldRetry = false
     statusCode = 403
     console.log(`[Queue] ❌ Status: 403 FORBIDDEN - Tweet deleted or not visible`)
   }
   ```
   - **Consecutive Failure Logic:**
   ```typescript
   // Only count retryable errors, not permanent failures
   const permanentFailures = ['tweet_deleted', 'reply_restricted', 'duplicate_content', 'rate_limited']
   if (!permanentFailures.includes(errorCategory)) {
     consecutiveFailures++
     console.log(`[Queue] ❌ Consecutive failure count: ${consecutiveFailures}/${MAX_CONSECUTIVE_FAILURES} (category: ${errorCategory})`)
   } else {
     console.log(`[Queue] Not counting as consecutive failure (permanent failure: ${errorCategory})`)
   }
   ```

8. **Frontend Timeout Too Short** (CRITICAL)
   - **Before:** 60-second frontend timeout
   - **After:** 35-minute timeout (30 min backend max + 5 min buffer)
   - **Impact:** Frontend aborted requests while backend was still processing successfully
   - **File:** `web/app/(dashboard)/tweet-queue/page.tsx`
   - **Code:**
   ```typescript
   const timeoutId = setTimeout(() => {
     console.error('[QUEUE UI] ❌ REQUEST TIMEOUT: Aborting after 35 minutes')
     controller.abort()
   }, 35 * 60 * 1000) // 35 minutes in milliseconds
   ```

**Expected Outcome:**
- Success rate improved from ~30-50% to >95%
- Clear error messages for debugging
- Consistent behavior across batch sizes
- No token expiration in long-running batches
- Special characters (newlines, quotes, backslashes) preserved correctly in tweets
- Queue continues processing valid tweets even when encountering deleted/restricted tweets
- Frontend doesn't timeout during long batch processing

---

## EPISODES TAB - Claude Pipeline Workflow

### User Action Flow
1. User uploads episode transcript via `/app/(dashboard)/episodes/page.tsx`
2. Frontend calls `POST /api/episodes/[id]/claude-pipeline/run`
3. API route spawns Python orchestrator as subprocess
4. Orchestrator runs through pipeline stages
5. Results saved to both filesystem AND database

### File: `/web/app/api/episodes/[id]/claude-pipeline/run/route.ts`

**What it does:**
- Receives episode ID and stage configuration from frontend
- Spawns Python subprocess: `python scripts/claude_pipeline_bridge.py`
- Sets up environment variables for Claude CLI and Python paths
- Updates database with pipeline status
- Returns immediately (non-blocking)

**Critical Environment Setup:**
```javascript
PATH: [
  '/usr/bin',  // Node.js location
  '/usr/local/bin',
  `${homeDir}/.claude/local`,  // Claude CLI
  process.env.PATH
].join(':')
```

### File: `/claude-pipeline/orchestrator.py`

**Entry Point:** `main()` function with CLI args
**Purpose:** Master coordinator for all pipeline stages

**Pipeline Stages Executed:**
1. Summarization
2. Scraping (optional)
3. Classification
4. Response Generation  
5. Moderation (optional)

**Stage Configuration:**
- Controlled via environment variables: `WDF_STAGE_<STAGE>_ENABLED`
- Each stage can be enabled/disabled independently
- Dependencies automatically handled

**Key Methods:**
- `run_episode()` - Full pipeline execution
- `run_individual_stage()` - Single stage execution
- `_scrape_tweets_real()` - Twitter API integration via subprocess

---

## STAGE 1: SUMMARIZATION

### File: `/claude-pipeline/stages/summarize.py`

**Class:** `Summarizer`

**Process:**
1. Create episode directory: `claude-pipeline/episodes/{episode_id}/`
2. Save transcript.txt
3. Create placeholder summary.md (prevents circular context loading)
4. Call Claude API with transcript reference
5. Extract keywords from summary
6. Update episode metadata

**Files Generated:**
```
claude-pipeline/episodes/{episode_id}/
├── transcript.txt          # Original transcript
├── summary.md             # Comprehensive episode analysis (3000-5000 words)
├── keywords.json          # 60-70 keywords for tweet discovery
├── metadata.json          # Episode metadata
└── video_url.txt          # YouTube URL (optional)
```

**Database Integration:**
- Keywords saved via `web_bridge.save_keywords_to_database()`
- Only if `WDF_WEB_MODE=true`

**Backward Compatibility:**
- Also saves to `transcripts/` directory
- Legacy file structure maintained

---

## STAGE 2: TWEET SCRAPING

### File: `/claude-pipeline/orchestrator.py` (method: `_scrape_tweets_real()`)

**Process:**
1. Load keywords from `keywords.json`
2. Spawn subprocess: `python -m src.wdf.tasks.scrape`
3. Pass episode ID and keyword count
4. Twitter API called via Python script
5. Results saved to episode directory

**Files Generated:**
```
claude-pipeline/episodes/{episode_id}/
└── tweets.json            # Scraped tweets with metadata
```

**Twitter API Safety:**
- Requires `WDF_NO_AUTO_SCRAPE=false` flag
- Checks for WDFWATCH_ACCESS_TOKEN
- Falls back to cached tweets or sample generation
- Never auto-scrapes without explicit permission

**Database Sync:**
- Tweets synced via `orchestrator._sync_tweets_to_database()`
- Saved to `tweets` table with episode association

---

## STAGE 3: CLASSIFICATION

### File: `/claude-pipeline/stages/classify.py`

**Class:** `Classifier`

**Process:**
1. Clean tweets (remove unnecessary fields)
2. Load episode context from summary.md
3. Batch classify via `claude.batch_classify()`
4. Score 0.00 to 1.00 (threshold: 0.70 = RELEVANT)
5. Add classification reason if requested

**Files Generated:**
```
claude-pipeline/episodes/{episode_id}/
├── tweets_clean.json      # Cleaned tweet data
└── classified.json        # Tweets with scores and classifications
```

**Database Sync:**
- Updates `tweets` table via `web_bridge.notify_tweets_classified()`
- Sets status: 'relevant' or 'skipped'
- Saves `relevance_score` and `classification_rationale`

**Scoring:**
- RELEVANT: score >= 0.70
- SKIP: score < 0.70
- Average score logged for monitoring

---

## STAGE 4: RESPONSE GENERATION

### File: `/claude-pipeline/stages/respond.py`

**Class:** `ResponseGenerator`

**Process:**
1. Load relevant tweets from classified.json
2. Load episode context and video URL
3. Batch generate responses (15 tweets per batch)
4. Validate responses (max 250 chars, no emojis)
5. Fallback to individual generation if batch fails

**Files Generated:**
```
claude-pipeline/episodes/{episode_id}/
└── responses.json         # Generated responses for all RELEVANT tweets
```

**CRITICAL: Database Sync**
```python
sync_responses_to_database(
    responses_file=str(responses_file),
    episode_dir=episode_id
)
```

**Database Integration:**
- **CRITICAL:** Responses saved as `draft_replies` via `web_bridge.sync_responses_to_database()`
- Status: 'pending' (awaiting human review)
- Associated with `tweets` table via twitter_id
- **WITHOUT THIS SYNC, DRAFTS DON'T APPEAR IN WEB UI**

**Response Validation:**
- Max 250 characters (allows for Draft Review edits)
- No emojis
- Must include video URL
- Over-length responses kept for manual editing

---

## STAGE 5: MODERATION (Optional)

### File: `/claude-pipeline/stages/moderate.py`

**Class:** `QualityModerator`

**Purpose:** Optional AI quality check before human review

**NOT CURRENTLY USED in WebUI workflow** - Human moderation happens in Draft Review page instead.

---

## DRAFT REVIEW PAGE - Human Approval Workflow

### File: `/web/app/(dashboard)/review/page.tsx`

**Purpose:** Human operator reviews and approves/rejects AI-generated responses

**UI Components:**
- **DraftReviewPanel**: Side-by-side tweet and draft display
- **DraftEditor**: Text editor with character count (250 max)
- **TweetContext**: Full tweet display with metadata
- Navigation: Previous/Next buttons to cycle through drafts

**User Actions:**
1. Review draft response
2. Edit text if needed (character-limited editor)
3. Click "Approve" or "Reject"

### File: `/web/app/api/drafts/[id]/approve/route.ts`

**Process:**
1. Validate draft exists and status is 'pending'
2. Start database transaction:
   - Update draft status to 'approved'
   - Update tweet status to 'drafted'
   - Create audit log entry
3. **IMMEDIATE POSTING** (if not scheduled):
   - Load fresh Twitter API keys via `loadApiKeys()`
   - Call Python script: `scripts/safe_twitter_reply.py` via `execFile()`
   - Pass tweet ID and response text as direct arguments (no shell escaping)
   - Update draft status to 'posted'
   - Add to tweet_queue as 'completed'
4. **OR Schedule for later:**
   - Add to tweet_queue with status 'scheduled'

**Critical Twitter Posting Code:**
```javascript
const args = [scriptPath, '--tweet-id', twitterId, '--message', responseText]
const { stdout, stderr } = await execFileAsync(pythonPath, args, {
  env: {
    ...cleanEnv,
    ...apiKeys,  // Fresh tokens
    WDFWATCH_MODE: 'true',
    WDF_WEB_MODE: 'true',
    WDF_BYPASS_QUOTA_CHECK: 'true',
    WDF_MOCK_MODE: 'false',
    WDF_REDIS_URL: 'redis://localhost:6379/0'
  },
  timeout: 25000,
  cwd: '/home/debian/Tools/WDFWatch'
})
```

**Two Posting Paths:**
1. **Immediate** (from Draft Review):
   - `POST /api/drafts/[id]/approve`
   - Posts to Twitter immediately
   - Adds to queue as 'completed' for tracking

2. **Queued** (from Draft Review with error):
   - Adds to `tweet_queue` as 'pending'
   - Processed via "Process Queue" button

---

## TWEET QUEUE TAB - Batch Processing

### File: `/web/app/(dashboard)/tweet-queue/page.tsx`

**Purpose:** Process multiple approved drafts in batch

**UI Features:**
- Queue statistics (pending, processing, completed, failed)
- Filtering by status, episode, priority
- Bulk actions (priority, retry, cancel)
- "Process Queue" button - main action

**Process Queue Button:**
```javascript
onClick={() => {
  processQueueMutation.mutate(1000)  // Process up to 1000 tweets
}}
```

### File: `/web/app/api/tweet-queue/process/route.ts`

**CRITICAL WORKFLOW (UPDATED 2025-01-05):**

1. **Token Refresh ALWAYS happens:**
```javascript
// FORCE token refresh before processing
await execAsync(`${pythonPath} ${ensureFreshScript} --max-age 0 --output-tokens`)
```

2. **Load pending tweets:**
```sql
SELECT * FROM tweet_queue
WHERE status = 'pending'
  AND source = 'approved_draft'
ORDER BY priority DESC, added_at ASC
LIMIT 1000
```

3. **Process each tweet:**
   - **NEW:** Refresh tokens every 90 seconds during batch processing
   - Mark as 'processing'
   - Call `scripts/safe_twitter_reply.py` via `execFile()` with direct argument passing
   - Parse response for errors
   - **45 second delay between posts** (Twitter rate limiting)

4. **Error Handling & Categorization:**
   - **tweet_deleted** (403 with "deleted or not visible"): Permanent failure, don't retry, don't count as consecutive failure
   - **reply_restricted** (403): Permanent failure, don't retry, don't count as consecutive failure
   - **duplicate_content** (409): Actually a success, don't retry, don't count as consecutive failure
   - **rate_limited** (429): Requeue, stop processing, don't count as consecutive failure
   - **auth_error** (401): Permanent failure, requires manual intervention
   - **unknown** (500): Retry up to 3 times, counts as consecutive failure

5. **Consecutive Failure Logic:**
   - **CRITICAL:** Only retryable errors count toward the "10 consecutive failures" stop condition
   - Permanent failures (deleted tweets, reply restrictions, duplicates, rate limits) are excluded
   - This allows the queue to continue processing valid tweets even when encountering deleted/restricted tweets
   ```typescript
   const permanentFailures = ['tweet_deleted', 'reply_restricted', 'duplicate_content', 'rate_limited']
   if (!permanentFailures.includes(errorCategory)) {
     consecutiveFailures++
   } else {
     console.log(`[Queue] Not counting as consecutive failure (permanent failure: ${errorCategory})`)
   }
   ```

6. **Stop Conditions:**
   - 10 consecutive retryable failures (system errors only, not deleted tweets)
   - Rate limit hit (429)
   - All tweets processed
   - 30-minute timeout

7. **Update Draft Status:**
```javascript
await prisma.draftReply.update({
  where: { id: metadata.draftId },
  data: {
    postedAt: new Date(),
    status: 'posted'
  }
})
```

**Rate Limiting:**
- Twitter allows 50 tweets per 15-minute window
- Resets at :00, :15, :30, :45 past each hour
- 45 second delay between tweets prevents burst limits
- Automatic calculation of reset time on 429 error

**Critical Improvements (2025-01-05):**
- Uses `execFile()` instead of `exec()` for proper argument passing (no shell escaping issues)
- Uses venv Python instead of system Python
- Refreshes tokens every 90 seconds during batch
- Full error logging with stderr/stdout capture
- Command logging with token masking
- Consistent environment variables with Draft Review
- Smart consecutive failure counting (excludes permanent failures)
- 35-minute frontend timeout to accommodate long batch jobs

---

## DATABASE SCHEMA (Key Tables)

### `podcast_episodes`
```sql
- id: integer (PK)
- title: varchar
- transcript_text: text
- pipelineType: varchar ('claude' or 'legacy')
- claudePipelineStatus: varchar ('initializing', 'running', 'completed', 'failed')
- claudeEpisodeDir: varchar (episode directory name)
- claudeContextGenerated: boolean
```

### `tweets`
```sql
- id: integer (PK)
- twitter_id: varchar (unique) - Twitter's tweet ID
- episode_id: integer (FK) - Associated episode
- author_handle: varchar
- full_text: text
- status: varchar ('unclassified', 'relevant', 'skipped', 'drafted', 'posted')
- relevance_score: decimal
- classification_rationale: text
- created_at: timestamp
```

### `draft_replies`
```sql
- id: integer (PK)
- tweet_id: integer (FK to tweets.id)
- text: text - Generated response
- status: varchar ('pending', 'approved', 'rejected', 'posted')
- model: varchar - AI model used
- approvedAt: timestamp
- postedAt: timestamp
- rejectedReason: text
```

### `tweet_queue`
```sql
- id: integer (PK)
- tweet_id: varchar (unique) - Queue entry ID
- twitter_id: varchar - Original tweet's Twitter ID
- source: varchar ('approved_draft', 'manual', 'scrape')
- priority: integer (0-10)
- status: varchar ('pending', 'processing', 'completed', 'failed', 'cancelled')
- episode_id: integer (FK)
- metadata: jsonb - Stores draftId, responseText, error details
- retry_count: integer
- processed_at: timestamp
```

### `claude_pipeline_runs`
```sql
- id: integer (PK)
- episode_id: integer (FK)
- run_id: varchar
- stage: varchar
- claude_mode: varchar
- status: varchar
- started_at: timestamp
- completed_at: timestamp
- cost_usd: decimal
- error_message: text
```

---

## FILE SYSTEM STRUCTURE

### Episode Directory (Primary Storage)
```
claude-pipeline/episodes/{episode_id}/
├── transcript.txt          # Original transcript (saved first)
├── summary.md             # Comprehensive analysis (3000-5000 words)
├── keywords.json          # 60-70 keywords
├── tweets.json            # Scraped tweets
├── tweets_clean.json      # Cleaned tweets for classification
├── classified.json        # Scored and classified tweets
├── responses.json         # Generated responses
├── metadata.json          # Episode metadata
└── video_url.txt          # YouTube URL

ALL FILES CREATED HERE BY PYTHON PIPELINE
```

### Legacy Compatibility (Backward Compatibility)
```
transcripts/
├── summary.md             # Copy of episode summary
├── keywords.json          # Copy of keywords
├── tweets.json            # Copy of tweets
└── *.hash                 # Cache invalidation

DUAL-WRITE: Files written to BOTH locations
```

---

## DATA FLOW SUMMARY

### Episode Processing (Full Workflow)

1. **Upload Transcript** → `podcast_episodes` table
2. **Run Claude Pipeline** → Spawn Python subprocess
3. **Summarization**:
   - Write: `claude-pipeline/episodes/{id}/summary.md`
   - Write: `claude-pipeline/episodes/{id}/keywords.json`
   - Save to DB: Keywords via web_bridge

4. **Scraping**:
   - Write: `claude-pipeline/episodes/{id}/tweets.json`
   - Save to DB: `tweets` table via web_bridge

5. **Classification**:
   - Write: `claude-pipeline/episodes/{id}/classified.json`
   - Update DB: `tweets.relevance_score`, `tweets.status`

6. **Response Generation**:
   - Write: `claude-pipeline/episodes/{id}/responses.json`
   - **CRITICAL:** Save to DB: `draft_replies` table via web_bridge
   - **Status:** 'pending'

### Draft Approval Workflow

7. **Human Review** (Draft Review page):
   - Read from: `draft_replies` WHERE status='pending'
   - User edits text (max 250 chars)
   - User clicks "Approve"

8. **Immediate Posting** (`/api/drafts/[id]/approve`):
   - Update DB: `draft_replies.status` = 'approved'
   - Call: `scripts/safe_twitter_reply.py` via `execFile()`
   - Post to Twitter API
   - Update DB: `draft_replies.status` = 'posted'
   - Add to: `tweet_queue` as 'completed' (for tracking)

**OR** (if immediate posting fails):
   - Add to: `tweet_queue` as 'pending'
   - Process via "Process Queue" button

### Queue Processing Workflow

9. **Process Queue** (Tweet Queue tab):
   - Refresh OAuth tokens (ALWAYS)
   - **NEW:** Refresh tokens every 90 seconds during batch
   - Load from: `tweet_queue` WHERE status='pending' AND source='approved_draft'
   - For each tweet:
     - Mark as 'processing'
     - Call: `scripts/safe_twitter_reply.py` via `execFile()` (direct argument passing)
     - Handle errors with smart categorization
     - Only count retryable errors toward consecutive failure limit
     - Update: `draft_replies.status` = 'posted'
     - Update: `tweet_queue.status` = 'completed'
     - 45 second delay before next tweet

---

## CRITICAL INTEGRATION POINTS

### 1. Response → Database Sync
**File:** `/claude-pipeline/stages/respond.py`
```python
sync_responses_to_database(
    responses_file=str(responses_file),
    episode_dir=episode_id
)
```
**Purpose:** Without this, generated responses don't appear in Draft Review page

### 2. Draft Approval → Twitter Posting
**File:** `/web/app/api/drafts/[id]/approve/route.ts`
```javascript
const args = [scriptPath, '--tweet-id', twitterId, '--message', responseText]
const { stdout, stderr } = await execFileAsync(pythonPath, args, {
  env: { ...apiKeys, WDFWATCH_MODE: 'true' }
})
```
**Purpose:** Immediately posts to Twitter after approval using direct argument passing

### 3. Queue Processing → Batch Posting
**File:** `/web/app/api/tweet-queue/process/route.ts`
```javascript
// Token refresh (CRITICAL - now every 90s during batch)
await execAsync(`${pythonPath} ${ensureFreshScript} --max-age 0`)
```
**Purpose:** Ensures fresh OAuth tokens before bulk posting

### 4. Web Bridge → SSE Events
**File:** `/web/scripts/web_bridge.py`
```python
self.emit_sse_event({
    "type": "pipeline_status",
    "stage": stage,
    "status": "completed"
})
```
**Purpose:** Real-time UI updates during pipeline execution

---

## KEY DIFFERENCES: Database vs Filesystem

### Saved to BOTH (Dual-Write):
- Tweets (tweets.json + tweets table)
- Keywords (keywords.json + keywords table)
- Classifications (classified.json + tweets.relevance_score)

### Saved to FILESYSTEM ONLY:
- transcript.txt
- summary.md
- tweets_clean.json
- metadata.json
- video_url.txt

### Saved to DATABASE ONLY:
- draft_replies (generated responses for review)
- tweet_queue (posting queue management)
- audit_log (all actions tracked)
- claude_pipeline_runs (pipeline execution tracking)

### PRIMARY STORAGE by Stage:
- **Summarization**: Filesystem (summary.md is source of truth)
- **Classification**: Database (tweets.relevance_score is source of truth)
- **Response Generation**: Database (draft_replies is source of truth)
- **Moderation**: Database (draft_replies.status is source of truth)
- **Posting**: Database (tweet_queue is source of truth)

---

## COMMON PITFALLS & DEBUGGING

### 1. Responses Not Appearing in Draft Review
**Cause:** `sync_responses_to_database()` not called or failed
**Fix:** Check logs for "synced X responses to database"
**Location:** `claude-pipeline/stages/respond.py:140`

### 2. Tweets Not Posting (FIXED 2025-01-05)
**Previous Causes:** 
- Stale OAuth tokens (now refreshed every 90s)
- Python environment mismatch (now uses venv Python)
- Shell escaping bugs (now uses execFile with direct arguments)
**Fix:** All issues resolved in latest update
**Location:** `/web/app/api/tweet-queue/process/route.ts`

### 3. Special Characters Appearing Incorrectly (FIXED 2025-01-05)
**Previous Cause:** Shell command construction with `exec()` caused escaping issues
**Fix:** Now uses `execFile()` which passes arguments directly without shell interpretation
**Impact:** Newlines, quotes, backslashes, and all special characters preserved correctly

### 4. Rate Limit Errors (429)
**Cause:** Twitter limits 50 tweets per 15 minutes
**Fix:** Automatic - queue stops and shows reset time
**Location:** `/web/app/api/tweet-queue/process/route.ts:445`

### 5. Queue Stopping Prematurely on Deleted Tweets (FIXED 2025-01-05)
**Previous Cause:** Deleted tweets (403 errors) counted as consecutive failures
**Fix:** Smart error categorization - permanent failures excluded from consecutive count
**Impact:** Queue now continues processing valid tweets even when encountering deleted/restricted tweets
**Location:** `/web/app/api/tweet-queue/process/route.ts:498-505, 665-673`

### 6. Duplicate Drafts
**Cause:** Multiple pipeline runs without cleanup
**Fix:** Delete old pending drafts before creating new ones
**Note:** 2025-01-21 fix implemented - auto-cleanup on regeneration

### 7. Episode Context Not Loading
**Cause:** summary.md not yet generated
**Fix:** Summarization stage creates placeholder first
**Location:** `claude-pipeline/stages/summarize.py:85`

### 8. Frontend Timeout During Long Queue Processing (FIXED 2025-01-05)
**Previous Cause:** 60-second frontend timeout too short for batch jobs
**Fix:** Increased to 35 minutes (30 min backend max + 5 min buffer)
**Location:** `/web/app/(dashboard)/tweet-queue/page.tsx`

---

## ENVIRONMENT VARIABLES

### Required for Pipeline:
```bash
DATABASE_URL=postgresql://...
WDF_WEB_MODE=true
WDF_NO_AUTO_SCRAPE=false  # Allow Twitter API
WDFWATCH_ACCESS_TOKEN=...
WDFWATCH_REFRESH_TOKEN=...
```

### Required for WebUI:
```bash
DATABASE_URL=postgresql://...
ENCRYPTION_KEY=...  # For API key storage
WEB_API_KEY=...  # For Python<->Web communication
PYTHON_PATH=/home/debian/Tools/WDFWatch/venv/bin/python  # Use venv Python
```

### Required for Tweet Queue (UPDATED 2025-01-05):
```bash
WDFWATCH_MODE=true
WDF_DEBUG=false
WDF_WEB_MODE=true
WDF_BYPASS_QUOTA_CHECK=true  # Match Draft Review
WDF_MOCK_MODE=false  # Force real Twitter API
WDF_REDIS_URL=redis://localhost:6379/0  # Ensure Redis connection
```

### Claude CLI:
```bash
PATH=/home/debian/.claude/local:$PATH
CLAUDE_CLI_PATH=/home/debian/.claude/local/claude
```

---

## EXECUTION TIMELINE (Typical Episode)

```
Time  | Stage              | Output
------|--------------------|---------------------------------
00:00 | Upload Transcript  | podcast_episodes row created
00:01 | Spawn Pipeline     | Python subprocess starts
00:02 | Summarization      | summary.md (15-30s)
00:32 | Keyword Extract    | keywords.json
00:33 | Tweet Scraping     | tweets.json (100 tweets)
01:03 | Classification     | classified.json (20 relevant)
01:23 | Response Gen       | responses.json → draft_replies
01:53 | Draft Review       | Human reviews in WebUI
02:00 | First Approval     | Posted to Twitter immediately
02:01 | Bulk Approve       | 19 drafts → tweet_queue
02:02 | Process Queue      | Tokens refreshed
02:03 | Tweet 1           | Posted (success)
02:48 | Tweet 2           | Posted (45s delay)
03:33 | Tweet 3           | Posted (45s delay) + Token refresh
...
17:03 | Tweet 19          | Posted (45s × 19 = 14.25 min)
17:04 | Complete          | All drafts posted
```

Total time: ~17 minutes for full episode processing + posting
**NEW:** Tokens now refresh at 90s, 180s, 270s, etc. to prevent auth failures

---

## FILES INVOLVED (Complete List)

### Frontend (Next.js):
- `web/app/(dashboard)/episodes/page.tsx`
- `web/app/(dashboard)/review/page.tsx`
- `web/app/(dashboard)/tweet-queue/page.tsx` **← UPDATED 2025-01-05 (timeout fix)**
- `web/app/api/episodes/[id]/claude-pipeline/run/route.ts`
- `web/app/api/drafts/[id]/approve/route.ts` **← UPDATED 2025-01-05 (execFile)**
- `web/app/api/drafts/[id]/reject/route.ts`
- `web/app/api/tweet-queue/process/route.ts` **← UPDATED 2025-01-05 (all fixes)**
- `web/components/drafts/DraftReviewPanel.tsx`
- `web/components/drafts/DraftEditor.tsx`
- `web/lib/db.ts` **← Now used by both routes**
- `web/lib/prisma.ts`

### Backend (Python):
- `claude-pipeline/orchestrator.py`
- `claude-pipeline/stages/summarize.py`
- `claude-pipeline/stages/classify.py`
- `claude-pipeline/stages/respond.py`
- `claude-pipeline/stages/moderate.py`
- `claude-pipeline/core/episode_manager.py`
- `claude-pipeline/core/unified_interface.py`
- `claude-pipeline/core/model_factory.py`
- `claude-pipeline/core/claude_adapter.py`
- `web/scripts/web_bridge.py`
- `scripts/safe_twitter_reply.py`
- `scripts/ensure_fresh_tokens.py`
- `src/wdf/tasks/scrape.py`
- `src/wdf/twitter_api_v2.py` **← UPDATED 2025-01-05 (structured errors)**

### Configuration:
- `claude-pipeline/CLAUDE.md` (master context)
- `claude-pipeline/specialized/classifier/CLAUDE.md`
- `claude-pipeline/specialized/responder/CLAUDE.md`
- `claude-pipeline/specialized/moderator/CLAUDE.md`
- `claude-pipeline/specialized/summarizer/CLAUDE.md`

---

## SUMMARY

The WDFWatch WebUI is a **hybrid architecture**:
- **Filesystem-first** for pipeline stages (summary, tweets, classifications)
- **Database-first** for user interactions (drafts, queue, approvals)
- **Dual-write** for tweet data (filesystem + database)

**Critical Success Factors:**
1. Responses MUST be synced to database via `sync_responses_to_database()`
2. OAuth tokens MUST be refreshed every 90s during batch posting (UPDATED 2025-01-05)
3. Episodes MUST have `claudeEpisodeDir` set to episode directory name
4. Draft approvals immediately post to Twitter (no queueing unless error)
5. Queue processing handles rate limits gracefully (45s delays, auto-stop on 429)
6. **Use `execFile()` for Python subprocess calls, NOT `exec()`** (prevents shell escaping issues)
7. **Python path MUST point to venv Python, not system Python**
8. **Environment variables MUST be consistent between Draft Review and Tweet Queue**
9. **Only retryable errors count toward consecutive failure limit** (excludes deleted tweets, reply restrictions, duplicates, rate limits)
10. **Frontend timeout MUST be longer than backend maximum processing time** (35 min vs 30 min)

**Data Flow:**
`Transcript → Summary → Tweets → Classifications → Responses → Drafts → Queue → Twitter`

Each arrow represents both filesystem writes AND database updates (where applicable)

**Bug Fix Success Metrics (2025-01-05):**
- Expected success rate: >95% (up from 30-50%)
- Token expiration eliminated in batch processing
- Shell escaping issues eliminated with execFile
- Special characters preserved correctly in all tweets
- Queue continues processing valid tweets despite encountering deleted/restricted tweets
- Consistent behavior across all message formats
- Frontend no longer times out during long batch jobs