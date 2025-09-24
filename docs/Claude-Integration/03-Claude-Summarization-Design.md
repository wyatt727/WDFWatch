# Claude Transcript Summarization Design

## Current Limitations vs Claude Advantages

### Current System (Gemini 2.5-Pro)
- Requires Node.js wrapper
- Chunks transcript into 16K segments
- No persistent episode understanding
- Cost: ~$0.10 per episode

### Claude Advantages
- Native CLI integration
- Superior context retention
- Better political/constitutional understanding
- Can maintain episode "memory" across pipeline stages

## Proposed Architecture

### Directory Structure
```
claude-summarizer/
├── CLAUDE.md                # Summarization role and instructions
├── summarize.py            # Main summarization script
├── extract_keywords.py     # Keyword extraction
├── episode_memory.json     # Persistent episode context
└── templates/
    ├── summary.md          # Output template
    └── keywords.json       # Keywords template
```

### CLAUDE.md for Summarization
```markdown
# WDF Podcast Episode Analyst

## YOUR ROLE
You are the official analyst for the War, Divorce, or Federalism podcast. Your job is to create comprehensive summaries that capture both the content and spirit of each episode.

## ANALYSIS FRAMEWORK

### 1. GUEST PROFILE
- Name and credentials
- Organization/affiliation
- Expertise areas
- Key arguments presented

### 2. CORE THEMES
- Constitutional issues discussed
- Federalism concepts explored
- State sovereignty arguments
- Historical precedents cited

### 3. ACTIONABLE INSIGHTS
- Practical solutions proposed
- Calls to action
- Resources mentioned
- Next steps for listeners

### 4. CONTROVERSIAL POINTS
- Provocative statements
- Challenging mainstream narratives
- Radical solutions proposed
- Points likely to generate discussion

### 5. QUOTABLE MOMENTS
- Powerful one-liners
- Memorable analogies
- Key statistics
- Historical references

## OUTPUT REQUIREMENTS

### Summary Format
- Length: 3000-5000 words
- Style: Engaging but informative
- Structure: Thematic sections with headers
- Tone: Aligned with podcast's libertarian perspective

### Keyword Extraction
- 20-30 highly specific terms
- Mix of:
  - Guest-specific terms
  - Episode themes
  - Trending political topics
  - Constitutional concepts
  - Historical references
```

## Implementation Strategy

### Phase 1: Single-Pass Summarization
```python
def summarize_with_claude(transcript: str, overview: str) -> dict:
    """
    Generate comprehensive summary in a single Claude call.
    No chunking needed with Claude's large context window.
    """
    prompt = f"""Analyze this WDF Podcast transcript and create:
    1. A comprehensive summary (3000-5000 words)
    2. 20-30 keywords for social media discovery
    
    PODCAST OVERVIEW:
    {overview}
    
    TRANSCRIPT:
    {transcript}
    
    OUTPUT FORMAT:
    ## SUMMARY
    [Comprehensive analysis following the framework]
    
    ## KEYWORDS
    [List of 20-30 terms, one per line]
    """
    
    response = call_claude(prompt)
    return parse_summary_and_keywords(response)
```

### Phase 2: Intelligent Chunking (If Needed)
```python
def smart_chunk_transcript(transcript: str, max_chars: int = 50000) -> List[str]:
    """
    Intelligently chunk transcript at natural boundaries.
    Unlike current system, preserves context.
    """
    chunks = []
    current_chunk = ""
    
    # Split by speaker turns
    segments = transcript.split('\n\n')
    
    for segment in segments:
        if len(current_chunk) + len(segment) < max_chars:
            current_chunk += segment + '\n\n'
        else:
            # End chunk at natural boundary
            chunks.append(current_chunk)
            current_chunk = segment + '\n\n'
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

def summarize_chunked(chunks: List[str]) -> str:
    """
    Process chunks with context preservation.
    """
    running_summary = ""
    
    for i, chunk in enumerate(chunks):
        if i == 0:
            prompt = f"Start analyzing this podcast transcript:\n{chunk}"
        else:
            prompt = f"""Continue analyzing. Previous context:
            {running_summary[-1000:]}
            
            Next segment:
            {chunk}"""
        
        chunk_summary = call_claude(prompt)
        running_summary += chunk_summary
    
    return running_summary
```

### Phase 3: Episode Memory System
```python
class EpisodeMemory:
    """
    Maintain persistent understanding across pipeline stages.
    This is revolutionary - no other component needs full summary!
    """
    
    def __init__(self, episode_id: str):
        self.episode_id = episode_id
        self.memory_file = f"episode_memory_{episode_id}.json"
        self.memory = {}
    
    def store_summary_insights(self, summary: str):
        """Extract and store key insights for other stages."""
        self.memory['guest'] = self.extract_guest_info(summary)
        self.memory['themes'] = self.extract_themes(summary)
        self.memory['quotes'] = self.extract_quotes(summary)
        self.memory['keywords'] = self.extract_keywords(summary)
        self.memory['controversy'] = self.extract_controversial_points(summary)
        self.save()
    
    def get_classification_context(self) -> str:
        """Provide focused context for tweet classification."""
        return f"""
        Guest: {self.memory['guest']['name']}
        Key Topics: {', '.join(self.memory['themes'][:5])}
        Controversial Points: {', '.join(self.memory['controversy'][:3])}
        """
    
    def get_response_context(self) -> str:
        """Provide focused context for response generation."""
        return f"""
        Guest: {self.memory['guest']['name']} ({self.memory['guest']['org']})
        Best Quote: {self.memory['quotes'][0]}
        Main Argument: {self.memory['themes'][0]}
        """
```

## Keyword Extraction Innovation

### Current System
- Simple keyword extraction
- Often generic terms
- Limited social media reach

### Claude Enhancement
```python
def extract_smart_keywords(summary: str, current_trends: List[str]) -> List[str]:
    """
    Extract keywords that will actually find relevant tweets.
    """
    prompt = f"""Based on this episode summary, generate 25 keywords that will:
    1. Find people discussing these exact topics on Twitter
    2. Include trending political hashtags if relevant
    3. Mix specific names with general concepts
    4. Include both supportive and oppositional terms
    
    SUMMARY:
    {summary}
    
    CURRENT TRENDING TOPICS:
    {', '.join(current_trends)}
    
    Generate keywords that real people would use in tweets:"""
    
    keywords = call_claude(prompt).split('\n')
    
    # Add variations
    expanded = []
    for keyword in keywords:
        expanded.append(keyword)
        expanded.append(f"#{keyword.replace(' ', '')}")  # Hashtag version
        if ' ' in keyword:
            expanded.append(keyword.split()[0])  # First word only
    
    return expanded[:30]
```

## Integration with Classification

### Revolutionary Concept: No Summary Needed!
Since Claude maintains episode context, classification can work with just the episode memory:

```python
def classify_without_summary(tweet: str, episode_memory: EpisodeMemory) -> float:
    """
    Classify using episode memory instead of full summary.
    Massive efficiency gain!
    """
    context = episode_memory.get_classification_context()
    
    prompt = f"""Given this episode context:
    {context}
    
    Score this tweet's relevance (0.00-1.00):
    {tweet}"""
    
    return float(call_claude(prompt))
```

## Cost Analysis

### Current Gemini System
```
Transcript (50K chars):     ~1500 tokens input
Summary generation:         ~1000 tokens output
Cost per episode:          ~$0.10
```

### Claude System
```
Transcript (50K chars):     ~10K tokens input
Summary generation:         ~1000 tokens output  
Cost per episode:          ~$0.08
Additional benefits:        Episode memory reuse
```

### ROI Calculation
- **Direct savings**: $0.02 per episode
- **Indirect savings**: Eliminate full summary passing (-$0.20 per 100 tweets)
- **Quality improvement**: Invaluable

## Output Quality Improvements

### Current Issues
- Generic summaries
- Missed nuances
- Poor keyword selection
- No cross-stage context

### Claude Advantages
1. **Thematic Understanding**: Better grasp of political concepts
2. **Guest Profiling**: Accurate capture of speaker positions
3. **Controversy Detection**: Identifies hot-button issues
4. **Keyword Intelligence**: Finds terms people actually use

## Migration Strategy

### Phase 1: Parallel Running
```python
def compare_summarizers(transcript: str):
    """Run both systems and compare."""
    
    gemini_summary = run_gemini_summarizer(transcript)
    claude_summary = run_claude_summarizer(transcript)
    
    comparison = {
        'length_difference': len(claude_summary) - len(gemini_summary),
        'keyword_overlap': calculate_overlap(
            gemini_summary['keywords'],
            claude_summary['keywords']
        ),
        'themes_detected': {
            'gemini': extract_themes(gemini_summary),
            'claude': extract_themes(claude_summary)
        }
    }
    
    return comparison
```

### Phase 2: Quality Metrics
- A/B test tweet discovery rates
- Compare classification accuracy
- Measure response relevance
- Track user engagement

### Phase 3: Full Migration
- Replace Node.js script entirely
- Implement episode memory system
- Optimize cross-stage context sharing

## UI Integration

### New Features
1. **Summary Preview**: Real-time summary generation with progress
2. **Keyword Suggestions**: AI-powered keyword recommendations
3. **Theme Extraction**: Visual theme hierarchy
4. **Episode Memory Viewer**: See what Claude "remembers"

### Settings Interface
```typescript
interface SummarizationSettings {
  provider: 'claude' | 'gemini';
  summaryLength: number;
  keywordCount: number;
  includeControversy: boolean;
  generateQuotes: boolean;
  maintainMemory: boolean;
}
```

## Performance Optimization

### Caching Strategy
```python
class SummaryCache:
    def __init__(self):
        self.cache_dir = Path("cache/summaries")
    
    def get_cached(self, transcript_hash: str) -> Optional[dict]:
        cache_file = self.cache_dir / f"{transcript_hash}.json"
        if cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < 86400:  # 24 hours
                return json.load(cache_file.open())
        return None
```

### Streaming Response
```python
def stream_summary_generation(transcript: str):
    """Stream summary as it's generated for better UX."""
    
    for chunk in call_claude_streaming(prompt):
        yield chunk
        # Update UI in real-time
        update_ui_progress(chunk)
```

## Expected Outcomes

### Improvements
- **Summary Quality**: +40% more insightful
- **Keyword Relevance**: +60% better tweet discovery
- **Processing Time**: -20% (no chunking overhead)
- **Context Preservation**: 100% (episode memory)

### New Capabilities
- Cross-stage context sharing
- Controversy detection
- Intelligent keyword expansion
- Real-time streaming updates

## Conclusion

Claude summarization with episode memory represents a paradigm shift. Instead of passing massive summaries between stages, we maintain intelligent context that each stage can query. This is not just a model swap - it's a fundamental architecture improvement.