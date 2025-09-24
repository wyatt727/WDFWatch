# Episode Directory Structure - Hybrid Context Design

## Evolution: From Unified to Hybrid

Initially we tried a unified approach where each episode had its own complete CLAUDE.md file. However, this diluted the precision of task-specific instructions. The hybrid approach preserves specialized expertise while providing rich episode context.

## Current Solution: Hybrid Context Architecture

```
claude-pipeline/
├── specialized/                       # Task-specific instructions
│   ├── classifier/CLAUDE.md          # Precise scoring criteria (0.85-1.00 etc.)
│   ├── responder/CLAUDE.md           # Response generation rules
│   ├── moderator/CLAUDE.md           # Quality evaluation framework
│   └── summarizer/CLAUDE.md          # Episode analysis guidelines
│
episodes/
├── episode_20250112_abc123/           # Each episode gets its own directory
│   ├── EPISODE_CONTEXT.md            # Episode-specific context ONLY
│   ├── transcript.txt                # Original transcript
│   ├── summary.md                    # Generated summary
│   ├── keywords.json                 # Extracted keywords
│   ├── video_url.txt                 # YouTube URL
│   ├── tweets.json                   # Scraped tweets
│   ├── classified.json               # Classification results
│   ├── responses.json                # Generated responses
│   ├── published.json                # Approved responses
│   └── metadata.json                 # Episode metadata
│
├── episode_20250113_def456/
│   ├── EPISODE_CONTEXT.md            # Different episode, different context
│   ├── transcript.txt
│   └── ...
│
└── current -> episode_20250113_def456 # Symlink to current episode
```

## Key Benefits

1. **Self-Contained Episodes**: Everything for an episode in one place
2. **Simple Claude Usage**: Just `cd` to episode directory and Claude reads local `CLAUDE.md`
3. **No Path Confusion**: All files are relative to episode directory
4. **Easy Archival**: Just zip/move entire episode directory
5. **Parallel Processing**: Can work on multiple episodes simultaneously

## How CLAUDE.md Works

### Master Template (`claude-pipeline/CLAUDE_TEMPLATE.md`)
```markdown
# WDF Podcast AI System

## YOUR IDENTITY
[Base instructions for all episodes]

## EPISODE CONTEXT
[This section will be replaced with episode-specific content]
```

### Episode-Specific (`episodes/episode_123/CLAUDE.md`)
```markdown
# WDF Podcast AI System

## YOUR IDENTITY
[Base instructions for all episodes]

## EPISODE CONTEXT

### Guest: Daniel Miller
### Organization: Texas Nationalist Movement
### Episode Date: 2025-01-12

### KEY THEMES
1. Texas independence movement
2. Federal overreach examples
3. Peaceful secession framework

### MEMORABLE QUOTES
- "The federal government has become what the founders feared most"
- "States have a natural right to self-determination"

### VIDEO URL
https://youtube.com/watch?v=abc123

### KEYWORDS FOR MATCHING
Texas, secession, Daniel Miller, state sovereignty, federal overreach...
```

## Implementation Changes

### Episode Manager Class
```python
class EpisodeManager:
    def __init__(self, episodes_dir: Path = "episodes"):
        self.episodes_dir = Path(episodes_dir)
        self.episodes_dir.mkdir(exist_ok=True)
        
    def create_episode(self, transcript: str) -> str:
        """Create new episode directory with structure."""
        episode_id = self._generate_id(transcript)
        episode_dir = self.episodes_dir / f"episode_{episode_id}"
        episode_dir.mkdir(exist_ok=True)
        
        # Save transcript
        (episode_dir / "transcript.txt").write_text(transcript)
        
        # Create base CLAUDE.md from template
        template = Path("CLAUDE_TEMPLATE.md").read_text()
        (episode_dir / "CLAUDE.md").write_text(template)
        
        # Update current symlink
        current_link = self.episodes_dir / "current"
        if current_link.exists():
            current_link.unlink()
        current_link.symlink_to(episode_dir)
        
        return episode_id
    
    def update_claude_context(self, episode_id: str, summary: str, keywords: List[str]):
        """Update episode's CLAUDE.md with extracted context."""
        episode_dir = self.episodes_dir / f"episode_{episode_id}"
        
        # Build episode-specific context
        context = self._build_context(summary, keywords)
        
        # Update CLAUDE.md
        template = Path("CLAUDE_TEMPLATE.md").read_text()
        full_context = template.replace("[EPISODE CONTEXT]", context)
        (episode_dir / "CLAUDE.md").write_text(full_context)
```

### Claude Interface Changes
```python
class ClaudeInterface:
    def call(self, prompt: str, episode_dir: Path = None):
        """Call Claude with episode-specific context."""
        
        # If episode directory provided, use its CLAUDE.md
        if episode_dir:
            context_file = episode_dir / "CLAUDE.md"
        else:
            context_file = Path("CLAUDE.md")  # Use current directory
        
        cmd = [
            "claude",
            "--model", "sonnet",
            f"@{context_file}",
            prompt
        ]
        
        # Claude automatically uses the episode-specific context!
```

## Migration Path

1. Create `episodes/` directory structure
2. Move existing transcripts to episode directories
3. Generate CLAUDE.md for each episode from summaries
4. Update all scripts to work with episode directories
5. Use `current` symlink for backward compatibility

## Decision: YES, This is Worth It!

This architecture is much cleaner because:
1. **Natural Organization**: Episodes are naturally self-contained units
2. **Simple Context**: Just one CLAUDE.md per episode, no complex naming
3. **Claude Native**: Works exactly how Claude expects (local CLAUDE.md)
4. **Future Proof**: Easy to add more episode-specific files later
5. **Parallel Work**: Can process multiple episodes without conflicts

The only downside is changing existing code, but the benefits far outweigh the migration cost.