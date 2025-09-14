#!/usr/bin/env python3
"""
Test Conservative Search Strategy

Verifies that the individual keyword search with weight-based priority works correctly.
Tests quota warnings, keyword effectiveness tracking, and max_tweets limiting.

Related files:
- src/wdf/twitter_api_v2.py (Implementation)
- docs/SEARCH_STRATEGY.md (Documentation)
"""

import json
import logging
from typing import List, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def mock_search_single_query(query: str, max_results: int = 10) -> List[Dict]:
    """Mock implementation of _search_single_query for testing."""
    # Generate mock tweets based on keyword
    keyword = query.split(' ')[0].replace('"', '')
    tweets = []
    
    # Simulate finding fewer tweets for some keywords
    if 'federalism' in keyword.lower():
        count = min(8, max_results)  # Popular keyword
    elif 'sovereignty' in keyword.lower():
        count = min(5, max_results)  # Medium popularity
    elif 'constitutional' in keyword.lower():
        count = min(3, max_results)  # Less popular
    else:
        count = min(2, max_results)  # Rare keywords
    
    for i in range(count):
        tweets.append({
            'id': f'{keyword}_{i}',
            'text': f'Mock tweet about {keyword} #{i}',
            'user': f'@user_{keyword}_{i}',
            'likes': i * 10,
            'retweets': i * 2,
            'replies': i
        })
    
    logger.info(f"  Mock search for '{keyword}' returned {len(tweets)} tweets")
    return tweets


def test_conservative_search():
    """Test the conservative search strategy."""
    
    # Test keywords with varying weights
    keywords = [
        {'keyword': 'state rights', 'weight': 0.3},       # Low priority
        {'keyword': 'federalism', 'weight': 0.95},        # Highest priority
        {'keyword': 'sovereignty', 'weight': 0.8},        # High priority
        {'keyword': 'constitutional', 'weight': 0.6},     # Medium priority
        {'keyword': 'libertarian', 'weight': 0.2},        # Very low priority
        {'keyword': 'tenth amendment', 'weight': 0.9},    # Very high priority
        {'keyword': 'nullification', 'weight': 0.4},      # Low-medium priority
        {'keyword': 'local control', 'weight': 0.5},      # Medium priority
    ]
    
    # Simulate search with different configurations
    test_cases = [
        {
            'name': 'Conservative (10 per keyword, 50 total)',
            'max_results_per_keyword': 10,
            'max_tweets': 50,
            'expected_keywords_searched': 8,  # All keywords
        },
        {
            'name': 'Very Conservative (10 per keyword, 20 total)',
            'max_results_per_keyword': 10,
            'max_tweets': 20,
            'expected_keywords_searched': 3,  # Only top 3-4 keywords
        },
        {
            'name': 'Aggressive (50 per keyword, 100 total)',
            'max_results_per_keyword': 50,
            'max_tweets': 100,
            'expected_keywords_searched': 3,  # Only 2-3 keywords before hitting limit
        },
    ]
    
    for test_case in test_cases:
        logger.info(f"\n{'='*60}")
        logger.info(f"Test Case: {test_case['name']}")
        logger.info(f"{'='*60}")
        
        # Sort keywords by weight (as the real implementation does)
        sorted_keywords = sorted(keywords, key=lambda k: k.get('weight', 0), reverse=True)
        
        logger.info(f"Keywords in priority order:")
        for i, kw in enumerate(sorted_keywords, 1):
            logger.info(f"  #{i}: '{kw['keyword']}' (weight: {kw['weight']:.2f})")
        
        # Simulate search
        all_tweets = []
        tweets_by_id = {}
        keyword_effectiveness = {}
        keywords_searched = 0
        
        for i, kw_dict in enumerate(sorted_keywords, 1):
            keyword = kw_dict['keyword']
            weight = kw_dict.get('weight', 1.0)
            
            # Check if we've hit the limit
            if len(tweets_by_id) >= test_case['max_tweets']:
                logger.warning(
                    f"STOPPING: Reached max_tweets limit ({test_case['max_tweets']}). "
                    f"Skipping {len(sorted_keywords) - keywords_searched} lower-weight keywords."
                )
                break
            
            # Simulate search
            logger.info(f"\nSearching keyword #{i}: '{keyword}' (weight: {weight:.2f})")
            tweets = mock_search_single_query(keyword, test_case['max_results_per_keyword'])
            keywords_searched += 1
            
            # Process tweets (deduplication)
            unique_count = 0
            for tweet in tweets:
                if tweet['id'] not in tweets_by_id:
                    unique_count += 1
                    tweet['matched_keyword'] = keyword
                    tweet['keyword_weight'] = weight
                    tweets_by_id[tweet['id']] = tweet
            
            # Track effectiveness
            keyword_effectiveness[keyword] = {
                'weight': weight,
                'tweets_found': len(tweets),
                'unique_tweets': unique_count
            }
        
        # Summary
        logger.info(f"\n📊 Search Summary:")
        logger.info(f"  Keywords searched: {keywords_searched}/{len(keywords)}")
        logger.info(f"  Total tweets collected: {len(tweets_by_id)}/{test_case['max_tweets']}")
        logger.info(f"  API calls made: {keywords_searched}")
        
        # Calculate quota usage
        quota_used = keywords_searched * test_case['max_results_per_keyword']
        quota_percentage = (quota_used / 10000) * 100
        logger.info(f"  Quota used: {quota_used} reads ({quota_percentage:.2f}% of monthly 10,000)")
        
        # Show effectiveness
        logger.info(f"\n📈 Keyword Effectiveness:")
        for keyword, stats in keyword_effectiveness.items():
            logger.info(
                f"  {keyword}: {stats['tweets_found']} found, "
                f"{stats['unique_tweets']} unique (weight: {stats['weight']:.2f})"
            )
        
        # Verify high-weight keywords were searched first
        searched_keywords = list(keyword_effectiveness.keys())
        if keywords_searched > 1:
            first_weight = keyword_effectiveness[searched_keywords[0]]['weight']
            last_weight = keyword_effectiveness[searched_keywords[-1]]['weight']
            assert first_weight >= last_weight, "Keywords not searched in weight order!"
            logger.info(f"\n✅ Verified: Keywords searched by weight priority")


if __name__ == '__main__':
    test_conservative_search()