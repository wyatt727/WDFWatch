#!/usr/bin/env python3
"""
Tweet Deduplication Service
Checks which tweets have already been replied to and filters them out
Ensures we fetch enough FRESH tweets to meet the target count
"""

import os
import logging
import psycopg2
from typing import List, Dict, Set, Tuple
from pathlib import Path

# Set up logging
logger = logging.getLogger(__name__)

class TweetDeduplicationService:
    """Service to check for and filter out already-replied tweets"""

    def __init__(self):
        """Initialize with database connection if in web mode"""
        self.web_mode = os.getenv("WDF_WEB_MODE", "false").lower() == "true"
        self.connection = None

        if self.web_mode:
            try:
                # Get database connection details
                db_url = os.getenv("DATABASE_URL", "postgresql://wdfwatch:wdfwatch@localhost:5432/wdfwatch")
                self.connection = psycopg2.connect(db_url)
                logger.info("Connected to database for deduplication checks")
            except Exception as e:
                logger.warning(f"Failed to connect to database: {e}")
                self.web_mode = False

    def get_already_replied_tweet_ids(self, episode_id: str = None) -> Set[str]:
        """
        Get set of tweet IDs that have already been replied to

        Returns:
            Set of twitter_id strings for tweets we've already responded to
        """
        replied_ids = set()

        if not self.web_mode or not self.connection:
            return replied_ids

        try:
            with self.connection.cursor() as cursor:
                # Get tweets with posted drafts or in tweet queue
                query = """
                    SELECT DISTINCT t.twitter_id
                    FROM tweets t
                    WHERE EXISTS (
                        -- Has an approved, posted, or scheduled draft
                        SELECT 1 FROM draft_replies dr
                        WHERE dr.tweet_id = t.id
                        AND dr.status IN ('approved', 'posted', 'scheduled')
                    )
                    OR EXISTS (
                        -- Is in tweet queue and completed
                        SELECT 1 FROM tweet_queue tq
                        WHERE tq.twitter_id = t.twitter_id
                        AND tq.status = 'completed'
                    )
                    OR t.status = 'posted'
                """

                # Add episode filter if provided
                params = []
                if episode_id:
                    query += " AND t.episode_id = %s"
                    params.append(episode_id)

                cursor.execute(query, params)
                replied_ids = {row[0] for row in cursor.fetchall()}

                logger.info(f"Found {len(replied_ids)} tweets already replied to")

        except Exception as e:
            logger.error(f"Failed to check replied tweets: {e}")

        return replied_ids

    def filter_fresh_tweets(self, tweets: List[Dict], episode_id: str = None) -> Tuple[List[Dict], List[Dict]]:
        """
        Filter tweets to separate fresh ones from already-replied

        Args:
            tweets: List of tweet dictionaries
            episode_id: Optional episode ID for context

        Returns:
            Tuple of (fresh_tweets, duplicate_tweets)
        """
        if not tweets:
            return [], []

        # Get already replied tweet IDs
        replied_ids = self.get_already_replied_tweet_ids(episode_id)

        if not replied_ids:
            # No duplicates found, all tweets are fresh
            return tweets, []

        fresh_tweets = []
        duplicate_tweets = []

        for tweet in tweets:
            tweet_id = tweet.get('id', tweet.get('twitter_id'))
            if tweet_id in replied_ids:
                duplicate_tweets.append(tweet)
            else:
                fresh_tweets.append(tweet)

        logger.info(
            f"Filtered tweets: {len(fresh_tweets)} fresh, "
            f"{len(duplicate_tweets)} already replied"
        )

        return fresh_tweets, duplicate_tweets

    def close(self):
        """Close database connection"""
        if self.connection and not self.connection.closed:
            self.connection.close()


def check_and_filter_tweets(tweets: List[Dict], episode_id: str = None) -> Tuple[List[Dict], int]:
    """
    Convenience function to filter tweets and return fresh ones

    Args:
        tweets: List of tweet dictionaries to check
        episode_id: Optional episode ID for context

    Returns:
        Tuple of (fresh_tweets, duplicate_count)
    """
    service = TweetDeduplicationService()
    try:
        fresh, duplicates = service.filter_fresh_tweets(tweets, episode_id)
        return fresh, len(duplicates)
    finally:
        service.close()


def get_fresh_tweet_count_needed(target_count: int, current_fresh: int) -> int:
    """
    Calculate how many more tweets we need to fetch

    Args:
        target_count: Target number of fresh tweets
        current_fresh: Current number of fresh tweets we have

    Returns:
        Number of additional tweets to fetch (with buffer for duplicates)
    """
    needed = target_count - current_fresh
    if needed <= 0:
        return 0

    # Add 50% buffer to account for potential duplicates in next batch
    # This helps avoid too many API calls
    return int(needed * 1.5)


if __name__ == "__main__":
    # Test the deduplication service
    service = TweetDeduplicationService()
    replied_ids = service.get_already_replied_tweet_ids()
    print(f"Found {len(replied_ids)} already-replied tweets")
    if replied_ids:
        print(f"Sample IDs: {list(replied_ids)[:5]}")
    service.close()