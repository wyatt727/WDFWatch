# WDFWatch Twitter Search Strategy

## Conservative Individual Keyword Search

After analyzing Twitter API constraints and quota limitations, we've adopted a conservative individual keyword search strategy that prioritizes tracking effectiveness and preserving our limited monthly quota.

## Rate Limit Reality

| Endpoint | Limit | Impact |
|----------|-------|--------|
| `/2/tweets/counts/recent` | 5 requests / 15 min | ❌ Useless for volume testing |
| `/2/tweets/search/recent` | 60 requests / 15 min | ✅ Sufficient for individual searches |
| Monthly quota | 10,000 reads total | ⚠️ Must be extremely conservative |
| Results per request | 10 default, 100 max | Use 10 default for development |

## Our Strategy: Individual & Conservative

### 1. **NO Keyword Batching**
Search each keyword individually to track effectiveness:
```python
# Search each keyword separately
for keyword in keywords:
    query = f'"{keyword}" -is:retweet lang:en'
    results = api.search(query, max_results=10)  # Conservative!
```

### 2. **Conservative Result Limits**
```python
# Default to 10 results per keyword, NOT 100!
max_results_per_keyword = settings.get('maxResultsPerKeyword', 10)
```
Why? Testing once with 100 results per keyword would consume ~30% of our ENTIRE monthly quota!

### 3. **Track Keyword Effectiveness**
Individual searches let us know which keywords actually produce results:
```python
keyword_effectiveness[keyword] = {
    'tweets_found': len(tweets),
    'unique_tweets': unique_count,
    'weight': weight
}
```

### 4. **Let Classification Handle Relevance**
The LLM classifier determines relevance - we don't need volume-based pre-filtering.

## Implementation

```python
def search_tweets_optimized(keywords, max_tweets=300):
    """Conservative individual keyword search."""
    all_tweets = []
    tweets_by_id = {}  # For deduplication
    
    # Get conservative max_results (default: 10)
    max_results = settings.get('maxResultsPerKeyword', 10)
    
    # Calculate and warn about quota usage
    total_reads = len(keywords) * max_results
    remaining = quota_manager.get_remaining_quota()
    if (total_reads / remaining) > 0.20:
        logger.warning(f"⚠️ Will use {total_reads}/{remaining} reads!")
    
    # Search each keyword individually
    for keyword in keywords:
        # Build individual query
        if ' ' in keyword:
            query = f'"{keyword}" -is:retweet lang:en'
        else:
            query = f'{keyword} -is:retweet lang:en'
        
        # Search with conservative limits
        tweets = api.search(query, max_results=max_results)
        
        # Track effectiveness
        unique_count = 0
        for tweet in tweets:
            if tweet['id'] not in tweets_by_id:
                unique_count += 1
                tweet['matched_keyword'] = keyword
                tweets_by_id[tweet['id']] = tweet
        
        # Log performance
        logger.info(f"Keyword '{keyword}': {len(tweets)} found, {unique_count} unique")
        
        if len(tweets_by_id) >= max_tweets:
            break
    
    return list(tweets_by_id.values())[:max_tweets]
```

## Why This Approach?

1. **Keyword Tracking**: Know exactly which keywords are effective
2. **Quota Conservation**: 10 results uses 10x less quota than 100
3. **Development Safety**: Won't accidentally exhaust monthly quota
4. **Clear Attribution**: Each tweet linked to its discovering keyword
5. **No Confusion**: Individual searches = clear effectiveness metrics

## What We DON'T Do

❌ Batch keywords with OR operators (causes attribution confusion)  
❌ Use max_results=100 by default (quota killer)  
❌ Volume-based optimization (Counts API too limited)  
❌ Complex weight adjustments (let classification handle it)  

## Configuration

```python
# .env or settings
WDF_MAX_RESULTS_PER_KEYWORD=10  # Conservative default
WDF_MAX_RESULTS_PER_KEYWORD=25  # Moderate (for production)
WDF_MAX_RESULTS_PER_KEYWORD=100 # DANGER: Uses massive quota!
```

## Quota Math

With 10,000 monthly reads:
- **Conservative (10/keyword)**: ~1000 keyword searches/month
- **Moderate (25/keyword)**: ~400 keyword searches/month  
- **Aggressive (100/keyword)**: ~100 keyword searches/month ⚠️

For development with 20 keywords per episode:
- **10 results**: 200 reads (2% of monthly quota) ✅
- **100 results**: 2000 reads (20% of monthly quota) ⚠️

## The Bottom Line

With only 10,000 reads/month, we must be extremely conservative:
1. Search keywords individually for tracking
2. Default to 10 results per keyword
3. Let classification determine relevance
4. Monitor quota usage carefully
5. **Use boundary checkpoints to avoid duplicate fetches** (see [SEARCH_BOUNDARIES.md](SEARCH_BOUNDARIES.md))

This approach preserves quota during development while providing clear keyword effectiveness metrics.

## 🚀 Advanced: Boundary Checkpoint System

We've implemented the **"Checkpoint your runs"** strategy from the API conservation guide:
- Tracks first/last tweet IDs per keyword
- Uses `since_id`/`until_id` to avoid re-fetching
- Saves ~40% of API quota by preventing duplicates
- See [SEARCH_BOUNDARIES.md](SEARCH_BOUNDARIES.md) for details

## 📊 Enriched Data Collection

Following the **"One-pass enriched fetch"** strategy from the API conservation guide:
- Collects ALL available fields in single API requests
- Preserves user metrics, context annotations, source, media, etc.
- All enriched data flows through to classification and response generation
- Claude can leverage any fields for better decisions (no pre-filtering)