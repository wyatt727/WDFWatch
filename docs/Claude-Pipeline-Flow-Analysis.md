# Claude Pipeline Stage Execution Flow Analysis

## Overview
This document details the exact data flow and file management when running individual Claude pipeline stages from the Web UI, based on a comprehensive investigation of the codebase.

## Current Architecture

### Web UI to Pipeline Bridge
1. **Web UI Trigger**: User clicks "Run" on a specific stage in the Web UI
2. **API Route**: `/api/episodes/[id]/claude-pipeline/run` handles the request
3. **Bridge Script**: Spawns `claude_pipeline_bridge.py` as a subprocess
4. **Orchestrator Call**: Bridge calls `orchestrator.py` via subprocess with stage parameter
5. **Stage Execution**: Orchestrator runs the specific stage method

### Directory Structure
The Claude pipeline maintains two parallel directory structures:

#### 1. Episode-Specific Directories
```
claude-pipeline/episodes/episode_{id}/
├── transcript.txt          # Original transcript
├── summary.md              # Generated summary (serves as context)
├── keywords.json           # Extracted keywords for search
├── tweets.json            # Scraped/loaded tweets
├── classified.json        # Classification results
├── responses.json         # Generated responses
├── video_url.txt          # YouTube URL
├── metadata.json          # Episode metadata and stage tracking
└── pipeline_results.json  # Full pipeline results
```

#### 2. Legacy Transcripts Directory (Backward Compatibility)
```
transcripts/
├── latest.txt             # Current transcript
├── podcast_overview.txt   # Podcast description
├── summary.md             # Latest summary (duplicated)
├── keywords.json          # Latest keywords (duplicated)
├── tweets.json           # Default tweet source
├── classified.json       # Latest classifications
└── responses.json        # Latest responses
```

## Stage-by-Stage Data Flow

### Stage 1: Summarization (`summarize`)

**Inputs:**
- `transcript.txt` - From episode directory if exists, otherwise from `transcripts/latest.txt`
- `podcast_overview.txt` - From transcripts directory

**Process:**
1. Creates new episode directory if not exists (`episodes/episode_{id}/`)
2. Saves transcript to episode directory
3. Creates placeholder `summary.md` and `keywords.json` BEFORE Claude call
4. Calls Claude API to generate comprehensive summary
5. Extracts keywords from summary or generates separately
6. Updates episode metadata

**Outputs:**
- `episodes/episode_{id}/summary.md` - Comprehensive 3000-5000 word summary
- `episodes/episode_{id}/keywords.json` - 25-30 search keywords
- `transcripts/summary.md` - Duplicate for backward compatibility
- `transcripts/keywords.json` - Duplicate for backward compatibility

**Key Finding:** The summarizer explicitly sets `episode_id=None` when calling Claude to avoid loading placeholder files as context.

### Stage 2: Classification (`classify`)

**Inputs:**
- `episodes/episode_{id}/tweets.json` - If exists in episode directory
- `transcripts/tweets.json` - Fallback if episode tweets don't exist
- `episodes/episode_{id}/summary.md` - Used as context via CLAUDE.md

**Process:**
1. Sets episode context (loads episode's CLAUDE.md)
2. Loads tweets from episode directory first, falls back to `transcripts/tweets.json`
3. Batch classifies tweets using Claude's direct scoring (0.00-1.00)
4. Marks tweets as RELEVANT (≥0.70) or SKIP (<0.70)
5. Saves classification results

**Outputs:**
- `episodes/episode_{id}/classified.json` - Tweet objects with:
  - `relevance_score`: Float between 0.00 and 1.00
  - `classification`: "RELEVANT" or "SKIP"
  - `classification_method`: "claude_direct"
  - `classification_reason`: Optional reasoning

**Current Behavior:**
- Without Twitter API key, uses pre-generated tweets from `transcripts/tweets.json`
- These tweets are copied to episode directory during classification
- All episodes currently share the same tweet set

### Stage 3: Response Generation (`respond`)

**Inputs:**
- `episodes/episode_{id}/classified.json` - Relevant tweets only
- `episodes/episode_{id}/summary.md` - Episode context
- `episodes/episode_{id}/video_url.txt` - YouTube URL to include

**Process:**
1. Loads only RELEVANT tweets from classified.json
2. Sets episode context (loads full CLAUDE.md with summary)
3. Processes tweets in batches of 25
4. Generates responses under 200 characters
5. Validates and cleans responses (removes emojis, ensures length)

**Outputs:**
- `episodes/episode_{id}/responses.json` - Tweet objects with:
  - Original tweet data
  - `response`: Generated response text
  - `response_length`: Character count
  - `response_method`: "claude_batch"

### Stage 4: Moderation (`moderate`)

**Inputs:**
- `episodes/episode_{id}/responses.json` - All generated responses

**Process:**
1. Loads pending responses
2. Evaluates quality scores (relevance, engagement, etc.)
3. Marks responses as approved/rejected
4. Generates quality report

**Outputs:**
- `episodes/episode_{id}/published.json` - Approved responses ready for posting
- Updated metadata with moderation statistics

## Critical Implementation Details

### 1. Episode Context Management
- Each episode has its own CLAUDE.md created from the master template
- The summary.md file serves as the primary episode context
- Context is loaded via `UnifiedInterface.set_episode_context()` before each stage

### 2. Tweet Source Without API
Currently, without Twitter API credentials:
- All episodes use the same pre-generated tweets from `transcripts/tweets.json`
- These are 50 mock tweets with a mix of relevant and irrelevant content
- The same tweets are copied to each episode directory during classification

### 3. File Duplication Strategy
The pipeline maintains backward compatibility by:
- Writing to both episode directory and transcripts directory
- Episode directory is the source of truth
- Transcripts directory maintains latest run for legacy tools

### 4. Stage Dependencies
- **Summarization**: Can run independently
- **Classification**: Requires summary.md and tweets (from file or API)
- **Response**: Requires classified.json with RELEVANT tweets
- **Moderation**: Requires responses.json

## Web UI Integration Points

### 1. Status Updates
The bridge emits SSE events at key points:
- `pipeline_stage_started`
- `pipeline_stage_completed`
- `pipeline_stage_error`

### 2. Database Synchronization
- Episode metadata stored in PostgreSQL
- Pipeline runs tracked in `claude_pipeline_runs` table
- Cost tracking integrated with API usage

### 3. Configuration Loading
The bridge loads from database:
- LLM model configuration per task
- Stage enable/disable settings
- API keys (when available)

## Recommendations for API Integration

When Twitter API key becomes available:

1. **Modify Tweet Loading**:
   - Implement actual Twitter scraping in `_scrape_tweets()`
   - Use keywords from `episodes/episode_{id}/keywords.json`
   - Save scraped tweets to episode directory

2. **Prevent Tweet Sharing**:
   - Each episode should have unique tweets based on its keywords
   - Remove fallback to `transcripts/tweets.json` for new episodes

3. **Add Tweet Caching**:
   - Implement age-based cache to avoid re-scraping
   - Store tweet metadata (scrape time, keywords used)

## Testing Checklist

- [x] Summarization creates episode directory structure
- [x] Classification loads tweets from correct location
- [x] Response generation uses episode-specific context
- [x] Files saved to episode directory
- [x] Backward compatibility maintained with transcripts/
- [ ] Web UI status updates working
- [ ] Database synchronization verified
- [ ] Cost tracking accurate

## Conclusion

The Claude pipeline is correctly structured for individual stage execution from the Web UI. The main limitation is the current use of pre-generated tweets due to missing API credentials. Once the API key is available, each episode will have unique, keyword-based tweets, making the pipeline fully functional for production use.

The architecture properly separates episodes with self-contained contexts while maintaining backward compatibility with the legacy file structure.