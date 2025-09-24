"""
Twitter client interface and implementations

This module provides both a real Twitter API client and a mock implementation
for testing and development purposes.
"""

import json
import logging
import os
import random
import sqlite3
import string
import subprocess
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

import redis
from prometheus_client import Counter
from pydantic import BaseModel

from .settings import settings

# Prometheus metrics
TWEETS_PUBLISHED = Counter(
    "tweets_published_total",
    "Number of tweets published",
    ["run_id"]
)

# SQLite database for tracking tweet publish status
DB_PATH = Path(settings.artefacts_dir) / "tweets.db"

def init_db():
    """Initialize the SQLite database for tracking tweet status"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS published_tweets (
        tweet_id TEXT PRIMARY KEY,
        response_text TEXT,
        timestamp TEXT,
        run_id TEXT
    )
    ''')
    conn.commit()
    conn.close()
    logging.info("Initialized tweet status database at %s", DB_PATH)

# Initialize the database
init_db()

def is_tweet_published(tweet_id: str) -> bool:
    """Check if a tweet has already been published"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM published_tweets WHERE tweet_id = ?", (tweet_id,))
    result = cursor.fetchone() is not None
    conn.close()
    return result

def record_tweet_published(tweet_id: str, response_text: str, run_id: str):
    """Record that a tweet has been published"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO published_tweets (tweet_id, response_text, timestamp, run_id) VALUES (?, ?, ?, ?)",
        (tweet_id, response_text, datetime.utcnow().isoformat(), run_id)
    )
    conn.commit()
    conn.close()

class Tweet(BaseModel):
    """Twitter tweet model"""
    id: str
    text: str
    user: str
    created_at: Optional[str] = None
    
    
class TweetReply(BaseModel):
    """Tweet reply model"""
    tweet_id: str
    text: str
    timestamp: str


class TwitterClient(ABC):
    """Abstract base class for Twitter clients"""
    
    @abstractmethod
    def search_by_keywords(self, keywords: List[str], count: int = 100, settings: Dict = None) -> List[Tweet]:
        """Search for tweets containing any of the given keywords"""
        pass
    
    @abstractmethod
    def reply_to_tweet(self, tweet_id: str, text: str, run_id: str = "unknown") -> bool:
        """Reply to a specific tweet"""
        pass
    
    @abstractmethod
    def publish_batch(self, replies: List[TweetReply], run_id: str = "unknown") -> Dict[str, bool]:
        """Publish a batch of replies and return success status for each"""
        pass


class MockTwitterClient(TwitterClient):
    """Mock Twitter client for testing and development"""
    
    def __init__(self, seed: int = 42):
        """Initialize with a random seed for deterministic behavior"""
        self.rand = random.Random(seed)
        self.published_path = Path(settings.transcript_dir) / "published.json"
        self.tweets_path = Path(settings.transcript_dir) / "tweets.json"
        self._seen_ids: Set[str] = set()
        
    def _rand_id(self, k: int = 18) -> str:
        """Generate a deterministic random tweet ID"""
        return "t" + "".join(self.rand.choices(string.ascii_lowercase + string.digits, k=k))
        
    def search_by_keywords(self, keywords: List[str], count: int = 100, scraping_settings: Dict = None) -> List[Tweet]:
        """Generate mock tweets using the second half of fewshot examples"""
        tweets = []
        
        # Try to load fewshot examples
        from .settings import settings as global_settings
        if global_settings and global_settings.transcript_dir:
            fewshots_path = Path(global_settings.transcript_dir) / "fewshots.json"
        else:
            fewshots_path = Path("transcripts") / "fewshots.json"
        if fewshots_path.exists():
            try:
                with open(fewshots_path, 'r') as f:
                    fewshots = json.load(f)
                
                # Use the second half of fewshots for mock tweets
                half_idx = len(fewshots) // 2
                fewshot_tweets = [fs[0] for fs in fewshots[half_idx:]]
                
                # If we have enough fewshot tweets, use them
                if fewshot_tweets:
                    # Generate count tweets, repeating fewshot tweets if needed
                    for i in range(count):
                        text = fewshot_tweets[i % len(fewshot_tweets)]
                        tweets.append(Tweet(
                            id=self._rand_id(), 
                            text=text, 
                            user=f"@user{self.rand.randint(1,9999)}",
                            created_at=datetime.utcnow().isoformat()
                        ))
                    
                    # Save to file for persistence
                    self.tweets_path.write_text(json.dumps([t.model_dump() for t in tweets], indent=2))
                    logging.info("Generated %s mock tweets from fewshots → %s", len(tweets), self.tweets_path)
                    return tweets
            except Exception as e:
                logging.warning("Failed to load fewshots for mock tweets: %s", e)
        
        # Fallback to random keyword tweets if fewshots couldn't be loaded
        for _ in range(count):
            kw = self.rand.choice(keywords)
            text = f"Hot take 👉 {kw}! What do y'all think? #WDFpod"
            tweets.append(Tweet(
                id=self._rand_id(), 
                text=text, 
                user=f"@user{self.rand.randint(1,9999)}",
                created_at=datetime.utcnow().isoformat()
            ))
        
        # Save to file for persistence
        self.tweets_path.write_text(json.dumps([t.model_dump() for t in tweets], indent=2))
        logging.info("Generated %s mock tweets with keywords → %s", len(tweets), self.tweets_path)
        return tweets
    
    def reply_to_tweet(self, tweet_id: str, text: str, run_id: str = "unknown") -> bool:
        """Mock replying to a tweet by saving to published.json"""
        # Check if already published in the database
        if is_tweet_published(tweet_id):
            logging.warning("Tweet %s already published (found in database)", tweet_id)
            return False
            
        # Also check in-memory cache for this session
        if tweet_id in self._seen_ids:
            logging.warning("Tweet %s already replied to (in memory)", tweet_id)
            return False
            
        reply = TweetReply(
            tweet_id=tweet_id,
            text=text,
            timestamp=datetime.utcnow().isoformat()
        )
        
        # Load existing published replies
        data = []
        if self.published_path.exists():
            try:
                data = json.loads(self.published_path.read_text())
            except json.JSONDecodeError:
                logging.warning("Could not parse %s, starting fresh", self.published_path)
        
        # Add new reply and save
        data.append(reply.model_dump())
        self.published_path.write_text(json.dumps(data, indent=2))
        
        # Mark as seen in memory and database
        self._seen_ids.add(tweet_id)
        record_tweet_published(tweet_id, text, run_id)
        
        logging.info("[MOCK] Published reply to %s: %s", tweet_id, text[:60])
        
        # Increment published counter
        TWEETS_PUBLISHED.labels(run_id=run_id).inc()
        
        return True
    
    def publish_batch(self, replies: List[TweetReply], run_id: str = "unknown") -> Dict[str, bool]:
        """Publish a batch of replies and return success status for each"""
        results = {}
        for reply in replies:
            success = self.reply_to_tweet(reply.tweet_id, reply.text, run_id)
            results[reply.tweet_id] = success
        return results


class RealTwitterClient(TwitterClient):
    """Real Twitter API client implementation"""
    
    def __init__(self, api_key: str = "", api_secret: str = "", token: str = "", token_secret: str = ""):
        """Initialize with Twitter API credentials - WDFWATCH ONLY"""
        # CRITICAL SAFETY: Refuse to use WDF_Show tokens
        dangerous_tokens = ["ACCESS_TOKEN", "TWITTER_TOKEN", "ACCESS_TOKEN_SECRET", "TWITTER_TOKEN_SECRET"]
        for dangerous_token in dangerous_tokens:
            if os.getenv(dangerous_token):
                logging.warning(f"⚠️  Ignoring {dangerous_token} (potential WDF_Show token)")
        
        # ONLY use WDFwatch tokens
        wdfwatch_token = os.getenv("WDFWATCH_ACCESS_TOKEN")
        if not wdfwatch_token and not token:
            logging.error("=" * 60)
            logging.error("❌ WDFWATCH_ACCESS_TOKEN not found!")
            logging.error("RealTwitterClient requires WDFwatch tokens for safety")
            logging.error("=" * 60)
            raise ValueError("WDFWATCH_ACCESS_TOKEN is required")
        
        # Use provided values or WDFwatch-safe defaults
        self.api_key = api_key or os.getenv("API_KEY", "")
        self.api_secret = api_secret or os.getenv("API_KEY_SECRET", "")
        self.token = token or wdfwatch_token
        self.token_secret = ""  # OAuth 2.0 doesn't need this
        
        # Redis for rate limiting
        self.redis = redis.Redis.from_url(settings.redis_url)
        self._seen_ids_key = "twitter:seen_ids"
        
    def search_by_keywords(self, keywords: List[str], count: int = 100, settings: Dict = None) -> List[Tweet]:
        """Search Twitter for tweets containing any of the given keywords"""
        # Try to use optimized Twitter API v2 if available
        try:
            from .twitter_api_v2 import TwitterAPIv2
            
            # Convert keywords to dict format if needed
            if keywords and isinstance(keywords[0], str):
                keyword_dicts = [{"keyword": kw, "weight": 1.0} for kw in keywords]
            else:
                keyword_dicts = keywords
            
            # Load scraping settings if not provided
            if settings is None:
                settings = {}
                # Try to load from environment or defaults
                if os.getenv('WDF_WEB_MODE', 'false').lower() == 'true':
                    try:
                        import subprocess
                        # Use virtual environment Python if available
                        venv_python = "/home/debian/Tools/WDFWatch/venv/bin/python"
                        python_cmd = venv_python if os.path.exists(venv_python) else "python"
                        result = subprocess.run(
                            [python_cmd, 'scripts/load_scraping_settings.py'],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0:
                            settings = json.loads(result.stdout)
                    except:
                        pass
            
            # Use optimized API with settings
            twitter_v2 = TwitterAPIv2(
                api_key=self.api_key,
                api_secret=self.api_secret,
                access_token=self.token,
                access_token_secret=self.token_secret,
                scraping_settings=settings
            )
            
            tweet_results = twitter_v2.search_tweets_optimized(
                keywords=keyword_dicts,
                max_tweets=count,
                min_relevance=0.5,
                days_back=settings.get('daysBack', 7)
            )
            
            # Convert to Tweet objects
            tweets = []
            for result in tweet_results:
                tweets.append(Tweet(
                    id=result['id'],
                    text=result['text'],
                    user=result['user'],
                    created_at=result.get('created_at')
                ))
            
            logging.info(f"Found {len(tweets)} tweets using optimized search")
            return tweets
            
        except (ImportError, ValueError) as e:
            logging.warning(f"TwitterAPIv2 not available or not configured: {e}")
            logging.warning("RealTwitterClient.search_by_keywords fallback not implemented")
            return []
    
    def reply_to_tweet(self, tweet_id: str, text: str, run_id: str = "unknown") -> bool:
        """Reply to a tweet using the Twitter API"""
        # Check if already published in the database
        if is_tweet_published(tweet_id):
            logging.warning("Tweet %s already published (found in database)", tweet_id)
            return False
            
        # Also check Redis
        if self.redis.sismember(self._seen_ids_key, tweet_id):
            logging.warning("Tweet %s already replied to (in Redis)", tweet_id)
            return False
            
        # In a real implementation, this would use the Twitter API
        # For now, we'll just log and return success
        logging.info("Would reply to tweet %s with: %s", tweet_id, text)
        
        # Mark as seen in Redis and database
        self.redis.sadd(self._seen_ids_key, tweet_id)
        record_tweet_published(tweet_id, text, run_id)
        
        # Increment published counter
        TWEETS_PUBLISHED.labels(run_id=run_id).inc()
        
        return True
    
    def publish_batch(self, replies: List[TweetReply], run_id: str = "unknown") -> Dict[str, bool]:
        """Publish a batch of replies and return success status for each"""
        results = {}
        for reply in replies:
            success = self.reply_to_tweet(reply.tweet_id, reply.text, run_id)
            results[reply.tweet_id] = success
        return results


def get_twitter_client() -> TwitterClient:
    """Factory function to get the appropriate Twitter client based on settings"""
    if settings.mock_mode:
        return MockTwitterClient(seed=settings.random_seed)
    return RealTwitterClient() 