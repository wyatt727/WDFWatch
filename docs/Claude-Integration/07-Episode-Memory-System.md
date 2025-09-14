# Episode Memory System - Episode Directories with CLAUDE.md Files

## Executive Summary

The WDFWatch Claude pipeline uses a revolutionary memory system where **each episode gets its own directory with its own CLAUDE.md file**. This eliminates complex memory management and works naturally with how Claude reads context files.

## Core Concept: Episodes as Self-Contained Units

### Traditional Approach (What We're NOT Doing)
```
❌ JSON memory files that need loading and formatting
❌ Complex context building from database
❌ Passing context strings to Claude
❌ Managing episode_123_CLAUDE.md with awkward naming
```

### Our Approach: Episode Directories with CLAUDE.md
```
✅ Each episode has its own directory
✅ Each directory contains CLAUDE.md with full context
✅ Claude reads the local CLAUDE.md file directly
✅ No complex memory management needed
```

## Directory Structure

```
episodes/
├── episode_20250112_abc123/           # Complete episode package
│   ├── CLAUDE.md                      # THE MEMORY - Episode-specific context
│   ├── transcript.txt                 # Original transcript
│   ├── summary.md                     # Generated summary
│   ├── keywords.json                  # Extracted keywords
│   ├── video_url.txt                  # YouTube URL
│   ├── tweets.json                    # Scraped tweets
│   ├── classified.json                # Classification results
│   ├── responses.json                 # Generated responses
│   ├── published.json                 # Approved responses
│   └── metadata.json                  # Episode metadata
│
├── episode_20250113_def456/
│   ├── CLAUDE.md                      # Different episode = different context
│   └── ...
│
└── current -> episode_20250113_def456 # Symlink to active episode
```

## How CLAUDE.md Serves as Memory

### What Goes in Episode CLAUDE.md

Each episode's CLAUDE.md contains:

1. **Base Instructions** (from template)
   - Claude's identity and role
   - Podcast information
   - Operating modes
   - Quality standards

2. **Episode-Specific Memory** (the actual memory)
   - Guest information
   - Key themes discussed
   - Memorable quotes
   - Controversial points
   - Solutions proposed
   - Keywords for matching
   - Video URL
   - Context usage guidelines

### Example Episode CLAUDE.md

```markdown
# WDF Podcast AI System - Master Context

## YOUR IDENTITY
You are the comprehensive AI system for the War, Divorce, or Federalism podcast...
[Base instructions]

## EPISODE CONTEXT

### Episode ID: 20250112_abc123
*Generated: 2025-01-12 14:30:00*

## GUEST INFORMATION
**Name**: Daniel Miller
**Title**: President
**Organization**: Texas Nationalist Movement
**Expertise**: Constitutional law, state sovereignty, peaceful secession

## KEY THEMES DISCUSSED
1. Texas independence movement and legal framework
2. Federal overreach in border policy
3. State nullification as constitutional remedy
4. Economic viability of independent Texas
5. Peaceful separation vs violent conflict

## MEMORABLE QUOTES
- "The federal government has become what the founders feared most"
- "Texas has both the moral and legal right to self-determination"
- "We're not talking about war, we're talking about a vote"

## CONTROVERSIAL POINTS
1. States have the right to secede peacefully
2. Federal government has violated the constitutional compact
3. Texas could thrive as an independent nation

## KEYWORDS FOR DISCOVERY
Texas, secession, Daniel Miller, state sovereignty, federal overreach, 
nullification, TEXIT, constitutional crisis, border security, tenth amendment...

## EPISODE VIDEO
**URL**: https://youtube.com/watch?v=abc123
*Always include this URL in tweet responses*

## CONTEXT USAGE

### For Classification
- Prioritize tweets about Texas independence and state sovereignty
- Higher scores for tweets mentioning Daniel Miller or TNM
- Consider federal overreach discussions highly relevant

### For Response Generation
- Reference Daniel Miller by name when appropriate
- Use quotes about self-determination
- Connect to Texas-specific issues
- Always include the video URL
```

## Memory Creation Pipeline

### Step 1: Episode Creation
```python
episode_manager = EpisodeManager()
episode_info = episode_manager.create_episode(
    transcript=transcript_text,
    video_url="https://youtube.com/watch?v=abc123"
)
# Creates: episodes/episode_20250112_abc123/
# With: CLAUDE.md (template), transcript.txt, metadata.json
```

### Step 2: Summarization Updates Memory
```python
summarizer = Summarizer(claude_interface)
result = summarizer.summarize(
    transcript=transcript_text,
    episode_id=episode_id
)
# Updates: episodes/episode_20250112_abc123/CLAUDE.md
# With: Guest info, themes, quotes, keywords extracted from summary
```

### Step 3: All Stages Use Episode Memory
```python
# Classification
classifier = Classifier(claude_interface)
classifier.classify(tweets, episode_id)
# Claude reads: episodes/episode_20250112_abc123/CLAUDE.md

# Response Generation
responder = ResponseGenerator(claude_interface)
responder.generate(tweet, episode_id)
# Claude reads: episodes/episode_20250112_abc123/CLAUDE.md

# Quality Moderation
moderator = QualityModerator(claude_interface)
moderator.moderate(response, tweet, episode_id)
# Claude reads: episodes/episode_20250112_abc123/CLAUDE.md
```

## How Claude Uses the Memory

### Simple and Direct
```python
# When working with an episode, Claude just reads the local CLAUDE.md
cmd = [
    "claude",
    "--model", "sonnet",
    f"@episodes/episode_{episode_id}/CLAUDE.md",
    prompt
]
```

### No Complex Memory Management
- No JSON parsing
- No context building
- No string formatting
- No memory loading
- Just read the file!

## Benefits of This Approach

### 1. **Simplicity**
- One file per episode contains everything
- Claude native format (markdown)
- No translation layer needed

### 2. **Persistence**
- Memory persists as a file
- Easy to backup and restore
- Human-readable and editable

### 3. **Isolation**
- Each episode completely separate
- No cross-contamination
- Parallel processing possible

### 4. **Debugging**
- Can read CLAUDE.md to see exact context
- Easy to modify for testing
- Clear audit trail

### 5. **Performance**
- No runtime memory building
- Direct file reading
- Cacheable by Claude

## Memory Lifecycle

### Creation
1. Episode directory created
2. Base CLAUDE.md copied from template
3. Transcript saved

### Enhancement
1. Summary generated
2. Information extracted
3. CLAUDE.md updated with episode context

### Usage
1. All pipeline stages read episode's CLAUDE.md
2. Claude has full context automatically
3. No memory management needed

### Archival
1. Complete episode directory can be zipped
2. Includes all context and outputs
3. Can be restored by unzipping

## Comparison with Traditional Memory Systems

| Aspect | Traditional JSON Memory | Our CLAUDE.md Approach |
|--------|------------------------|------------------------|
| Storage | JSON files with structured data | Markdown files with formatted context |
| Loading | Parse JSON, build context strings | Read file directly |
| Format | Programming data structure | Human and Claude readable |
| Management | Complex memory classes | Simple file operations |
| Debugging | Need to inspect JSON | Read CLAUDE.md directly |
| Persistence | Requires serialization | Already persisted |
| Claude Integration | Build prompts with context | Native @file support |

## Implementation Details

### EpisodeManager Class
```python
class EpisodeManager:
    """Manages episode directories with CLAUDE.md memories."""
    
    def create_episode(self, transcript: str) -> str:
        """Create episode directory with initial CLAUDE.md."""
        
    def update_episode_context(self, episode_id: str, summary: str):
        """Update episode's CLAUDE.md with extracted context."""
        
    def get_episode_dir(self, episode_id: str) -> Path:
        """Get path to episode directory."""
```

### ClaudeInterface Integration
```python
class ClaudeInterface:
    """Uses episode CLAUDE.md files for context."""
    
    def call(self, prompt: str, episode_id: str):
        """Call Claude with episode-specific CLAUDE.md."""
        episode_dir = f"episodes/episode_{episode_id}"
        context_file = f"{episode_dir}/CLAUDE.md"
        # Claude reads the episode's memory directly!
```

## Best Practices

### 1. One Episode = One Directory
- Never mix episode files
- Keep everything self-contained
- Use consistent naming

### 2. CLAUDE.md is THE Memory
- This file IS the episode memory
- All context goes here
- Keep it updated and accurate

### 3. Template Management
- Maintain master template
- Update template for all episodes
- Episode-specific content clearly marked

### 4. Archival Strategy
- Zip old episodes
- Keep recent episodes ready
- Clean up periodically

## Conclusion

By using episode directories with CLAUDE.md files as our memory system, we achieve:
- **Maximum Simplicity**: Just files, no complex systems
- **Perfect Integration**: Claude reads context naturally
- **Complete Isolation**: Each episode is independent
- **Easy Management**: Standard file operations
- **Full Transparency**: Human-readable memories

This approach eliminates the complexity of traditional memory systems while providing superior functionality. The episode's CLAUDE.md file IS the memory - simple, powerful, and elegant.