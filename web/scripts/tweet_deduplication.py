#!/usr/bin/env python3
"""
Tweet Deduplication Service
Checks for existing tweets in database before making Twitter API calls
This prevents unnecessary API quota usage by avoiding re-fetching tweets we already have
"""

import os
import sys
import logging
from typing import List, Set, Dict, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from web_bridge import WebUIBridge

logger = logging.getLogger(__name__)


class TweetDeduplicationService:
    """Service to check for existing tweets and avoid duplicate API calls"""
    
    def __init__(self):
        self.bridge = WebUIBridge()
        
    def get_existing_tweet_ids(self, 
                              keywords: List[str] = None,
                              days_back: int = 30,
                              episode_id: int = None) -> Set[str]:
        """
        Get Twitter IDs of tweets we already have in the database.
        
        Args:
            keywords: Optional keywords to filter by (checks if tweet text contains any keyword)
            days_back: How many days back to check for existing tweets
            episode_id: Optional episode ID to check episode-specific tweets
            
        Returns:
            Set of Twitter IDs we already have
        """
        try:
            with self.bridge.connection.cursor() as cursor:
                # Build query based on parameters
                query = """
                    SELECT DISTINCT twitter_id 
                    FROM tweets 
                    WHERE created_at >= %s
                """
                params = [datetime.now() - timedelta(days=days_back)]
                
                # Add episode filter if provided
                if episode_id:
                    query += " AND episode_id = %s"
                    params.append(episode_id)
                
                # Add keyword filter if provided
                if keywords:
                    # Create OR conditions for each keyword
                    keyword_conditions = []
                    for keyword in keywords[:20]:  # Limit to first 20 keywords for query efficiency
                        keyword_conditions.append("LOWER(full_text) LIKE %s")
                        params.append(f"%{keyword.lower()}%")
                    
                    if keyword_conditions:
                        query += f" AND ({' OR '.join(keyword_conditions)})"
                
                cursor.execute(query, params)
                results = cursor.fetchall()
                
                existing_ids = {row[0] for row in results}
                
                logger.info(
                    f"Found {len(existing_ids)} existing tweets in database",
                    extra={
                        "days_back": days_back,
                        "keyword_count": len(keywords) if keywords else 0,
                        "episode_id": episode_id
                    }
                )
                
                return existing_ids
                
        except Exception as e:
            logger.error(f"Failed to get existing tweet IDs: {e}")
            return set()
    
    def get_tweets_needing_refresh(self,
                                  existing_ids: Set[str],
                                  days_old: int = 7) -> Set[str]:
        """
        Get tweets that might need refreshing (e.g., updated metrics).
        
        Args:
            existing_ids: Set of existing tweet IDs
            days_old: How old tweets should be before considering refresh
            
        Returns:
            Set of tweet IDs that could be refreshed
        """
        if not existing_ids:
            return set()
            
        try:
            with self.bridge.connection.cursor() as cursor:
                # Find tweets that haven't been updated recently
                placeholders = ','.join(['%s'] * len(existing_ids))
                query = f"""
                    SELECT twitter_id 
                    FROM tweets 
                    WHERE twitter_id IN ({placeholders})
                    AND updated_at < %s
                    AND status != 'replied'  -- Don't refresh tweets we've already replied to
                """
                
                params = list(existing_ids) + [datetime.now() - timedelta(days=days_old)]
                cursor.execute(query, params)
                
                results = cursor.fetchall()
                refresh_ids = {row[0] for row in results}
                
                if refresh_ids:
                    logger.info(f"Found {len(refresh_ids)} tweets that could be refreshed (>={days_old} days old)")
                
                return refresh_ids
                
        except Exception as e:
            logger.error(f"Failed to get tweets needing refresh: {e}")
            return set()
    
    def estimate_api_savings(self,
                            keywords: List[str],
                            max_tweets: int,
                            existing_count: int) -> Dict[str, int]:
        """
        Estimate how many API calls we're saving by checking existing tweets.
        
        Args:
            keywords: Keywords for search
            max_tweets: Maximum tweets requested
            existing_count: Number of existing tweets found
            
        Returns:
            Dictionary with savings estimates
        """
        # Estimate API calls needed without deduplication
        calls_without_dedup = min(len(keywords) * 10, max_tweets)  # Assuming 10 results per keyword
        
        # Estimate API calls needed with deduplication
        new_tweets_needed = max(0, max_tweets - existing_count)
        calls_with_dedup = min(len(keywords) * 5, new_tweets_needed)  # Fewer calls needed
        
        savings = {
            "api_calls_saved": max(0, calls_without_dedup - calls_with_dedup),
            "tweets_reused": existing_count,
            "new_tweets_needed": new_tweets_needed,
            "estimated_quota_saved": max(0, calls_without_dedup - calls_with_dedup) * 100  # Each call can return up to 100 tweets
        }
        
        logger.info(
            f"Deduplication savings estimate: {savings['api_calls_saved']} API calls saved, "
            f"{savings['tweets_reused']} tweets reused from database"
        )
        
        return savings
    
    def get_recent_tweets_for_keywords(self,
                                      keywords: List[str],
                                      max_tweets: int = 100,
                                      days_back: int = 7) -> Tuple[List[Dict], Dict[str, int]]:
        """
        Get existing tweets from database that match keywords.
        
        Args:
            keywords: Keywords to search for
            max_tweets: Maximum number of tweets to return
            days_back: How many days back to search
            
        Returns:
            Tuple of (tweets, statistics)
        """
        try:
            from psycopg2.extras import RealDictCursor
            
            with self.bridge.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                # Build keyword search query
                keyword_conditions = []
                params = []
                
                for keyword in keywords[:20]:  # Limit keywords for query efficiency
                    keyword_conditions.append("LOWER(full_text) LIKE %s")
                    params.append(f"%{keyword.lower()}%")
                
                query = f"""
                    SELECT 
                        twitter_id as id,
                        author_handle as user,
                        full_text as text,
                        created_at,
                        relevance_score,
                        status
                    FROM tweets
                    WHERE created_at >= %s
                    AND ({' OR '.join(keyword_conditions)})
                    ORDER BY relevance_score DESC NULLS LAST, created_at DESC
                    LIMIT %s
                """
                
                params = [datetime.now() - timedelta(days=days_back)] + params + [max_tweets]
                cursor.execute(query, params)
                
                tweets = cursor.fetchall()
                
                # Convert to list of dicts
                tweet_list = [dict(tweet) for tweet in tweets]
                
                # Calculate statistics
                stats = {
                    "total_found": len(tweet_list),
                    "relevant_count": sum(1 for t in tweet_list if t.get('status') == 'relevant'),
                    "unclassified_count": sum(1 for t in tweet_list if t.get('status') == 'unclassified'),
                    "days_searched": days_back,
                    "keywords_used": len(keywords)
                }
                
                logger.info(
                    f"Retrieved {stats['total_found']} existing tweets from database",
                    extra=stats
                )
                
                return tweet_list, stats
                
        except Exception as e:
            logger.error(f"Failed to get recent tweets: {e}")
            return [], {}


def check_before_scraping(keywords: List[str],
                         max_tweets: int = 100,
                         days_back: int = 7,
                         episode_id: int = None) -> Dict:
    """
    Check for existing tweets before making API calls.
    
    This function should be called BEFORE initiating Twitter API scraping
    to avoid re-fetching tweets we already have.
    
    Args:
        keywords: Keywords for tweet search
        max_tweets: Maximum tweets needed
        days_back: How far back to search
        episode_id: Optional episode ID
        
    Returns:
        Dictionary with deduplication results and recommendations
    """
    service = TweetDeduplicationService()
    
    # Get existing tweets from database
    existing_tweets, stats = service.get_recent_tweets_for_keywords(
        keywords=keywords,
        max_tweets=max_tweets,
        days_back=days_back
    )
    
    # Get existing tweet IDs
    existing_ids = service.get_existing_tweet_ids(
        keywords=keywords,
        days_back=days_back,
        episode_id=episode_id
    )
    
    # Calculate savings
    savings = service.estimate_api_savings(
        keywords=keywords,
        max_tweets=max_tweets,
        existing_count=len(existing_tweets)
    )
    
    # Build recommendations
    recommendations = []
    
    if len(existing_tweets) >= max_tweets * 0.8:
        recommendations.append(
            f"SKIP API CALL: Already have {len(existing_tweets)}/{max_tweets} tweets needed. "
            "Consider using existing tweets instead."
        )
        skip_api = True
    elif len(existing_tweets) >= max_tweets * 0.5:
        recommendations.append(
            f"PARTIAL FETCH: Have {len(existing_tweets)}/{max_tweets} tweets. "
            f"Only fetch {max_tweets - len(existing_tweets)} new tweets."
        )
        skip_api = False
    else:
        recommendations.append(
            f"PROCEED WITH FETCH: Only {len(existing_tweets)}/{max_tweets} existing tweets found."
        )
        skip_api = False
    
    # Check for stale tweets
    if existing_ids:
        refresh_ids = service.get_tweets_needing_refresh(existing_ids, days_old=7)
        if refresh_ids:
            recommendations.append(
                f"Consider refreshing {len(refresh_ids)} tweets that are >7 days old."
            )
    
    return {
        "existing_tweets": existing_tweets,
        "existing_count": len(existing_tweets),
        "existing_ids": list(existing_ids),
        "new_tweets_needed": max(0, max_tweets - len(existing_tweets)),
        "skip_api_call": skip_api,
        "savings": savings,
        "stats": stats,
        "recommendations": recommendations
    }


if __name__ == "__main__":
    # Test the deduplication service
    import json
    
    logging.basicConfig(level=logging.INFO)
    
    # Test keywords
    test_keywords = ["federalism", "state sovereignty", "constitution"]
    
    print("🔍 Testing Tweet Deduplication Service\n")
    print(f"Keywords: {test_keywords}")
    print(f"Max tweets: 100")
    print(f"Days back: 7\n")
    
    # Check for existing tweets
    results = check_before_scraping(
        keywords=test_keywords,
        max_tweets=100,
        days_back=7
    )
    
    print(f"📊 Results:")
    print(f"  Existing tweets found: {results['existing_count']}")
    print(f"  New tweets needed: {results['new_tweets_needed']}")
    print(f"  Skip API call: {results['skip_api_call']}")
    
    print(f"\n💰 Savings:")
    for key, value in results['savings'].items():
        print(f"  {key}: {value}")
    
    print(f"\n📋 Recommendations:")
    for rec in results['recommendations']:
        print(f"  • {rec}")
    
    if results['existing_tweets']:
        print(f"\n📝 Sample existing tweets:")
        for tweet in results['existing_tweets'][:3]:
            print(f"  @{tweet['user']}: {tweet['text'][:100]}...")