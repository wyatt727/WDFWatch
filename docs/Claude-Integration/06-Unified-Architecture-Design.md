# Unified Claude Pipeline Architecture - Optimal Design

## Executive Summary

This document outlines the optimal unified architecture for the Claude-powered WDFWatch pipeline. The design consolidates all Claude functionality into a single, cohesive system with episode memory at its core.

## Current State Analysis

### Problems with Current Architecture
1. **Fragmentation**: Three separate Claude directories (classifier, summarizer, responder)
2. **No Memory Utilization**: Response generator doesn't use episode memory
3. **No Unified Interface**: Each component calls Claude differently
4. **No Caching**: Redundant API calls for similar content
5. **No Cost Tracking**: No visibility into API costs
6. **No Quality Control**: No automated quality moderation
7. **Complex Orchestration**: main.py still uses old pipeline flow

### Gaps to Address
- Response generation needs memory integration
- Need unified Claude interface for all operations
- Need intelligent caching to reduce costs
- Need quality moderation for responses
- Need cost tracking and optimization
- Need simplified orchestration

## Optimal Unified Architecture

### Directory Structure
```
claude-pipeline/
├── __init__.py
├── CLAUDE.md                    # Master context for all operations
├── config.yaml                  # Configuration (API keys, models, thresholds)
│
├── core/                        # Core components
│   ├── __init__.py
│   ├── claude_interface.py     # Unified Claude CLI wrapper
│   ├── episode_memory.py       # Episode memory system
│   ├── cache.py                # Intelligent caching layer
│   ├── batch_processor.py      # Batch processing utilities
│   └── cost_tracker.py         # API cost tracking
│
├── stages/                      # Pipeline stages
│   ├── __init__.py
│   ├── summarize.py            # Transcript summarization
│   ├── classify.py             # Tweet classification
│   ├── respond.py              # Response generation
│   └── moderate.py             # Quality moderation
│
├── utils/                       # Utilities
│   ├── __init__.py
│   ├── prompts.py              # Prompt templates
│   ├── validators.py           # Response validation
│   └── metrics.py              # Performance metrics
│
├── data/                        # Data storage
│   ├── memories/               # Episode memories
│   ├── cache/                  # Response cache
│   └── costs/                  # Cost tracking data
│
├── orchestrator.py             # Master pipeline orchestrator
├── monitor.py                  # Real-time monitoring
└── tests/                      # Test suite
    ├── test_memory.py
    ├── test_classification.py
    ├── test_response.py
    └── test_integration.py
```

## Core Components Design

### 1. Unified Claude Interface
```python
class ClaudeInterface:
    """Unified interface for all Claude operations."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = load_config(config_path)
        self.cost_tracker = CostTracker()
        self.cache = ResponseCache()
        
    def call(self, 
             prompt: str, 
             mode: str = "default",
             context: str = None,
             use_cache: bool = True) -> str:
        """
        Unified Claude calling with caching and cost tracking.
        
        Modes:
        - summarize: Long-form analysis
        - classify: Batch classification
        - respond: Response generation
        - moderate: Quality evaluation
        """
        # Check cache first
        if use_cache:
            cached = self.cache.get(prompt, mode)
            if cached:
                return cached
        
        # Build full prompt with context
        full_prompt = self._build_prompt(prompt, mode, context)
        
        # Call Claude
        response = self._call_claude_cli(full_prompt)
        
        # Track costs
        self.cost_tracker.track(prompt, response, mode)
        
        # Cache response
        if use_cache:
            self.cache.store(prompt, response, mode)
        
        return response
```

### 2. Episode Context System (CLAUDE.md Files)
```python
class EpisodeContext:
    """
    Creates episode-specific CLAUDE.md files instead of JSON memories.
    Each episode gets its own context file that Claude reads directly.
    """
    
    def __init__(self, episode_id: str):
        self.episode_id = episode_id
        self.context_file = f"episode_contexts/episode_{episode_id}_CLAUDE.md"
        
    def create_from_summary(self, summary: str, keywords: List[str], video_url: str):
        """
        Generate episode-specific CLAUDE.md from summary.
        Combines master context with episode details.
        """
        
        # Extract structured information
        guest_info = self._extract_guest_info(summary)
        themes = self._extract_themes(summary)
        quotes = self._extract_quotes(summary)
        
        # Build episode-specific markdown context
        episode_context = f"""
        # EPISODE CONTEXT: {self.episode_id}
        
        ## GUEST INFORMATION
        **Name**: {guest_info['name']}
        **Organization**: {guest_info['organization']}
        
        ## KEY THEMES DISCUSSED
        {format_themes(themes)}
        
        ## POWERFUL QUOTES
        {format_quotes(quotes)}
        
        ## VIDEO URL
        {video_url}
        *Always include this URL in responses*
        
        ## CONTEXT USAGE GUIDELINES
        
        ### For Classification:
        - Focus on tweets relating to these themes
        - Higher scores for guest-specific topics
        
        ### For Response Generation:
        - Reference the guest by name
        - Use quotes for authenticity
        - Always include video URL
        """
        
        # Combine with master CLAUDE.md
        master_content = read_file("CLAUDE.md")
        full_context = master_content.replace(
            "*Episode-specific context will be inserted here*",
            episode_context
        )
        
        # Save as episode-specific CLAUDE.md
        write_file(self.context_file, full_context)
```

**Key Innovation**: Instead of JSON memories that need to be loaded and formatted, we create complete CLAUDE.md files for each episode. Claude simply reads the appropriate file with `@episode_contexts/episode_123_CLAUDE.md`.

### 3. Intelligent Cache
```python
class ResponseCache:
    """Smart caching with similarity matching."""
    
    def __init__(self, similarity_threshold: float = 0.85):
        self.cache = {}
        self.embeddings = {}  # Store embeddings for similarity
        self.threshold = similarity_threshold
        
    def get(self, prompt: str, mode: str) -> Optional[str]:
        """Get cached response for similar prompts."""
        
        # Check exact match
        cache_key = self._hash(prompt, mode)
        if cache_key in self.cache:
            return self.cache[cache_key]['response']
        
        # Check similar prompts (using simple similarity for now)
        for key, entry in self.cache.items():
            if entry['mode'] == mode:
                similarity = self._calculate_similarity(prompt, entry['prompt'])
                if similarity > self.threshold:
                    # Adapt response if needed
                    return self._adapt_response(entry['response'], prompt, entry['prompt'])
        
        return None
    
    def store(self, prompt: str, response: str, mode: str):
        """Store response with metadata."""
        cache_key = self._hash(prompt, mode)
        self.cache[cache_key] = {
            'prompt': prompt,
            'response': response,
            'mode': mode,
            'timestamp': time.time(),
            'hits': 0
        }
```

### 4. Cost Tracker
```python
class CostTracker:
    """Track and optimize API costs."""
    
    # Pricing per 1M tokens (Claude 3.5 Sonnet)
    PRICING = {
        'input': 3.00,   # $3 per 1M input tokens
        'output': 15.00  # $15 per 1M output tokens
    }
    
    def __init__(self):
        self.costs_file = "data/costs/costs.json"
        self.costs = self._load_costs()
        
    def track(self, prompt: str, response: str, mode: str):
        """Track API call costs."""
        input_tokens = self._count_tokens(prompt)
        output_tokens = self._count_tokens(response)
        
        cost = (input_tokens * self.PRICING['input'] + 
                output_tokens * self.PRICING['output']) / 1_000_000
        
        self.costs['total'] += cost
        self.costs['by_mode'][mode] = self.costs['by_mode'].get(mode, 0) + cost
        self.costs['calls'] += 1
        
        self._save_costs()
        
    def get_report(self) -> dict:
        """Get cost report with optimization suggestions."""
        return {
            'total_cost': self.costs['total'],
            'calls': self.costs['calls'],
            'average_cost': self.costs['total'] / self.costs['calls'],
            'by_mode': self.costs['by_mode'],
            'suggestions': self._get_optimization_suggestions()
        }
```

## Pipeline Stages (Enhanced)

### 1. Summarization (with Memory Creation)
```python
class Summarizer:
    def __init__(self, claude: ClaudeInterface):
        self.claude = claude
        
    def summarize(self, transcript: str, episode_id: str) -> dict:
        """Generate summary and create episode memory."""
        
        # Generate comprehensive summary
        summary = self.claude.call(
            prompt=f"Analyze this transcript: {transcript}",
            mode="summarize"
        )
        
        # Create episode memory
        memory = EpisodeMemory(episode_id)
        memory.store_summary_analysis(summary, keywords, video_url)
        
        return {
            'summary': summary,
            'memory_id': episode_id,
            'memory_created': True
        }
```

### 2. Classification (No Few-Shots)
```python
class Classifier:
    def __init__(self, claude: ClaudeInterface):
        self.claude = claude
        
    def classify(self, tweets: List[str], episode_id: str) -> List[dict]:
        """Classify tweets using episode memory."""
        
        # Load episode memory
        memory = EpisodeMemory(episode_id)
        context = memory.get_context_for_stage('classification')
        
        # Batch classify
        scores = self.claude.call(
            prompt=format_tweets_for_classification(tweets),
            mode="classify",
            context=context
        )
        
        return parse_classification_scores(scores)
```

### 3. Response Generation (with Memory)
```python
class ResponseGenerator:
    def __init__(self, claude: ClaudeInterface):
        self.claude = claude
        
    def generate(self, tweet: str, episode_id: str) -> str:
        """Generate response using rich episode context."""
        
        # Load episode memory
        memory = EpisodeMemory(episode_id)
        context = memory.get_context_for_stage('response')
        
        # Generate response with context
        response = self.claude.call(
            prompt=f"Generate response for: {tweet}",
            mode="respond",
            context=context
        )
        
        return validate_response(response)
```

### 4. Quality Moderation (New!)
```python
class QualityModerator:
    def __init__(self, claude: ClaudeInterface):
        self.claude = claude
        
    def moderate(self, response: str, tweet: str, episode_id: str) -> dict:
        """Claude evaluates its own response quality."""
        
        memory = EpisodeMemory(episode_id)
        context = memory.get_context_for_stage('moderation')
        
        evaluation = self.claude.call(
            prompt=f"""
            Evaluate this response:
            Tweet: {tweet}
            Response: {response}
            
            Check: relevance, engagement, character count, URL included
            """,
            mode="moderate",
            context=context
        )
        
        return parse_moderation_result(evaluation)
```

## Master Orchestrator

```python
class UnifiedClaudePipeline:
    """Master orchestrator for the entire pipeline."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.claude = ClaudeInterface(config_path)
        self.summarizer = Summarizer(self.claude)
        self.classifier = Classifier(self.claude)
        self.responder = ResponseGenerator(self.claude)
        self.moderator = QualityModerator(self.claude)
        
    def run_episode(self, transcript_path: str, episode_id: str = None):
        """Run complete pipeline for an episode."""
        
        # Stage 1: Summarize and create memory
        summary_result = self.summarizer.summarize(
            transcript=load_transcript(transcript_path),
            episode_id=episode_id or generate_episode_id()
        )
        
        # Stage 2: Scrape tweets (existing functionality)
        tweets = scrape_tweets(summary_result['keywords'])
        
        # Stage 3: Classify without few-shots
        classified = self.classifier.classify(
            tweets=tweets,
            episode_id=summary_result['memory_id']
        )
        
        # Stage 4: Generate responses for relevant tweets
        responses = []
        for tweet in filter_relevant(classified):
            response = self.responder.generate(
                tweet=tweet['text'],
                episode_id=summary_result['memory_id']
            )
            
            # Stage 5: Moderate response quality
            moderation = self.moderator.moderate(
                response=response,
                tweet=tweet['text'],
                episode_id=summary_result['memory_id']
            )
            
            if moderation['approved']:
                responses.append({
                    'tweet': tweet,
                    'response': response,
                    'quality_score': moderation['score']
                })
        
        # Stage 6: Human review (existing moderation UI)
        final_responses = human_moderation(responses)
        
        # Generate report
        return self.generate_report(summary_result, classified, responses, final_responses)
```

## Performance Optimizations

### 1. Batch Processing
- Classify 20 tweets per Claude call
- Generate multiple responses in parallel
- Moderate responses in batches

### 2. Intelligent Caching
- Cache similar tweet classifications
- Reuse responses for similar tweets
- Cache episode contexts for 48 hours

### 3. Progressive Enhancement
- Use heuristics for obvious classifications
- Only call Claude for uncertain cases
- Pre-filter with keyword matching

### 4. Cost Optimization
- Compress contexts to minimum viable
- Batch operations to reduce overhead
- Track and alert on cost thresholds

## Migration Strategy

### Phase 1: Core Infrastructure (Day 1-2)
1. Create claude-pipeline directory
2. Implement ClaudeInterface
3. Migrate EpisodeMemory
4. Add ResponseCache

### Phase 2: Stage Migration (Day 3-4)
1. Migrate summarizer to unified system
2. Migrate classifier to use interface
3. Update responder with memory
4. Add quality moderator

### Phase 3: Integration (Day 5)
1. Create master orchestrator
2. Update main.py to use new pipeline
3. Add monitoring and metrics
4. Test end-to-end flow

### Phase 4: Optimization (Day 6-7)
1. Tune batch sizes
2. Optimize caching
3. Add cost alerts
4. Performance testing

## Expected Outcomes

### Improvements
- **Architecture**: 70% simpler (1 directory vs 3)
- **Code Reduction**: 50% less code
- **API Costs**: 30% reduction via caching
- **Quality**: 40% better responses with memory
- **Speed**: 2x faster with batching
- **Maintainability**: 10x easier

### New Capabilities
- Automatic quality moderation
- Cost tracking and optimization
- Response caching
- Unified monitoring
- Episode memory persistence

## Risk Mitigation

### Technical Risks
1. **Claude API failures**: Implement exponential backoff
2. **Memory corruption**: Add validation and backups
3. **Cache invalidation**: TTL and version tracking
4. **Cost overruns**: Hard limits and alerts

### Operational Risks
1. **Migration failures**: Parallel run old and new
2. **Quality degradation**: A/B testing
3. **Performance issues**: Progressive rollout

## Success Metrics

### Quantitative
- API costs < $0.60 per 100 tweets
- Response quality score > 8/10
- Cache hit rate > 40%
- Processing time < 10 minutes per episode
- Zero few-shot generation needed

### Qualitative
- Simplified codebase
- Easier debugging
- Better documentation
- Improved team velocity

## Conclusion

This unified architecture represents the optimal integration of Claude throughout the WDFWatch pipeline. By consolidating around a single interface with episode memory at its core, we achieve dramatic simplification while improving quality and reducing costs.

The key innovations are:
1. **Unified Interface**: One way to call Claude
2. **Episode Memory**: Persistent context across stages
3. **No Few-Shots**: Direct classification
4. **Quality Moderation**: Automatic quality control
5. **Smart Caching**: Reduce redundant API calls
6. **Cost Tracking**: Visibility and optimization

This is not just a refactor - it's a fundamental reimagining that positions WDFWatch for scalable, high-quality social media engagement.