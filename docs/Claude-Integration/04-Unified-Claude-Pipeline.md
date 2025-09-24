# Unified Claude Pipeline Architecture

## Vision: One Model to Rule Them All

### The Paradigm Shift
Instead of 4 different models with complex handoffs, use Claude's superior reasoning for everything.

## Revolutionary Architecture

### Directory Structure
```
claude-pipeline/
├── CLAUDE.md                    # Master context and role
├── episode/
│   ├── EPISODE_CONTEXT.md      # Current episode memory
│   ├── summarize.py            # Transcript analysis
│   ├── classify.py             # Tweet classification  
│   └── respond.py              # Response generation
├── lib/
│   ├── memory.py               # Episode memory management
│   ├── batch.py                # Batch processing utilities
│   └── cache.py                # Intelligent caching
└── main.py                     # Unified orchestrator
```

### Master CLAUDE.md
```markdown
# WDF Podcast AI Assistant

## YOUR IDENTITY
You are the AI system for the War, Divorce, or Federalism podcast. You handle all content analysis, social media engagement, and audience interaction.

## CAPABILITIES
Based on the task specified, you can:
1. SUMMARIZE: Analyze transcripts and extract insights
2. CLASSIFY: Score tweet relevance without examples
3. RESPOND: Generate engaging tweet responses
4. MODERATE: Evaluate response quality

## CONTEXT AWARENESS
You maintain persistent understanding of:
- Current episode content
- Guest expertise and arguments  
- Key themes and controversies
- Audience interests and reactions

## TASK MODES
You will be instructed which mode to operate in for each request.
```

## Unified Pipeline Flow

### Step 1: Episode Ingestion
```python
class UnifiedClaudePipeline:
    def __init__(self, episode_id: str):
        self.episode_id = episode_id
        self.context = EpisodeContext(episode_id)
        self.claude = ClaudeInterface("claude-pipeline/")
    
    def ingest_episode(self, transcript: str, overview: str):
        """Single Claude call to understand entire episode."""
        
        response = self.claude.call(
            mode="ANALYZE",
            prompt=f"""Analyze this episode and extract:
            1. Comprehensive summary (3000-5000 words)
            2. Key themes and arguments
            3. Guest information
            4. Controversial points
            5. 25 keywords for tweet discovery
            6. Notable quotes
            
            TRANSCRIPT: {transcript}
            OVERVIEW: {overview}
            """
        )
        
        # Store in context for all future operations
        self.context.store(response)
        return response
```

### Step 2: Tweet Classification (No Few-Shots!)
```python
    def classify_tweets(self, tweets: List[str]) -> List[float]:
        """Classify tweets using episode understanding."""
        
        # Batch for efficiency
        batches = chunk_list(tweets, size=20)
        all_scores = []
        
        for batch in batches:
            response = self.claude.call(
                mode="CLASSIFY",
                context=self.context.get_classification_context(),
                prompt=f"""Score each tweet's relevance (0.00-1.00) based on episode themes.
                Output one score per line.
                
                TWEETS:
                {format_numbered_list(batch)}
                """
            )
            
            scores = parse_scores(response)
            all_scores.extend(scores)
        
        return all_scores
```

### Step 3: Response Generation
```python
    def generate_responses(self, relevant_tweets: List[dict]) -> List[str]:
        """Generate responses using full episode context."""
        
        responses = []
        
        for tweet in relevant_tweets:
            response = self.claude.call(
                mode="RESPOND",
                context=self.context.get_response_context(),
                prompt=f"""Generate a <200 char response promoting the podcast.
                
                Tweet: {tweet['text']}
                Video URL: {self.context.video_url}
                """
            )
            
            responses.append(response)
        
        return responses
```

### Step 4: Quality Moderation (New!)
```python
    def moderate_responses(self, responses: List[dict]) -> List[dict]:
        """Claude can evaluate its own responses for quality."""
        
        moderated = []
        
        for response in responses:
            evaluation = self.claude.call(
                mode="MODERATE",
                prompt=f"""Evaluate this response:
                Original Tweet: {response['tweet']}
                Response: {response['text']}
                
                Check for:
                1. Relevance (0-10)
                2. Engagement potential (0-10)
                3. Character count (<200)
                4. URL included
                5. Tone appropriateness
                
                OUTPUT:
                APPROVE/REJECT
                REASON: [one line]
                SUGGESTED_EDIT: [if rejected]
                """
            )
            
            response['moderation'] = parse_moderation(evaluation)
            moderated.append(response)
        
        return moderated
```

## Episode Context Management

### Intelligent Memory System
```python
class EpisodeContext:
    """Maintains episode understanding across all operations."""
    
    def __init__(self, episode_id: str):
        self.episode_id = episode_id
        self.memory = {}
        self.load_or_create()
    
    def store(self, analysis: dict):
        """Store episode analysis for reuse."""
        self.memory = {
            'summary': analysis['summary'],
            'themes': analysis['themes'],
            'guest': analysis['guest'],
            'quotes': analysis['quotes'],
            'keywords': analysis['keywords'],
            'controversy': analysis['controversy'],
            'timestamp': time.time()
        }
        self.save()
    
    def get_classification_context(self) -> str:
        """Minimal context for classification."""
        return f"""
        Episode Theme: {self.memory['themes'][0]}
        Guest: {self.memory['guest']['name']}
        Key Topics: {', '.join(self.memory['themes'][:3])}
        """
    
    def get_response_context(self) -> str:
        """Rich context for response generation."""
        return f"""
        Guest: {self.memory['guest']['name']} - {self.memory['guest']['title']}
        Main Point: {self.memory['themes'][0]}
        Best Quote: "{self.memory['quotes'][0]}"
        """
    
    def is_valid(self, max_age_hours: int = 24) -> bool:
        """Check if context is still fresh."""
        age = time.time() - self.memory.get('timestamp', 0)
        return age < (max_age_hours * 3600)
```

## Batch Processing Optimization

### Smart Batching
```python
class BatchProcessor:
    """Optimize Claude API usage with intelligent batching."""
    
    def __init__(self, max_batch_size: int = 20):
        self.max_batch_size = max_batch_size
        self.queue = []
    
    def process_tweets(self, tweets: List[dict], operation: str) -> List[dict]:
        """Process tweets in optimal batches."""
        
        # Group similar tweets for better context
        grouped = self.group_by_similarity(tweets)
        results = []
        
        for group in grouped:
            if operation == "classify":
                scores = self.batch_classify(group)
                for tweet, score in zip(group, scores):
                    tweet['score'] = score
            elif operation == "respond":
                responses = self.batch_respond(group)
                for tweet, response in zip(group, responses):
                    tweet['response'] = response
            
            results.extend(group)
        
        return results
    
    def group_by_similarity(self, tweets: List[dict]) -> List[List[dict]]:
        """Group similar tweets for coherent batches."""
        # Simple length-based grouping for now
        # Could use embeddings for semantic similarity
        
        groups = []
        current_group = []
        
        for tweet in sorted(tweets, key=lambda t: len(t['text'])):
            if len(current_group) < self.max_batch_size:
                current_group.append(tweet)
            else:
                groups.append(current_group)
                current_group = [tweet]
        
        if current_group:
            groups.append(current_group)
        
        return groups
```

## Cost Optimization Strategies

### 1. Context Compression
```python
def compress_context(context: str, max_tokens: int = 500) -> str:
    """Compress context to essential information."""
    
    # Use Claude itself to compress!
    compressed = call_claude(f"""
    Compress this context to under {max_tokens} tokens while preserving key information:
    {context}
    
    OUTPUT: Compressed version only
    """)
    
    return compressed
```

### 2. Response Caching
```python
class ResponseCache:
    """Cache responses for similar tweets."""
    
    def __init__(self, similarity_threshold: float = 0.85):
        self.cache = {}
        self.threshold = similarity_threshold
    
    def get_or_generate(self, tweet: str, generator_func) -> str:
        """Return cached response or generate new one."""
        
        # Check exact match
        if tweet in self.cache:
            return self.cache[tweet]
        
        # Check similar tweets
        for cached_tweet, response in self.cache.items():
            if self.similarity(tweet, cached_tweet) > self.threshold:
                # Adapt cached response
                adapted = self.adapt_response(response, tweet, cached_tweet)
                self.cache[tweet] = adapted
                return adapted
        
        # Generate new response
        response = generator_func(tweet)
        self.cache[tweet] = response
        return response
```

### 3. Progressive Enhancement
```python
def progressive_classification(tweets: List[str]) -> List[float]:
    """Start with cheap heuristics, use Claude for uncertain cases."""
    
    results = []
    needs_claude = []
    
    for tweet in tweets:
        # Quick heuristics
        quick_score = apply_heuristics(tweet)
        
        if quick_score < 0.3 or quick_score > 0.8:
            # High confidence from heuristics
            results.append((tweet, quick_score))
        else:
            # Needs Claude's judgment
            needs_claude.append(tweet)
    
    # Batch process uncertain tweets
    if needs_claude:
        claude_scores = batch_classify_with_claude(needs_claude)
        for tweet, score in zip(needs_claude, claude_scores):
            results.append((tweet, score))
    
    return results
```

## UI Integration Design

### Real-Time Pipeline View
```typescript
interface PipelineStatus {
  stage: 'summarization' | 'classification' | 'response' | 'moderation';
  progress: number;  // 0-100
  currentBatch: number;
  totalBatches: number;
  estimatedTimeRemaining: number;
  costIncurred: number;
}

// WebSocket updates
ws.on('pipeline:update', (status: PipelineStatus) => {
  updateProgressBar(status);
  updateCostMeter(status.costIncurred);
});
```

### Configuration Interface
```typescript
interface ClaudePipelineConfig {
  // Feature flags
  useFewShots: false;  // Always false with Claude!
  enableModeration: boolean;
  enableCaching: boolean;
  
  // Optimization settings
  batchSize: number;
  compressionLevel: 'none' | 'light' | 'aggressive';
  similarityThreshold: number;
  
  // Cost controls
  maxCostPerRun: number;
  costAlertThreshold: number;
  
  // Quality settings
  minConfidenceScore: number;
  requireReasoning: boolean;
}
```

### Episode Memory Viewer
```typescript
interface EpisodeMemoryView {
  episodeId: string;
  guest: GuestInfo;
  themes: string[];
  quotes: string[];
  keywords: string[];
  controversialPoints: string[];
  
  // Memory usage stats
  contextSize: number;
  compressionRatio: number;
  cacheHits: number;
  apiCalls: number;
}
```

## Migration Roadmap

### Phase 1: Foundation (Week 1)
- [ ] Set up claude-pipeline directory structure
- [ ] Create master CLAUDE.md with all modes
- [ ] Implement EpisodeContext class
- [ ] Build ClaudeInterface wrapper

### Phase 2: Summarization (Week 2)
- [ ] Replace Gemini summarizer
- [ ] Implement episode memory system
- [ ] Create keyword extraction
- [ ] Add controversy detection

### Phase 3: Classification (Week 3)
- [ ] Eliminate few-shot generation
- [ ] Implement direct classification
- [ ] Add batch processing
- [ ] Create similarity caching

### Phase 4: Integration (Week 4)
- [ ] Unify all stages
- [ ] Add progressive enhancement
- [ ] Implement cost monitoring
- [ ] Create fallback mechanisms

### Phase 5: UI Updates (Week 5)
- [ ] Update settings pages
- [ ] Add pipeline monitoring
- [ ] Create memory viewer
- [ ] Implement real-time updates

### Phase 6: Optimization (Week 6)
- [ ] Tune batch sizes
- [ ] Optimize context compression
- [ ] Implement smart caching
- [ ] Add A/B testing

## Performance Projections

### Current Multi-Model Pipeline
```
Models: 4 (Gemini, Gemma, DeepSeek, Claude)
Complexity: High
Maintenance: Difficult
Cost per 100 tweets: $0.55
Processing time: 5-10 minutes
Quality score: 7/10
```

### Unified Claude Pipeline
```
Models: 1 (Claude)
Complexity: Low
Maintenance: Simple
Cost per 100 tweets: $0.65
Processing time: 8-12 minutes
Quality score: 9.5/10
```

## Risk Mitigation

### 1. Single Point of Failure
**Risk**: All operations depend on Claude
**Mitigation**: 
- Maintain Gemini summarizer as fallback
- Cache aggressively
- Implement circuit breakers

### 2. Cost Overruns
**Risk**: Higher API costs
**Mitigation**:
- Progressive enhancement (heuristics first)
- Intelligent batching
- Response caching
- Cost alerts and limits

### 3. Speed Degradation
**Risk**: Sequential processing slower
**Mitigation**:
- Batch operations
- Async processing where possible
- Pre-filtering with heuristics
- Parallel Claude instances

## Revolutionary Benefits

### 1. Simplicity
- One model to configure
- One API to manage
- One context to maintain
- One system to debug

### 2. Quality
- Consistent reasoning across all stages
- Better contextual understanding
- No information loss between stages
- Superior response generation

### 3. Maintainability
- Single upgrade path
- Unified prompt engineering
- Centralized optimization
- Simplified monitoring

### 4. Innovation Potential
- Episode memory enables new features
- Quality moderation improves output
- Unified context enables cross-stage insights
- Single model allows rapid iteration

## Conclusion

The Unified Claude Pipeline represents a fundamental reimagining of the WDFWatch system. By leveraging Claude's superior reasoning across all stages, we eliminate complexity while improving quality. The episode memory system and intelligent batching make this not just feasible, but optimal.

This is not incremental improvement - it's a paradigm shift that positions WDFWatch at the forefront of AI-powered content engagement.