"""
Tweet Cache Manager

Manages a local cache of previously scraped tweets to enable pipeline testing
without making new API calls. Tweets are stored chronologically and can be
retrieved for testing purposes.

Related files:
- src/wdf/tasks/scrape.py (Uses cache when API calls are disabled)
- artefacts/tweet_cache.json (Persistent cache file)
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import structlog

logger = structlog.get_logger(__name__)

class TweetCache:
    """Manages cached tweets for testing without API calls"""
    
    def __init__(self, cache_file: str = "artefacts/tweet_cache.json"):
        # Make cache file path absolute to avoid working directory issues
        if not Path(cache_file).is_absolute():
            # Find project root by looking for pyproject.toml
            current_dir = Path(__file__).parent
            while current_dir != current_dir.parent:
                if (current_dir / "pyproject.toml").exists():
                    cache_file = str(current_dir / cache_file)
                    break
                current_dir = current_dir.parent
        self.cache_file = Path(cache_file)
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self._cache = None
        self.max_cache_size = 10000  # Maximum tweets to keep in cache
        self.max_age_days = 90  # Maximum age of cached tweets
    
    def _load_cache(self) -> Dict:
        """Load cache from file"""
        if self._cache is not None:
            return self._cache
            
        if self.cache_file.exists():
            try:
                with open(self.cache_file) as f:
                    self._cache = json.load(f)
                    if not isinstance(self._cache, dict):
                        self._cache = {"tweets": [], "last_updated": None}
                    print(f"🔍 CACHE DEBUG: Loaded tweet cache from {self.cache_file} with {len(self._cache.get('tweets', []))} tweets")
                    logger.info(f"Loaded tweet cache with {len(self._cache.get('tweets', []))} tweets")
            except (json.JSONDecodeError, IOError) as e:
                print(f"🔍 CACHE DEBUG: Failed to load tweet cache from {self.cache_file}: {e}")
                logger.warning(f"Failed to load tweet cache: {e}")
                self._cache = {"tweets": [], "last_updated": None}
        else:
            print(f"🔍 CACHE DEBUG: Cache file not found at {self.cache_file}")
            self._cache = {"tweets": [], "last_updated": None}
        
        return self._cache
    
    def _save_cache(self):
        """Save cache to file"""
        if self._cache is None:
            return
            
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self._cache, f, indent=2)
            logger.info(f"Saved tweet cache with {len(self._cache.get('tweets', []))} tweets")
        except IOError as e:
            logger.error(f"Failed to save tweet cache: {e}")
    
    def add_tweets(self, tweets: List[Dict]):
        """Add new tweets to the cache"""
        cache = self._load_cache()
        
        # Add unique tweets (by ID)
        existing_ids = {t.get('id') for t in cache['tweets']}
        new_tweets = [t for t in tweets if t.get('id') not in existing_ids]
        
        if new_tweets:
            cache['tweets'].extend(new_tweets)
            cache['last_updated'] = datetime.now().isoformat()
            
            # Sort by created_at (newest first)
            cache['tweets'].sort(
                key=lambda t: t.get('created_at', ''),
                reverse=True
            )
            
            # Trim cache to size limit
            if len(cache['tweets']) > self.max_cache_size:
                cache['tweets'] = cache['tweets'][:self.max_cache_size]
            
            self._save_cache()
            logger.info(f"Added {len(new_tweets)} new tweets to cache")
    
    def get_tweets(self, count: int = 100, keywords: Optional[List[str]] = None) -> List[Dict]:
        """
        Get tweets from cache
        
        Args:
            count: Number of tweets to retrieve
            keywords: Optional keywords to filter tweets (basic substring matching)
            
        Returns:
            List of tweet dictionaries
        """
        cache = self._load_cache()
        tweets = cache.get('tweets', [])
        
        # Filter out old tweets
        cutoff_date = (datetime.now() - timedelta(days=self.max_age_days)).isoformat()
        tweets = [t for t in tweets if t.get('created_at', '') > cutoff_date]
        
        # Filter by keywords if provided
        if keywords:
            filtered_tweets = []
            for tweet in tweets:
                # First try to match by exact matched_keyword field
                matched_keyword = tweet.get('matched_keyword', '')
                if matched_keyword.lower() in [kw.lower() for kw in keywords]:
                    filtered_tweets.append(tweet)
                    continue

                # Fallback to text content matching for backwards compatibility
                tweet_text = tweet.get('text', '').lower()
                if any(keyword.lower() in tweet_text for keyword in keywords):
                    filtered_tweets.append(tweet)
            tweets = filtered_tweets
        
        # Sort by created_at (oldest first) for consistent retrieval order
        tweets.sort(key=lambda t: t.get('created_at', ''))
        
        # Return requested count
        result = tweets[:count]

        print(f"🔍 CACHE DEBUG: get_tweets called with keywords={keywords}, count={count}")
        print(f"🔍 CACHE DEBUG: Found {len(result)} tweets after filtering from {len(cache.get('tweets', []))} total")

        logger.info(
            f"Retrieved {len(result)} tweets from cache",
            total_cached=len(cache.get('tweets', [])),
            filtered_by_keywords=bool(keywords)
        )

        return result
    
    def clear_old_tweets(self):
        """Remove tweets older than max_age_days"""
        cache = self._load_cache()
        original_count = len(cache.get('tweets', []))
        
        cutoff_date = (datetime.now() - timedelta(days=self.max_age_days)).isoformat()
        cache['tweets'] = [
            t for t in cache.get('tweets', [])
            if t.get('created_at', '') > cutoff_date
        ]
        
        removed = original_count - len(cache['tweets'])
        if removed > 0:
            cache['last_updated'] = datetime.now().isoformat()
            self._save_cache()
            logger.info(f"Removed {removed} old tweets from cache")
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        cache = self._load_cache()
        tweets = cache.get('tweets', [])
        
        if not tweets:
            return {
                'total_tweets': 0,
                'oldest_tweet': None,
                'newest_tweet': None,
                'last_updated': cache.get('last_updated')
            }
        
        # Sort to find oldest and newest
        sorted_tweets = sorted(tweets, key=lambda t: t.get('created_at', ''))
        
        return {
            'total_tweets': len(tweets),
            'oldest_tweet': sorted_tweets[0].get('created_at') if sorted_tweets else None,
            'newest_tweet': sorted_tweets[-1].get('created_at') if sorted_tweets else None,
            'last_updated': cache.get('last_updated'),
            'cache_file': str(self.cache_file)
        }


# Global cache instance
_tweet_cache = None

def get_tweet_cache() -> TweetCache:
    """Get or create the global tweet cache instance"""
    global _tweet_cache
    if _tweet_cache is None:
        _tweet_cache = TweetCache()
    return _tweet_cache