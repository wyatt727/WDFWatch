#!/usr/bin/env python3
"""
Smart Tweet Fetcher with Deduplication and Pagination Support
Fetches exactly the requested number of FRESH tweets by continuing to search until target is met
"""

import os
import time
import logging
from typing import List, Dict, Set, Tuple, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SmartTweetFetcher:
    """
    Smart fetcher that uses pagination and deduplication to get exactly the
    requested number of fresh tweets (not already replied to).
    """

    def __init__(self, twitter_api, dedup_service=None):
        """
        Initialize smart fetcher with Twitter API client and optional deduplication service.

        Args:
            twitter_api: TwitterAPIv2 instance
            dedup_service: TweetDeduplicationService instance (optional)
        """
        self.api = twitter_api
        self.dedup_service = dedup_service
        self.use_dedup = dedup_service is not None and dedup_service.web_mode

        # Track pagination state per keyword
        self.pagination_state = {}  # keyword -> next_token

        # Track exhausted keywords (no more results available)
        self.exhausted_keywords = set()

        # Track search statistics
        self.stats = {
            'api_calls': 0,
            'total_fetched': 0,
            'duplicates_filtered': 0,
            'fresh_tweets': 0,
            'keywords_searched': set(),
            'keywords_exhausted': set()
        }

    def fetch_fresh_tweets(self,
                          keywords: List[Dict[str, float]],
                          target_count: int,
                          episode_id: str = None,
                          days_back: int = 7,
                          max_api_calls: int = 10) -> Tuple[List[Dict], Dict]:
        """
        Fetch exactly target_count of FRESH tweets using smart pagination and deduplication.

        Args:
            keywords: List of keyword dicts with 'keyword' and 'weight' fields
            target_count: Exact number of fresh tweets to return
            episode_id: Episode ID for context (used in deduplication)
            days_back: Number of days to search back
            max_api_calls: Maximum API calls to prevent infinite loops

        Returns:
            Tuple of (fresh_tweets, statistics)
        """
        fresh_tweets = []
        all_fetched = []

        # Sort keywords by weight (highest priority first)
        sorted_keywords = sorted(keywords, key=lambda k: k.get('weight', 0), reverse=True)

        # Determine strategy based on keyword count
        # Use deep pagination only for small keyword sets (<=2 keywords)
        # For larger sets, use shallow search across all keywords
        use_deep_pagination = len(keywords) <= 2

        if use_deep_pagination:
            logger.info(
                f"Using DEEP pagination strategy ({len(keywords)} keywords <= 2)",
                extra={'keyword_count': len(keywords)}
            )
        else:
            logger.info(
                f"Using SHALLOW search strategy ({len(keywords)} keywords > 2)",
                extra={'keyword_count': len(keywords)}
            )

        logger.info(
            f"Starting smart fetch for {target_count} fresh tweets from {len(keywords)} keywords",
            extra={
                'target_count': target_count,
                'keyword_count': len(keywords),
                'deduplication': self.use_dedup,
                'days_back': days_back
            }
        )

        # Keep fetching until we have enough fresh tweets
        while len(fresh_tweets) < target_count and self.stats['api_calls'] < max_api_calls:

            # Try each keyword in priority order
            made_progress = False

            for kw_dict in sorted_keywords:
                keyword = kw_dict['keyword']
                weight = kw_dict.get('weight', 1.0)

                # Skip exhausted keywords
                if keyword in self.exhausted_keywords:
                    continue

                # Check if we have enough tweets
                if len(fresh_tweets) >= target_count:
                    break

                # Calculate how many more tweets we need
                needed = target_count - len(fresh_tweets)

                if use_deep_pagination:
                    # Deep pagination: fetch more tweets with buffer for duplicates
                    # Add 50% buffer for potential duplicates
                    fetch_size = min(100, int(needed * 1.5))  # Cap at 100 (API limit)
                else:
                    # Shallow search: fetch fewer tweets per keyword
                    # With many keywords, we want to spread the search
                    tweets_per_keyword = max(10, int(target_count / len(keywords) * 1.2))
                    fetch_size = min(tweets_per_keyword, needed, 100)

                    # For shallow search, only do one pass per keyword
                    if keyword in self.pagination_state:
                        logger.debug(f"Skipping '{keyword}' - already searched in shallow mode")
                        continue

                logger.info(
                    f"Searching keyword '{keyword}' (weight={weight:.2f})",
                    extra={
                        'keyword': keyword,
                        'weight': weight,
                        'fetch_size': fetch_size,
                        'needed': needed,
                        'has_pagination': keyword in self.pagination_state
                    }
                )

                # Get pagination token if we have one for this keyword
                next_token = self.pagination_state.get(keyword)

                try:
                    # Use search_keyword_deep for pagination support
                    result = self.api.search_keyword_deep(
                        keyword=keyword,
                        max_results=fetch_size,
                        days_back=days_back if not next_token else None,  # Only set days_back on first search
                        next_token=next_token,
                        exclude_retweets=True,  # Exclude retweets for better quality
                        min_likes=0  # Don't filter by likes, let classification handle quality
                    )

                    self.stats['api_calls'] += 1
                    self.stats['keywords_searched'].add(keyword)

                    batch_tweets = result.get('data', [])
                    meta = result.get('meta', {})

                    if not batch_tweets:
                        # No more tweets for this keyword
                        logger.info(f"No tweets found for '{keyword}'")
                        self.exhausted_keywords.add(keyword)
                        self.stats['keywords_exhausted'].add(keyword)
                        if keyword in self.pagination_state:
                            del self.pagination_state[keyword]
                        continue

                    # Track that we found tweets
                    made_progress = True
                    all_fetched.extend(batch_tweets)
                    self.stats['total_fetched'] += len(batch_tweets)

                    # Add keyword tracking to tweets
                    for tweet in batch_tweets:
                        tweet['matched_keyword'] = keyword
                        tweet['keyword_weight'] = weight

                    # Filter for fresh tweets if deduplication is enabled
                    if self.use_dedup:
                        fresh_batch, duplicate_batch = self.dedup_service.filter_fresh_tweets(
                            batch_tweets,
                            episode_id
                        )

                        duplicates_count = len(duplicate_batch)
                        self.stats['duplicates_filtered'] += duplicates_count

                        logger.info(
                            f"Keyword '{keyword}': {len(batch_tweets)} fetched → "
                            f"{len(fresh_batch)} fresh, {duplicates_count} duplicates"
                        )

                        fresh_tweets.extend(fresh_batch)
                    else:
                        # No deduplication, all tweets are considered fresh
                        fresh_tweets.extend(batch_tweets)
                        logger.info(f"Keyword '{keyword}': {len(batch_tweets)} tweets (no dedup)")

                    self.stats['fresh_tweets'] = len(fresh_tweets)

                    # Update pagination token for this keyword (only in deep mode)
                    next_token = meta.get('next_token')
                    if use_deep_pagination:
                        # Deep pagination: save token for next iteration
                        if next_token:
                            self.pagination_state[keyword] = next_token
                            logger.debug(f"Saved pagination token for '{keyword}'")
                        else:
                            # No more results for this keyword
                            logger.info(f"No more results available for '{keyword}'")
                            self.exhausted_keywords.add(keyword)
                            self.stats['keywords_exhausted'].add(keyword)
                            if keyword in self.pagination_state:
                                del self.pagination_state[keyword]
                    else:
                        # Shallow search: mark as searched (don't paginate)
                        self.pagination_state[keyword] = 'searched'
                        if not batch_tweets:
                            self.exhausted_keywords.add(keyword)
                            self.stats['keywords_exhausted'].add(keyword)

                    # Log progress
                    logger.info(
                        f"Progress: {len(fresh_tweets)}/{target_count} fresh tweets collected",
                        extra={
                            'fresh_count': len(fresh_tweets),
                            'target': target_count,
                            'api_calls': self.stats['api_calls'],
                            'total_fetched': self.stats['total_fetched'],
                            'duplicates': self.stats['duplicates_filtered']
                        }
                    )

                except Exception as e:
                    logger.error(f"Error searching keyword '{keyword}': {e}")
                    self.exhausted_keywords.add(keyword)
                    continue

            # If we made no progress with any keyword, we're done
            if not made_progress:
                logger.warning(
                    "No more tweets available from any keyword",
                    extra={
                        'exhausted_keywords': list(self.exhausted_keywords),
                        'fresh_tweets': len(fresh_tweets),
                        'target': target_count
                    }
                )
                break

            # In shallow mode, stop after one pass through all keywords
            if not use_deep_pagination:
                # Check if we've searched all keywords at least once
                all_searched = all(
                    kw['keyword'] in self.pagination_state or
                    kw['keyword'] in self.exhausted_keywords
                    for kw in sorted_keywords
                )
                if all_searched:
                    logger.info(
                        "Shallow search complete - searched all keywords once",
                        extra={
                            'fresh_tweets': len(fresh_tweets),
                            'target': target_count
                        }
                    )
                    break

        # Trim to exact count if we got more
        if len(fresh_tweets) > target_count:
            logger.info(f"Trimming from {len(fresh_tweets)} to {target_count} tweets")
            fresh_tweets = fresh_tweets[:target_count]
            self.stats['fresh_tweets'] = target_count

        # Calculate final statistics
        efficiency = (self.stats['fresh_tweets'] / self.stats['total_fetched'] * 100) if self.stats['total_fetched'] > 0 else 0

        logger.info(
            f"Smart fetching complete ({'deep' if use_deep_pagination else 'shallow'} mode)",
            extra={
                'strategy': 'deep' if use_deep_pagination else 'shallow',
                'target': target_count,
                'achieved': len(fresh_tweets),
                'total_fetched': self.stats['total_fetched'],
                'duplicates_filtered': self.stats['duplicates_filtered'],
                'efficiency': f"{efficiency:.1f}%",
                'api_calls': self.stats['api_calls'],
                'keywords_used': len(self.stats['keywords_searched']),
                'keywords_exhausted': len(self.stats['keywords_exhausted'])
            }
        )

        return fresh_tweets, self.stats

    def reset_pagination(self):
        """Reset pagination state to start fresh searches."""
        self.pagination_state.clear()
        self.exhausted_keywords.clear()
        logger.info("Pagination state reset")

    def get_pagination_state(self) -> Dict:
        """Get current pagination state for persistence."""
        return {
            'pagination_tokens': self.pagination_state.copy(),
            'exhausted_keywords': list(self.exhausted_keywords),
            'stats': self.stats.copy()
        }

    def restore_pagination_state(self, state: Dict):
        """Restore pagination state from previous session."""
        self.pagination_state = state.get('pagination_tokens', {})
        self.exhausted_keywords = set(state.get('exhausted_keywords', []))
        self.stats = state.get('stats', self.stats)
        logger.info(
            "Pagination state restored",
            extra={
                'active_keywords': len(self.pagination_state),
                'exhausted_keywords': len(self.exhausted_keywords)
            }
        )