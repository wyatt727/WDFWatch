# Tweet Gathering Improvements Plan

## Executive Summary
This document outlines improvements to WDFWatch's tweet gathering system to provide fine-grained control, prevent API exhaustion, and enable better tweet management.

## Current Issues & Solutions

### 1. API Exhaustion Prevention

**Problem**: Users can accidentally exhaust API limits without meaningful results.

**Solution**: Multi-layered protection system
- **Pre-flight Checks**: Estimate API usage before scraping
- **Smart Caching**: Use existing tweet cache before making API calls
- **Progressive Scraping**: Start with small batches, review results, then expand
- **Cost Calculator**: Show estimated API calls before execution

### 2. Orphaned Tweet Management

**Problem**: Tweets not associated with episodes are invisible and unmanageable.

**Solution**: Global Tweet Queue
- Persistent queue table tracks all tweets regardless of episode association
- "Unassigned Tweets" dashboard section for viewing/managing orphaned tweets
- Bulk operations to assign tweets to episodes post-scraping
- Auto-suggest episode associations based on content similarity

### 3. Storage & Queue Persistence

**Current State**: 
- Tweets stored in database with optional episode_id
- 90-day cache in `artefacts/tweet_cache.json`
- No persistent queue for processing order

**Improvements**:
```sql
-- Tweet Queue provides:
-- 1. Priority-based processing (high-value tweets first)
-- 2. Retry logic for failed processing
-- 3. Source tracking (manual vs automated)
-- 4. Processing status visibility
```

### 4. Single Tweet Response Capability

**New Feature**: Respond to specific tweets outside the normal pipeline

**Implementation**:
1. **Direct URL Input**: Paste tweet URL in dashboard
2. **Instant Processing**: Skip classification, go straight to response generation
3. **Context Selection**: Choose which episode context to use for response
4. **Preview & Edit**: Review response before publishing

## Improved Manual Control Interface

### Tweet Gathering Dashboard
```
┌─────────────────────────────────────────────────────────────┐
│                  Manual Tweet Gathering                      │
├─────────────────────────────────────────────────────────────┤
│ API Quota: ████████░░ 8,234/10,000 (82%)                   │
│ Estimated Exhaustion: 5 days                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ ┌──── Gathering Options ────┐  ┌──── Cost Estimate ────┐   │
│ │                            │  │                        │   │
│ │ Source:                    │  │ Keywords: 5            │   │
│ │ ○ Keywords (Recommended)   │  │ Est. API Calls: ~15    │   │
│ │ ○ Direct URLs              │  │ Cache Hits: ~45        │   │
│ │ ○ User Timeline            │  │ New Tweets: ~10-20     │   │
│ │                            │  │                        │   │
│ │ Keywords: [Use Episode ▼]  │  │ ⚠️ High cache hit rate │   │
│ │ □ federalism               │  │    expected            │   │
│ │ □ state sovereignty        │  └────────────────────────┘   │
│ │ □ constitutional           │                              │
│ │                            │  ┌──── Safety Settings ───┐   │
│ │ Time Range: [7 days ▼]     │  │                        │   │
│ │ Max Tweets: [50 ▼]         │  │ □ Test with cache only │   │
│ │ Min Engagement: [10 ▼]     │  │ □ Dry run (no API)     │   │
│ │                            │  │ ☑ Use cache first      │   │
│ │ [Preview] [Start Gathering]│  │ □ Auto-stop at 100 API │   │
│ └────────────────────────────┘  └────────────────────────┘   │
│                                                              │
│ ┌──── Tweet Queue Status ─────────────────────────────────┐  │
│ │ Pending: 43 | Processing: 2 | Completed: 187            │  │
│ │                                                          │  │
│ │ Priority Queue:                                          │  │
│ │ 1. @constitutional_voter - "State sovereignty..." (9.2) │  │
│ │ 2. @liberty_defender - "Federal overreach..." (8.7)     │  │
│ │ 3. [Unassigned] @random_user - "Interesting..." (7.1)   │  │
│ └──────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Plan

### Phase 1: Core Queue System (Week 1)
- [ ] Create tweet_queue and related tables
- [ ] Build queue management API endpoints
- [ ] Implement priority scoring algorithm
- [ ] Add retry logic for failed processing

### Phase 2: Enhanced UI Controls (Week 2)
- [ ] Tweet Gathering Dashboard component
- [ ] API usage estimator
- [ ] Cache-first gathering option
- [ ] Progressive scraping interface

### Phase 3: Single Tweet Response (Week 3)
- [ ] Direct URL input interface
- [ ] Instant response generation pipeline
- [ ] Context selection dropdown
- [ ] Response preview/edit workflow

### Phase 4: Orphaned Tweet Management (Week 4)
- [ ] Unassigned tweets dashboard section
- [ ] Bulk assignment operations
- [ ] Episode suggestion algorithm
- [ ] Cleanup automation rules

## API Usage Optimization Strategy

### 1. Cache-First Approach
```python
def gather_tweets(keywords, options):
    # Step 1: Check cache for matching tweets
    cached_tweets = search_cache(keywords, options)
    
    # Step 2: Estimate API calls needed
    estimated_api_calls = estimate_api_usage(keywords, cached_tweets)
    
    # Step 3: Get user confirmation if high usage
    if estimated_api_calls > 100:
        if not get_user_confirmation(estimated_api_calls):
            return cached_tweets  # Use cache only
    
    # Step 4: Make API calls with progressive limits
    new_tweets = []
    for batch in progressive_batches([10, 25, 50, 100]):
        batch_tweets = api_search(keywords, limit=batch)
        new_tweets.extend(batch_tweets)
        
        # Stop if getting low-quality results
        if average_relevance(batch_tweets) < 0.5:
            break
    
    return merge_deduplicate(cached_tweets, new_tweets)
```

### 2. Smart Deduplication
- SHA-256 hash of tweet text for exact duplicates
- Fuzzy matching for near-duplicates (85% similarity threshold)
- Cross-episode duplicate detection
- Automatic merge of duplicate tweet metadata

### 3. Priority Processing
```python
PRIORITY_FACTORS = {
    'verified_account': 2.0,
    'high_engagement': 1.5,  # >100 likes/retweets
    'keyword_density': 1.3,  # Multiple keyword matches
    'recent_tweet': 1.2,     # Posted within 24 hours
    'has_thread': 1.1,       # Part of a thread
}
```

## Storage Optimization

### Retention Policies
```yaml
retention_rules:
  high_relevance:  # Score > 0.85
    keep_forever: true
    
  relevant:        # Score 0.70-0.85
    keep_days: 180
    
  maybe_relevant:  # Score 0.50-0.70
    keep_days: 90
    
  not_relevant:    # Score < 0.50
    keep_days: 30
    archive_to_cold_storage: true
```

### Archive System
- Move old tweets to `artefacts/archive/` after retention period
- Compress with gzip for 70% space savings
- Maintain index for searchability
- Restore on-demand if needed

## Monitoring & Alerts

### Real-time Dashboard Metrics
- API calls per minute/hour/day
- Cache hit rate percentage
- Queue processing speed
- Error rate tracking
- Relevance score distribution

### Alert Thresholds
```yaml
alerts:
  api_exhaustion_warning:
    threshold: 80%  # Of monthly quota
    action: email_notification
    
  high_error_rate:
    threshold: 10%  # Of API calls
    action: pause_scraping
    
  low_cache_hits:
    threshold: 20%  # Cache hit rate
    action: suggest_cache_rebuild
    
  queue_backup:
    threshold: 500  # Pending tweets
    action: increase_workers
```

## Benefits

1. **API Preservation**: 60-80% reduction in API calls through intelligent caching
2. **Better Control**: Granular control over every aspect of gathering
3. **Visibility**: Complete transparency into what tweets exist and their status
4. **Flexibility**: Respond to specific tweets outside normal workflow
5. **Efficiency**: Priority processing ensures high-value tweets handled first
6. **Safety**: Multiple safeguards prevent accidental API exhaustion

## Migration Path

1. **Database Migration**: Run new schema migrations
2. **Populate Queue**: Import existing tweets into queue
3. **Update Pipeline**: Modify scrape.py to use queue system
4. **Deploy UI**: Roll out new dashboard components
5. **Monitor**: Track metrics for 1 week before deprecating old system

## Success Metrics

- API usage reduction: Target 60% decrease
- Cache hit rate: Target 70% for common keywords  
- Queue processing time: <5 minutes for 100 tweets
- User satisfaction: Reduced API exhaustion incidents to zero
- Response quality: Maintain or improve relevance scores