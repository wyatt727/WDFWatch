# Hybrid Context System Guide

## Overview

The WDFWatch Claude pipeline uses a hybrid context approach that combines **specialized task instructions** with **episode-specific context**. This design preserves the precision of specialized instructions while providing rich episode information.

## Architecture

### Specialized Instructions
Located in `claude-pipeline/specialized/*/CLAUDE.md`:

- **classifier/CLAUDE.md** - Precise tweet relevancy scoring criteria
- **responder/CLAUDE.md** - Response generation rules and constraints  
- **moderator/CLAUDE.md** - Quality evaluation framework
- **summarizer/CLAUDE.md** - Episode analysis guidelines

### Episode Context
Located in `episodes/episode_*/EPISODE_CONTEXT.md`:

- Guest information and credentials
- Key themes discussed in the episode
- Memorable quotes from the episode
- Keywords for tweet discovery
- Episode video URL

## How It Works

### Claude CLI Integration
Each pipeline operation uses dual @ file references:

```bash
# Classification
claude --model sonnet \
  @claude-pipeline/specialized/classifier/CLAUDE.md \
  @episodes/episode_123/EPISODE_CONTEXT.md \
  @prompt.txt

# Response Generation
claude --model sonnet \
  @claude-pipeline/specialized/responder/CLAUDE.md \
  @episodes/episode_123/EPISODE_CONTEXT.md \
  @prompt.txt

# Quality Moderation
claude --model sonnet \
  @claude-pipeline/specialized/moderator/CLAUDE.md \
  @episodes/episode_123/EPISODE_CONTEXT.md \
  @prompt.txt
```

### Pipeline Integration
The `ClaudeInterface` class automatically manages context loading:

```python
# Set episode context
claude.set_episode_context("episode_123")

# Call with mode - automatically uses specialized + episode context
response = claude.call(
    prompt="Classify this tweet about state sovereignty",
    mode="classify",  # Uses classifier/CLAUDE.md
    episode_id="episode_123"  # Uses episode_123/EPISODE_CONTEXT.md
)
```

## Benefits

### 1. Specialized Precision
Each task gets exact instructions tailored for its purpose:
- Classification gets precise scoring criteria (0.85-1.00 for highly relevant)
- Response generation gets specific rules about character limits and tone
- Moderation gets detailed evaluation frameworks

### 2. Rich Episode Context  
Each episode provides detailed context:
- Guest expertise and background
- Specific themes and arguments discussed
- Memorable quotes for reference
- Keywords that worked for discovery

### 3. No Instruction Dilution
Unlike a unified approach, specialized instructions remain:
- Sharp and focused on their specific task
- Easy to update in one place
- Consistent across all episodes

### 4. Maintainable
- Update task instructions in `specialized/*/CLAUDE.md` 
- Episode context is automatically generated
- No need to touch individual episodes when updating instructions

## Example: Tweet Classification

### Specialized Instructions (`specialized/classifier/CLAUDE.md`)
```markdown
# WDF Podcast Tweet Relevancy Classifier

## CLASSIFICATION CRITERIA
### HIGHLY RELEVANT (0.85-1.00)
- Directly discusses federalism, state sovereignty, or constitutional issues
- Mentions specific topics from the current episode
- Expresses frustration with federal overreach
...
```

### Episode Context (`episodes/episode_123/EPISODE_CONTEXT.md`)
```markdown
# Episode Context: 20250112_abc123

## GUEST INFORMATION
**Name**: Daniel Miller
**Organization**: Texas Nationalist Movement

## KEY THEMES DISCUSSED
1. Texas independence movement
2. Federal overreach in border policy
3. State nullification as remedy

## MEMORABLE QUOTES
- "The federal government has become what the founders feared"
- "States have a natural right to self-determination"
...
```

### Result
Claude gets both:
1. **Precise scoring instructions** - knows exactly how to score tweets
2. **Rich episode context** - knows this episode discussed Texas independence with Daniel Miller

This results in highly accurate, context-aware classification that references specific episode content.

## File Management

### Creating Episode Context
The `EpisodeManager` automatically creates `EPISODE_CONTEXT.md`:

```python
# Creates episode directory with initial context file
episode_mgr.create_episode(transcript, episode_id="test_001")

# Updates context file with rich episode information
episode_mgr.update_episode_context(
    episode_id="test_001",
    summary="Analysis of Texas independence with Daniel Miller...",
    keywords=["Texas", "independence", "federalism"],
    video_url="https://youtube.com/watch?v=abc123"
)
```

### Updating Specialized Instructions
Edit files in `claude-pipeline/specialized/*/CLAUDE.md` directly:

```bash
# Update classification criteria
vim claude-pipeline/specialized/classifier/CLAUDE.md

# Update response generation rules  
vim claude-pipeline/specialized/responder/CLAUDE.md
```

Changes immediately apply to all future operations.

## Best Practices

### 1. Keep Contexts Separate
- **Specialized files**: Task instructions only
- **Episode context**: Episode information only
- Don't mix task instructions into episode context

### 2. Review Generated Context
- Check `EPISODE_CONTEXT.md` after summarization
- Ensure guest information and themes are accurate
- Verify video URL is included

### 3. Update Specialized Instructions
- Refine scoring criteria based on results
- Adjust response rules based on quality feedback
- Keep instructions precise and specific

### 4. Test Changes
- Use `test_hybrid_approach.py` to verify context loading
- Test individual stages with updated instructions
- Monitor quality metrics after changes

## Migration Notes

This hybrid approach evolved from an earlier unified approach where each episode had a complete `CLAUDE.md` file. The problem was instruction dilution - specialized instructions became generic and lost precision.

The hybrid approach solves this by:
- Keeping specialized expertise in dedicated files
- Providing rich episode context separately  
- Using Claude's native @ file syntax for dual context loading

This gives Claude the best of both worlds: **precise task instructions** AND **comprehensive episode context**.