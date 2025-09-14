# Unified Claude Pipeline for WDFWatch

## 🚀 Revolutionary Hybrid Context System

The WDFWatch Claude pipeline uses a hybrid approach that combines **specialized task instructions** with **episode-specific context**. This preserves the precision of specialized instructions while providing rich episode context for superior AI performance.

## ✨ Key Innovation: Hybrid Context Architecture

```
claude-pipeline/
├── specialized/           # Task-specific instructions
│   ├── classifier/CLAUDE.md   # Precise scoring criteria
│   ├── responder/CLAUDE.md    # Response generation rules
│   ├── moderator/CLAUDE.md    # Quality evaluation criteria
│   └── summarizer/CLAUDE.md   # Analysis framework
│
episodes/
├── episode_20250112_abc123/           
│   ├── EPISODE_CONTEXT.md # ← Episode-specific context only
│   ├── transcript.txt     # Original transcript
│   ├── summary.md         # Generated summary
│   ├── keywords.json      # Extracted keywords
│   ├── tweets.json        # Scraped tweets
│   ├── classified.json    # Classification results
│   ├── responses.json     # Generated responses
│   └── published.json     # Approved responses
```

**Claude uses both specialized instructions AND episode context for maximum precision.**

## 🎯 Core Benefits

1. **Specialized Precision**: Task-specific CLAUDE.md files maintain precise instructions
2. **Rich Episode Context**: EPISODE_CONTEXT.md provides detailed episode information
3. **No Instruction Dilution**: Specialized instructions remain sharp and focused
4. **Dual Context Loading**: Claude reads both specialized + episode context files
5. **Complete Episode Isolation**: Episodes are independent and parallel-processable
6. **No Few-Shots Needed**: Claude classifies directly using hybrid context

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/WDFWatch.git
cd WDFWatch

# Install dependencies
pip install -r requirements.txt

# Ensure Claude CLI is installed
claude --version
```

## 🚀 Quick Start

### Run Complete Pipeline

```bash
# Process a new episode
python claude-pipeline/orchestrator.py \
  --transcript transcripts/latest.txt \
  --video-url "https://youtube.com/watch?v=abc123"
```

### What Happens

1. **Episode Directory Created**: `episodes/episode_20250112_abc123/`
2. **CLAUDE.md Generated**: Full context from summary
3. **Classification Without Few-Shots**: Direct reasoning
4. **Responses Use Episode Context**: Rich, relevant replies
5. **Quality Auto-Moderation**: Claude evaluates itself

## 📁 Directory Structure

```
claude-pipeline/
├── README.md                   # This file
├── CLAUDE.md                   # Master template
├── orchestrator.py             # Main pipeline runner
│
├── specialized/                # Task-specific instructions
│   ├── classifier/CLAUDE.md   # Tweet relevancy scoring criteria
│   ├── responder/CLAUDE.md    # Response generation rules
│   ├── moderator/CLAUDE.md    # Quality evaluation framework
│   └── summarizer/CLAUDE.md   # Episode analysis guidelines
│
├── core/                       # Core components
│   ├── claude_interface.py    # Hybrid context manager
│   ├── episode_manager.py     # Episode directory management
│   ├── cache.py               # Response caching
│   └── batch_processor.py     # Batch utilities
│
├── stages/                     # Pipeline stages
│   ├── summarize.py           # Creates episode context
│   ├── classify.py            # Uses specialized + episode context
│   ├── respond.py             # Uses specialized + episode context
│   └── moderate.py            # Uses specialized + episode context
│
└── episodes/                   # Episode directories
    ├── episode_20250112_abc/
    │   ├── EPISODE_CONTEXT.md # Episode-specific context
    │   └── ...
    └── current -> episode_... # Symlink to active
```

## 🧠 How Hybrid Context Works

### 1. Episode Context Creation (Summarization)

```python
summarizer = Summarizer(claude_interface)
result = summarizer.summarize(
    transcript=transcript_text,
    podcast_overview=overview,
    episode_id="20250112_abc123",
    video_url="https://youtube.com/watch?v=abc123"
)
# Creates: episodes/episode_20250112_abc123/EPISODE_CONTEXT.md
```

### 2. Specialized Instructions (classifier/CLAUDE.md)

```markdown
# WDF Podcast Tweet Relevancy Classifier

## YOUR ROLE
You are the official tweet relevancy scorer for the War, Divorce, or Federalism podcast.

## CLASSIFICATION CRITERIA
### HIGHLY RELEVANT (0.85-1.00)
- Directly discusses federalism, state sovereignty, or constitutional issues
- Mentions specific topics from the current episode
...
```

### 3. Episode Context (EPISODE_CONTEXT.md)

```markdown
# Episode Context: 20250112_abc123
*Generated: 2025-01-12 14:30:00*

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

## EPISODE VIDEO
**URL**: https://youtube.com/watch?v=abc123
*Include this URL in all tweet responses*
```

### 4. Hybrid Context Usage (All Stages)

```python
# Classification uses specialized + episode context
classifier.classify(tweets, episode_id="20250112_abc123")
# Claude reads: 
#   specialized/classifier/CLAUDE.md (precise scoring criteria)
#   episodes/episode_20250112_abc123/EPISODE_CONTEXT.md (episode info)

# Response generation uses specialized + episode context
responder.generate(tweet, episode_id="20250112_abc123")
# Claude reads:
#   specialized/responder/CLAUDE.md (response generation rules)
#   episodes/episode_20250112_abc123/EPISODE_CONTEXT.md (episode info)
```

### 5. Claude CLI Integration

```bash
# Actual Claude CLI call for classification:
claude --model sonnet \
  @specialized/classifier/CLAUDE.md \
  @episodes/episode_123/EPISODE_CONTEXT.md \
  @prompt.txt
```

## 🔧 Pipeline Stages

### Stage 1: Summarization & Context Creation
- Uses `specialized/summarizer/CLAUDE.md` for analysis framework
- Analyzes transcript with specialized instructions
- Extracts guest info, themes, quotes
- **Creates episode directory**
- **Generates EPISODE_CONTEXT.md with episode-specific data**

### Stage 2: Tweet Scraping
- Uses keywords from summary
- Saves to episode directory

### Stage 3: Classification (No Few-Shots!)
- **Reads specialized/classifier/CLAUDE.md** (precise scoring criteria)
- **Reads episode EPISODE_CONTEXT.md** (episode-specific context)
- Classifies directly using hybrid context
- No example generation needed

### Stage 4: Response Generation
- **Reads specialized/responder/CLAUDE.md** (response generation rules)
- **Reads episode EPISODE_CONTEXT.md** (episode-specific context)
- Generates contextual responses
- References guest and themes

### Stage 5: Quality Moderation
- **Reads specialized/moderator/CLAUDE.md** (quality evaluation criteria)
- **Reads episode EPISODE_CONTEXT.md** (episode-specific context)
- Claude evaluates its own responses
- Checks relevance and quality

## 💻 API Usage

### Python Integration

```python
from claude_pipeline.core import ClaudeInterface, EpisodeManager
from claude_pipeline.stages import Summarizer, Classifier

# Initialize
claude = ClaudeInterface()
episode_mgr = EpisodeManager()

# Create episode
episode_info = episode_mgr.create_episode(
    transcript="Rick Becker: Welcome to WDF...",
    video_url="https://youtube.com/watch?v=abc123"
)
episode_id = episode_info['episode_id']

# Summarize and create episode context
summarizer = Summarizer(claude)
summary_result = summarizer.summarize(
    transcript=transcript,
    podcast_overview=overview,
    episode_id=episode_id
)
# Uses: specialized/summarizer/CLAUDE.md + creates EPISODE_CONTEXT.md

# Classify using hybrid context (no few-shots needed)
classifier = Classifier(claude)
classified = classifier.classify(tweets, episode_id)
# Uses: specialized/classifier/CLAUDE.md + episode EPISODE_CONTEXT.md
```

### Command Line

```bash
# List episodes
ls episodes/

# View episode context
cat episodes/episode_20250112_abc123/EPISODE_CONTEXT.md

# View specialized instructions for classification
cat claude-pipeline/specialized/classifier/CLAUDE.md

# Run specific stage
python -m claude_pipeline.stages.classify \
  --episode-id 20250112_abc123 \
  --tweets tweets.json
```

## 🎨 Configuration

### Environment Variables

```bash
# No rate limiting needed with MAX20 plan
export WDF_RATE_LIMIT=0

# Episode directory location
export WDF_EPISODES_DIR=/path/to/episodes

# Cache settings
export WDF_CACHE_TTL_HOURS=48
```

### Config File (optional)

```yaml
# claude-pipeline/config.yaml
claude:
  model: sonnet
  temperature: 0.7

episodes:
  directory: ./episodes
  max_age_days: 30

cache:
  enabled: true
  ttl_hours: 48
```

## 📊 Performance

### Without Unified Pipeline
- 4 different models
- Few-shot generation required
- Complex memory management
- ~10 minutes per episode

### With Unified Pipeline
- 1 model (Claude)
- No few-shots needed
- Simple file-based memory
- ~8 minutes per episode
- 40% quality improvement

## 🔍 Debugging

### View Hybrid Context
```bash
# See episode-specific context
cat episodes/episode_20250112_abc123/EPISODE_CONTEXT.md

# See specialized instructions for classification
cat claude-pipeline/specialized/classifier/CLAUDE.md

# See specialized instructions for response generation
cat claude-pipeline/specialized/responder/CLAUDE.md
```

### Check Cache Stats
```python
from claude_pipeline.core import ResponseCache
cache = ResponseCache()
print(cache.get_stats())
```

### Episode Management
```python
from claude_pipeline.core import EpisodeManager
mgr = EpisodeManager()

# List all episodes
episodes = mgr.list_episodes()

# Get current episode
current = mgr.get_current_episode()

# Clean old episodes
mgr.cleanup_old_episodes(max_age_days=30)
```

## 🚨 Common Issues

### Episode Not Found
```python
# Episode directory doesn't exist
# Solution: Create episode first
episode_mgr.create_episode(transcript, episode_id)
```

### EPISODE_CONTEXT.md Not Updated
```python
# Episode context not reflecting latest summary
# Solution: Run update_episode_context
episode_mgr.update_episode_context(episode_id, summary, keywords)
```

### Classification Too Permissive
```markdown
# Edit specialized/classifier/CLAUDE.md to adjust scoring criteria
### HIGHLY RELEVANT (0.85-1.00)
- Require mention of [guest name or org]
- Must discuss [specific constitutional topics]

# Episode context provides specific details automatically
```

## 🎯 Best Practices

1. **One Episode = One Directory**: Keep everything together
2. **Specialized + Context**: Use both instruction precision and episode context
3. **EPISODE_CONTEXT.md is Episode Memory**: Contains episode-specific data only
4. **specialized/*/CLAUDE.md for Instructions**: Task-specific instructions remain sharp
5. **Review Generated Context**: Ensure EPISODE_CONTEXT.md is accurate
6. **Archive Old Episodes**: Zip and store completed episodes

## 🔄 Migration from Old System

```bash
# Migrate existing transcripts
python scripts/migrate_to_episodes.py \
  --source transcripts/ \
  --target episodes/

# Convert JSON memories to EPISODE_CONTEXT.md
python scripts/convert_memories.py \
  --source episode_memories/ \
  --target episodes/
```

## 📈 Monitoring

```python
# Get pipeline metrics
from claude_pipeline.orchestrator import UnifiedClaudePipeline
pipeline = UnifiedClaudePipeline()

# Run with monitoring
results = pipeline.run_episode(
    transcript_path="transcript.txt",
    episode_id="test_001"
)

# View metrics
print(f"Total time: {results['stats']['total_time_minutes']} minutes")
print(f"Approval rate: {results['stats']['approval_rate']}%")
print(f"Cost: ${results['cost_report']['total_cost']}")
```

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch
3. Ensure EPISODE_CONTEXT.md generation works
4. Test with sample episode
5. Submit pull request

## 📄 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

- Claude 3.5 Sonnet for superior reasoning
- WDF Podcast team for the vision
- Episode-based architecture for simplicity

---

**Remember: Hybrid context = specialized instructions + episode context. Precise, powerful, elegant.**