#!/usr/bin/env python3
"""
Keyword Search Cache Service
Tracks keyword searches and their results to avoid redundant Twitter API calls.
Caches search results for 4 days to optimize API quota usage.
"""

import os
import sys
import json
import logging
from typing import List, Dict, Set, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from web_bridge import WebUIBridge

logger = logging.getLogger(__name__)


class SearchCacheService:
    """Service to cache keyword search results and prevent redundant API calls"""
    
    def __init__(self, cache_days: int = 4):
        """
        Initialize the search cache service.
        
        Args:
            cache_days: Number of days to cache search results (default: 4)
        """
        self.bridge = WebUIBridge()
        self.cache_days = cache_days
        self.cache_hours = cache_days * 24
        
    def check_keyword_cache(self, 
                           keyword: str, 
                           episode_id: int = None,
                           max_age_hours: int = None) -> Dict:
        """
        Check if a keyword has been searched recently and return cached results.
        
        Args:
            keyword: The keyword to check
            episode_id: Optional episode ID for episode-specific searches
            max_age_hours: Maximum age of cache entry to consider valid (default: 4 days)
            
        Returns:
            Dictionary with cache information:
            - cached: Boolean indicating if valid cache exists
            - tweet_ids: List of tweet IDs from cached search
            - searched_at: When the search was performed
            - hours_old: How old the cache entry is
        """
        if max_age_hours is None:
            max_age_hours = self.cache_hours
            
        try:
            with self.bridge.connection.cursor() as cursor:
                # Check for recent search of this keyword
                query = """
                    SELECT 
                        id,
                        searched_at,
                        tweet_ids,
                        tweet_count,
                        EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - searched_at))/3600 as hours_old
                    FROM keyword_search_cache
                    WHERE keyword = %s
                    AND expires_at > CURRENT_TIMESTAMP
                    AND searched_at > CURRENT_TIMESTAMP - INTERVAL '%s hours'
                """
                params = [keyword, max_age_hours]
                
                # Add episode filter if specified
                if episode_id:
                    query += " AND episode_id = %s"
                    params.append(episode_id)
                
                query += " ORDER BY searched_at DESC LIMIT 1"
                
                cursor.execute(query, params)
                result = cursor.fetchone()
                
                if result:
                    cache_id, searched_at, tweet_ids, tweet_count, hours_old = result
                    
                    logger.info(
                        f"Found cached search for '{keyword}' from {hours_old:.1f} hours ago "
                        f"with {len(tweet_ids) if tweet_ids else 0} tweets"
                    )
                    
                    return {
                        'cached': True,
                        'cache_id': cache_id,
                        'tweet_ids': tweet_ids or [],
                        'tweet_count': tweet_count,
                        'searched_at': searched_at,
                        'hours_old': hours_old,
                        'keyword': keyword
                    }
                else:
                    logger.info(f"No recent cache found for keyword '{keyword}'")
                    return {
                        'cached': False,
                        'keyword': keyword
                    }
                    
        except Exception as e:
            logger.error(f"Failed to check keyword cache: {e}")
            return {'cached': False, 'keyword': keyword, 'error': str(e)}
    
    def check_multiple_keywords(self, 
                               keywords: List[str],
                               episode_id: int = None) -> Dict[str, Dict]:
        """
        Check cache status for multiple keywords at once.
        
        Args:
            keywords: List of keywords to check
            episode_id: Optional episode ID
            
        Returns:
            Dictionary mapping keywords to their cache status
        """
        results = {}
        
        for keyword in keywords:
            results[keyword] = self.check_keyword_cache(keyword, episode_id)
        
        # Calculate summary statistics
        cached_count = sum(1 for r in results.values() if r['cached'])
        total_cached_tweets = sum(len(r.get('tweet_ids', [])) for r in results.values() if r['cached'])
        
        logger.info(
            f"Cache check complete: {cached_count}/{len(keywords)} keywords cached "
            f"with {total_cached_tweets} total tweets available"
        )
        
        return {
            'keywords': results,
            'summary': {
                'total_keywords': len(keywords),
                'cached_keywords': cached_count,
                'uncached_keywords': len(keywords) - cached_count,
                'total_cached_tweets': total_cached_tweets,
                'cache_hit_rate': (cached_count / len(keywords) * 100) if keywords else 0
            }
        }
    
    def save_search_results(self,
                          keyword: str,
                          tweet_ids: List[str],
                          episode_id: int = None,
                          search_params: Dict = None,
                          api_calls_used: int = 1) -> bool:
        """
        Save search results to cache for future reuse.
        
        Args:
            keyword: The keyword that was searched
            tweet_ids: List of tweet IDs returned from the search
            episode_id: Optional episode ID
            search_params: Search parameters used (days_back, max_results, etc.)
            api_calls_used: Number of API calls this search consumed
            
        Returns:
            Boolean indicating success
        """
        try:
            with self.bridge.connection.cursor() as cursor:
                # Insert new cache entry
                cursor.execute("""
                    INSERT INTO keyword_search_cache 
                    (keyword, searched_at, episode_id, tweet_count, tweet_ids, 
                     search_params, api_calls_used, expires_at)
                    VALUES (%s, CURRENT_TIMESTAMP, %s, %s, %s, %s, %s, 
                            CURRENT_TIMESTAMP + INTERVAL '%s days')
                    RETURNING id
                """, (
                    keyword,
                    episode_id,
                    len(tweet_ids),
                    tweet_ids,
                    json.dumps(search_params) if search_params else None,
                    api_calls_used,
                    self.cache_days
                ))
                
                cache_id = cursor.fetchone()[0]
                
                # Update tweets with search metadata
                if tweet_ids:
                    placeholders = ','.join(['%s'] * len(tweet_ids))
                    cursor.execute(f"""
                        UPDATE tweets 
                        SET search_keywords = array_append(
                            COALESCE(search_keywords, '{{}}'), %s
                        ),
                        last_search_date = CURRENT_TIMESTAMP
                        WHERE twitter_id IN ({placeholders})
                    """, [keyword] + tweet_ids)
                
                self.bridge.connection.commit()
                
                logger.info(
                    f"Cached search results for '{keyword}': "
                    f"{len(tweet_ids)} tweets, {api_calls_used} API calls used"
                )
                
                return True
                
        except Exception as e:
            self.bridge.connection.rollback()
            logger.error(f"Failed to save search results: {e}")
            return False
    
    def get_cached_tweets(self, 
                         cached_keywords: Dict[str, Dict]) -> Tuple[List[Dict], Set[str]]:
        """
        Retrieve actual tweet data for cached keyword searches.
        
        Args:
            cached_keywords: Dictionary of cached keyword results
            
        Returns:
            Tuple of (tweets list, tweet_ids set)
        """
        all_tweet_ids = set()
        
        # Collect all tweet IDs from cached searches
        for keyword, cache_info in cached_keywords.items():
            if cache_info.get('cached') and cache_info.get('tweet_ids'):
                all_tweet_ids.update(cache_info['tweet_ids'])
        
        if not all_tweet_ids:
            return [], set()
        
        try:
            from psycopg2.extras import RealDictCursor
            
            with self.bridge.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                # Fetch full tweet data for cached IDs
                placeholders = ','.join(['%s'] * len(all_tweet_ids))
                cursor.execute(f"""
                    SELECT 
                        twitter_id as id,
                        author_handle as user,
                        full_text as text,
                        created_at,
                        relevance_score,
                        status,
                        search_keywords
                    FROM tweets
                    WHERE twitter_id IN ({placeholders})
                    ORDER BY created_at DESC
                """, list(all_tweet_ids))
                
                tweets = [dict(row) for row in cursor.fetchall()]
                
                logger.info(f"Retrieved {len(tweets)} cached tweets from database")
                
                return tweets, all_tweet_ids
                
        except Exception as e:
            logger.error(f"Failed to get cached tweets: {e}")
            return [], set()
    
    def get_cache_statistics(self, days: int = 30) -> Dict:
        """
        Get statistics about search cache usage.
        
        Args:
            days: Number of days to look back for statistics
            
        Returns:
            Dictionary with cache statistics
        """
        try:
            with self.bridge.connection.cursor() as cursor:
                # Overall statistics
                cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT keyword) as unique_keywords,
                        COUNT(*) as total_searches,
                        SUM(tweet_count) as total_tweets_cached,
                        SUM(api_calls_used) as total_api_calls_used,
                        AVG(tweet_count) as avg_tweets_per_search
                    FROM keyword_search_cache
                    WHERE searched_at > CURRENT_TIMESTAMP - INTERVAL '%s days'
                """, (days,))
                
                overall = cursor.fetchone()
                
                # Active cache entries
                cursor.execute("""
                    SELECT COUNT(*) as active_entries,
                           SUM(tweet_count) as active_tweets
                    FROM keyword_search_cache
                    WHERE expires_at > CURRENT_TIMESTAMP
                """)
                
                active = cursor.fetchone()
                
                # Most searched keywords
                cursor.execute("""
                    SELECT keyword, COUNT(*) as search_count
                    FROM keyword_search_cache
                    WHERE searched_at > CURRENT_TIMESTAMP - INTERVAL '%s days'
                    GROUP BY keyword
                    ORDER BY search_count DESC
                    LIMIT 10
                """, (days,))
                
                top_keywords = cursor.fetchall()
                
                return {
                    'period_days': days,
                    'unique_keywords': overall[0] or 0,
                    'total_searches': overall[1] or 0,
                    'total_tweets_cached': overall[2] or 0,
                    'total_api_calls_used': overall[3] or 0,
                    'avg_tweets_per_search': float(overall[4] or 0),
                    'active_cache_entries': active[0] or 0,
                    'active_cached_tweets': active[1] or 0,
                    'top_keywords': [{'keyword': k, 'count': c} for k, c in top_keywords]
                }
                
        except Exception as e:
            logger.error(f"Failed to get cache statistics: {e}")
            return {}
    
    def cleanup_expired_cache(self) -> int:
        """
        Remove expired cache entries older than cache_days.
        
        Returns:
            Number of entries deleted
        """
        try:
            with self.bridge.connection.cursor() as cursor:
                cursor.execute("SELECT cleanup_expired_search_cache()")
                deleted = cursor.fetchone()[0]
                self.bridge.connection.commit()
                
                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} expired cache entries")
                
                return deleted
                
        except Exception as e:
            logger.error(f"Failed to cleanup expired cache: {e}")
            return 0


def optimize_keyword_search(keywords: List[str],
                           max_tweets: int = 100,
                           episode_id: int = None,
                           force_refresh: bool = False) -> Dict:
    """
    Optimize keyword search by using cached results where available.
    
    This is the main function to call before making Twitter API searches.
    It will check cache for all keywords and return information about
    what's cached and what needs to be fetched.
    
    Args:
        keywords: List of keywords to search
        max_tweets: Maximum tweets needed
        episode_id: Optional episode ID
        force_refresh: If True, ignore cache and fetch fresh data
        
    Returns:
        Dictionary with optimization results:
        - cached_tweets: Tweets available from cache
        - cached_keywords: Keywords that have cached results
        - keywords_to_search: Keywords that need API calls
        - estimated_api_calls_saved: Number of API calls saved by using cache
        - recommendations: List of optimization recommendations
    """
    if force_refresh:
        logger.info("Force refresh requested, ignoring cache")
        return {
            'cached_tweets': [],
            'cached_keywords': [],
            'keywords_to_search': keywords,
            'estimated_api_calls_saved': 0,
            'recommendations': ["Force refresh mode - all keywords will be searched"]
        }
    
    service = SearchCacheService()
    
    # Check cache for all keywords
    cache_results = service.check_multiple_keywords(keywords, episode_id)
    
    # Separate cached and uncached keywords
    cached_keywords = []
    keywords_to_search = []
    
    for keyword in keywords:
        if cache_results['keywords'][keyword]['cached']:
            cached_keywords.append(keyword)
        else:
            keywords_to_search.append(keyword)
    
    # Get cached tweets
    cached_tweets, cached_tweet_ids = service.get_cached_tweets(cache_results['keywords'])
    
    # Calculate savings
    estimated_api_calls_saved = len(cached_keywords)  # Each keyword search is 1+ API calls
    
    # Build recommendations
    recommendations = []
    
    if len(cached_tweets) >= max_tweets:
        recommendations.append(
            f"✅ SKIP ALL API CALLS: Have {len(cached_tweets)} cached tweets, "
            f"need only {max_tweets}. Use cached results."
        )
    elif len(cached_tweets) >= max_tweets * 0.7:
        recommendations.append(
            f"⚠️ MINIMAL API CALLS: Have {len(cached_tweets)} cached tweets. "
            f"Only need {max_tweets - len(cached_tweets)} more."
        )
    elif cached_keywords:
        recommendations.append(
            f"💾 PARTIAL CACHE HIT: Reusing {len(cached_keywords)} cached keyword searches "
            f"({len(cached_tweets)} tweets). Need to search {len(keywords_to_search)} keywords."
        )
    else:
        recommendations.append(
            f"🔍 NO CACHE: All {len(keywords)} keywords need API searches."
        )
    
    # Add cache freshness info
    for keyword in cached_keywords[:3]:  # Show first 3 cached keywords
        cache_info = cache_results['keywords'][keyword]
        recommendations.append(
            f"  • '{keyword}' cached {cache_info['hours_old']:.1f} hours ago "
            f"({len(cache_info['tweet_ids'])} tweets)"
        )
    
    # Statistics
    stats = cache_results['summary']
    recommendations.append(
        f"📊 Cache hit rate: {stats['cache_hit_rate']:.1f}% "
        f"({stats['cached_keywords']}/{stats['total_keywords']} keywords)"
    )
    
    return {
        'cached_tweets': cached_tweets,
        'cached_tweet_ids': list(cached_tweet_ids),
        'cached_keywords': cached_keywords,
        'keywords_to_search': keywords_to_search,
        'estimated_api_calls_saved': estimated_api_calls_saved,
        'cache_stats': stats,
        'recommendations': recommendations,
        'skip_all_api_calls': len(cached_tweets) >= max_tweets
    }


if __name__ == "__main__":
    # Test the search cache service
    import argparse
    
    logging.basicConfig(level=logging.INFO)
    
    parser = argparse.ArgumentParser(description="Search Cache Service")
    parser.add_argument('command', choices=['check', 'stats', 'cleanup', 'test'],
                       help='Command to execute')
    parser.add_argument('--keywords', nargs='+', 
                       default=["federalism", "constitution", "states rights"],
                       help='Keywords to check')
    parser.add_argument('--cleanup', action='store_true',
                       help='Cleanup expired cache entries')
    
    args = parser.parse_args()
    
    if args.command == 'check':
        # Check cache for keywords
        print(f"🔍 Checking cache for keywords: {args.keywords}\n")
        
        results = optimize_keyword_search(args.keywords)
        
        print("📊 Results:")
        print(f"  Cached tweets: {len(results['cached_tweets'])}")
        print(f"  Cached keywords: {results['cached_keywords']}")
        print(f"  Keywords to search: {results['keywords_to_search']}")
        print(f"  API calls saved: {results['estimated_api_calls_saved']}")
        
        print("\n💡 Recommendations:")
        for rec in results['recommendations']:
            print(f"  {rec}")
    
    elif args.command == 'stats':
        # Get cache statistics
        service = SearchCacheService()
        stats = service.get_cache_statistics()
        
        print("📈 Search Cache Statistics (Last 30 Days)\n")
        print(f"  Unique keywords: {stats['unique_keywords']}")
        print(f"  Total searches: {stats['total_searches']}")
        print(f"  Total tweets cached: {stats['total_tweets_cached']}")
        print(f"  Total API calls used: {stats['total_api_calls_used']}")
        print(f"  Average tweets per search: {stats['avg_tweets_per_search']:.1f}")
        print(f"  Active cache entries: {stats['active_cache_entries']}")
        print(f"  Active cached tweets: {stats['active_cached_tweets']}")
        
        if stats.get('top_keywords'):
            print("\n🔝 Top Keywords:")
            for kw in stats['top_keywords']:
                print(f"    {kw['keyword']}: {kw['count']} searches")
    
    elif args.command == 'cleanup':
        # Cleanup expired cache
        service = SearchCacheService()
        deleted = service.cleanup_expired_cache()
        print(f"🧹 Cleaned up {deleted} expired cache entries")
    
    elif args.command == 'test':
        # Test saving and retrieving
        service = SearchCacheService()
        
        # Test save
        test_keyword = "test_federalism"
        test_tweets = ["1234567890", "0987654321", "1111111111"]
        
        print(f"💾 Saving test search for '{test_keyword}'...")
        success = service.save_search_results(
            keyword=test_keyword,
            tweet_ids=test_tweets,
            search_params={'days_back': 7, 'max_results': 100}
        )
        
        if success:
            print("✅ Save successful")
            
            # Test retrieve
            print(f"\n🔍 Checking cache for '{test_keyword}'...")
            result = service.check_keyword_cache(test_keyword)
            
            if result['cached']:
                print(f"✅ Cache found: {len(result['tweet_ids'])} tweets")
                print(f"   Cached {result['hours_old']:.1f} hours ago")
            else:
                print("❌ Cache not found")
        else:
            print("❌ Save failed")