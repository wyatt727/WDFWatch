#!/usr/bin/env python3
"""
Apply keyword penalty when a draft is rejected
Called from the web API when a draft rejection occurs

Interacts with: keyword_learning.py, Redis, database
"""

import json
import logging
import sys
import os
from pathlib import Path
import argparse
from datetime import datetime

# Add parent directory to path to import wdf modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.wdf.keyword_learning import KeywordLearner
from src.wdf.settings import settings
import redis

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def apply_rejection_penalty(tweet_id: str, keywords: list = None, penalty_factor: float = 0.2):
    """
    Apply negative feedback to keywords associated with a rejected draft.
    
    Args:
        tweet_id: Twitter ID of the tweet whose draft was rejected
        keywords: Optional list of keywords to penalize (if not provided, will be extracted from DB)
        penalty_factor: How much to reduce weights (0.2 = 20% reduction)
    """
    try:
        # Initialize Redis and keyword learner
        redis_client = redis.Redis.from_url(settings.redis_url)
        learner = KeywordLearner(redis_client)
        
        # If keywords not provided, try to get from database
        if not keywords:
            try:
                # Import here to avoid circular dependency
                import subprocess
                
                # Query database for tweet keywords
                cmd = [
                    "npx", "prisma", "db", "execute",
                    "--preview-feature",
                    "--sql",
                    f"SELECT search_keywords FROM tweets WHERE twitter_id = '{tweet_id}' LIMIT 1"
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=Path(__file__).parent.parent
                )
                
                if result.returncode == 0 and result.stdout:
                    data = json.loads(result.stdout)
                    if data and len(data) > 0:
                        keywords = data[0].get('search_keywords', [])
                        logger.info(f"Found {len(keywords)} keywords for tweet {tweet_id}")
            except Exception as e:
                logger.error(f"Failed to fetch keywords from database: {e}")
        
        if not keywords:
            logger.warning(f"No keywords found for tweet {tweet_id}, cannot apply penalty")
            return False
        
        # Apply negative feedback to the keywords
        logger.info(f"Applying penalty to keywords: {keywords}")
        learner.apply_negative_feedback(keywords, penalty_factor)
        
        # Log the action to Redis for tracking
        redis_client.lpush(
            "keyword_penalties:history",
            json.dumps({
                "tweet_id": tweet_id,
                "keywords": keywords,
                "penalty_factor": penalty_factor,
                "timestamp": datetime.utcnow().isoformat()
            })
        )
        
        # Keep only last 100 penalty events
        redis_client.ltrim("keyword_penalties:history", 0, 99)
        
        logger.info(f"Successfully applied penalty to {len(keywords)} keywords for tweet {tweet_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to apply keyword penalty: {e}")
        return False


def main():
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(description="Apply keyword penalty for rejected draft")
    parser.add_argument("--tweet-id", required=True, help="Twitter ID of the rejected tweet")
    parser.add_argument("--keywords", nargs="+", help="Optional list of keywords to penalize")
    parser.add_argument("--penalty", type=float, default=0.2, help="Penalty factor (0-1)")
    
    args = parser.parse_args()
    
    success = apply_rejection_penalty(
        tweet_id=args.tweet_id,
        keywords=args.keywords,
        penalty_factor=args.penalty
    )
    
    if success:
        print(json.dumps({"success": True, "message": "Keyword penalty applied"}))
        sys.exit(0)
    else:
        print(json.dumps({"success": False, "message": "Failed to apply penalty"}))
        sys.exit(1)


if __name__ == "__main__":
    main()