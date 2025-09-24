#!/usr/bin/env python3
"""
Focused Tweet Scraping Task

Handles focused scraping for specific keywords with deep search capabilities.
This script performs comprehensive scraping for a small number of keywords,
gathering many tweets per keyword rather than spreading across many keywords.

Related files:
- /web/app/api/scraping/trigger/route.ts (API trigger)
- /src/wdf/twitter_api_v2.py (Twitter API implementation)
- /src/wdf/episode_files.py (Episode file management)
"""

import json
import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

import structlog
from pydantic import BaseModel

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.wdf.settings import settings
from src.wdf.twitter_client import get_twitter_client
from src.wdf.episode_files import get_episode_file_manager

# Import web bridge for database sync
try:
    web_scripts_path = Path(__file__).parent.parent.parent.parent / "web" / "scripts"
    sys.path.insert(0, str(web_scripts_path))
    from web_bridge import sync_if_web_mode, update_claude_pipeline_status
    logger_import = structlog.get_logger()
    logger_import.debug("Web bridge imported successfully")
except ImportError:
    # Web bridge not available, continue without it
    def sync_if_web_mode(tweets):
        pass
    def update_claude_pipeline_status(episode_id, status):
        pass
    logger_import = structlog.get_logger()
    logger_import.debug("Web bridge not available, continuing without database sync")

logger = structlog.get_logger(__name__)


class FocusedScrapeParams(BaseModel):
    """Parameters for focused scraping"""
    keywords: List[str]
    target_per_keyword: int = 100  # Target tweets per keyword
    maxTweets: int = 500  # Total max tweets
    daysBack: int = 7
    minLikes: int = 0
    minRetweets: int = 0
    minReplies: int = 0
    excludeReplies: bool = False
    excludeRetweets: bool = False
    language: str = "en"
    run_id: str
    episode_id: Optional[str] = None
    episode_dir: Optional[str] = None  # Directory name for keyword-based episodes
    focused_mode: bool = True


def scrape_keyword_deep(keyword: str, target_count: int, twitter_api, settings: Dict) -> List[Dict]:
    """
    Deep scrape for a single keyword using pagination.

    Args:
        keyword: The keyword to search for
        target_count: Target number of tweets to collect
        twitter_api: Twitter API v2 instance
        settings: Scraping settings

    Returns:
        List of tweet dictionaries
    """
    logger.info(
        f"Starting deep search for keyword: '{keyword}'",
        target=target_count
    )

    tweets = []
    next_token = None
    api_calls = 0
    max_api_calls = 10  # Safety limit

    while len(tweets) < target_count and api_calls < max_api_calls:
        remaining = target_count - len(tweets)
        # Use max batch size (100) unless we need less
        batch_size = min(100, remaining)

        logger.info(
            f"Fetching batch {api_calls + 1} for '{keyword}'",
            batch_size=batch_size,
            current_total=len(tweets),
            has_next_token=bool(next_token)
        )

        try:
            # Call the new deep search method
            result = twitter_api.search_keyword_deep(
                keyword=keyword,
                max_results=batch_size,
                days_back=settings.get('daysBack', 7),
                next_token=next_token,
                exclude_replies=settings.get('excludeReplies', False),
                exclude_retweets=settings.get('excludeRetweets', False),
                min_likes=settings.get('minLikes', 0),
                min_retweets=settings.get('minRetweets', 0)
            )

            # Extract tweets and pagination token
            if 'data' in result:
                batch_tweets = result['data']
                tweets.extend(batch_tweets)
                logger.info(
                    f"Got {len(batch_tweets)} tweets in batch {api_calls + 1}",
                    total_so_far=len(tweets)
                )

            # Check for next page
            next_token = result.get('meta', {}).get('next_token')
            api_calls += 1

            # Stop if no more results
            if not next_token:
                logger.info(f"No more results available for '{keyword}'")
                break

        except Exception as e:
            logger.error(f"Error during deep search for '{keyword}': {e}")
            break

    # Ensure we don't exceed target
    tweets = tweets[:target_count]

    logger.info(
        f"Completed deep search for '{keyword}'",
        collected=len(tweets),
        target=target_count,
        api_calls=api_calls
    )

    return tweets


def run_focused_scrape(params: FocusedScrapeParams) -> bool:
    """
    Run focused scraping for specific keywords with deep search.

    Args:
        params: Focused scraping parameters

    Returns:
        bool: True if successful
    """
    logger.info(
        "Starting focused scraping",
        run_id=params.run_id,
        keywords=params.keywords,
        target_per_keyword=params.target_per_keyword,
        episode_id=params.episode_id,
        episode_dir=params.episode_dir
    )

    # Get episode file manager if episode_id or episode_dir provided
    file_manager = None
    if params.episode_dir:
        # Use the explicit directory name for keyword-based episodes
        from src.wdf.episode_files import EpisodeFileManager
        # Pass episode_id and episode_dir to EpisodeFileManager
        file_manager = EpisodeFileManager(
            episode_id=params.episode_id or "0",  # Use episode_id if available, else dummy ID
            episode_dir=params.episode_dir,
            pipeline_type='claude'
        )
        logger.info(f"Using episode file manager for directory {params.episode_dir}")
    elif params.episode_id:
        file_manager = get_episode_file_manager(params.episode_id)
        logger.info(f"Using episode file manager for episode {params.episode_id}")

    # Temporarily enable real API for focused scraping
    original_mock_mode = settings.mock_mode
    settings.mock_mode = False
    logger.info("Forcing real Twitter API for focused scraping")

    try:
        # Import and initialize Twitter API v2
        from src.wdf.twitter_api_v2 import TwitterAPIv2

        twitter_api = TwitterAPIv2(
            scraping_settings={
                'daysBack': params.daysBack,
                'minLikes': params.minLikes,
                'minRetweets': params.minRetweets,
                'excludeReplies': params.excludeReplies,
                'excludeRetweets': params.excludeRetweets,
            }
        )

        # Collect all tweets
        all_tweets = []

        # Scrape each keyword deeply
        for i, keyword in enumerate(params.keywords, 1):
            logger.info(
                f"Processing keyword {i}/{len(params.keywords)}: '{keyword}'",
                target_tweets=params.target_per_keyword
            )

            # Deep scrape for this keyword
            keyword_tweets = scrape_keyword_deep(
                keyword=keyword,
                target_count=params.target_per_keyword,
                twitter_api=twitter_api,
                settings={
                    'daysBack': params.daysBack,
                    'minLikes': params.minLikes,
                    'minRetweets': params.minRetweets,
                    'excludeReplies': params.excludeReplies,
                    'excludeRetweets': params.excludeRetweets,
                }
            )

            # Add metadata to each tweet
            for tweet in keyword_tweets:
                tweet['matched_keywords'] = [keyword]
                tweet['search_keyword'] = keyword
                tweet['focused_search'] = True

            all_tweets.extend(keyword_tweets)

            logger.info(
                f"Collected {len(keyword_tweets)} tweets for '{keyword}'",
                total_so_far=len(all_tweets)
            )

            # Check if we've hit the overall maximum
            if len(all_tweets) >= params.maxTweets:
                logger.info(
                    f"Reached overall maximum of {params.maxTweets} tweets",
                    stopping_at_keyword=i
                )
                all_tweets = all_tweets[:params.maxTweets]
                break

        # Save tweets to episode directory
        if file_manager:
            file_manager.write_output('tweets', all_tweets)
            tweets_path = file_manager.get_output_path('tweets')
            logger.info(
                f"Saved {len(all_tweets)} tweets to episode",
                path=str(tweets_path)
            )
        else:
            # Fallback to transcripts directory
            tweets_path = Path(settings.transcript_dir) / "tweets.json"
            with open(tweets_path, 'w') as f:
                json.dump(all_tweets, f, indent=2)
            logger.info(
                f"Saved {len(all_tweets)} tweets to transcripts",
                path=str(tweets_path)
            )

        # Update episode status in database if in web mode
        if os.getenv('WDF_WEB_MODE', 'false').lower() == 'true' and params.episode_id:
            try:
                # Log environment variable for debugging
                current_episode_id = os.getenv('WDF_CURRENT_EPISODE_ID')
                logger.info(f"WDF_CURRENT_EPISODE_ID: '{current_episode_id}', params.episode_id: '{params.episode_id}'")

                # Sync tweets to database
                sync_if_web_mode(all_tweets)

                # Update episode status
                update_claude_pipeline_status(
                    int(params.episode_id),
                    'ready_for_classification'
                )
                logger.info("Updated episode status in database")

            except Exception as e:
                logger.warning(f"Failed to update database: {e}")

        logger.info(
            "Focused scraping completed successfully",
            total_tweets=len(all_tweets),
            keywords_processed=min(i, len(params.keywords))
        )
        return True

    except Exception as e:
        logger.error(f"Focused scraping failed: {e}")
        return False

    finally:
        # Restore original mock mode
        settings.mock_mode = original_mock_mode


def main():
    """Main entry point for focused scraping"""
    parser = argparse.ArgumentParser(description="Focused tweet scraping")
    parser.add_argument(
        "--params",
        type=str,
        required=True,
        help="JSON string with scraping parameters",
    )
    args = parser.parse_args()

    try:
        # Parse parameters
        params_dict = json.loads(args.params)
        params = FocusedScrapeParams(**params_dict)

        # Log startup info
        logger.info("=" * 60)
        logger.info("FOCUSED SCRAPING STARTED")
        logger.info(f"Episode ID: {params.episode_id}")
        logger.info(f"Episode Directory: {params.episode_dir}")
        logger.info(f"Keywords: {params.keywords}")
        logger.info(f"Target per keyword: {params.target_per_keyword}")
        logger.info("=" * 60)

        # Check for API keys
        logger.info("Checking for API keys in environment...")
        api_key = os.getenv("API_KEY") or os.getenv("CLIENT_ID")
        api_secret = os.getenv("API_KEY_SECRET") or os.getenv("CLIENT_SECRET")
        access_token = os.getenv("WDFWATCH_ACCESS_TOKEN")
        bearer_token = os.getenv("BEARER_TOKEN")

        logger.info(f"API_KEY present: {bool(api_key)}")
        logger.info(f"API_KEY_SECRET present: {bool(api_secret)}")
        logger.info(f"WDFWATCH_ACCESS_TOKEN present: {bool(access_token)}")
        logger.info(f"BEARER_TOKEN present: {bool(bearer_token)}")

        if not api_key:
            error_msg = "ERROR: No Twitter API keys found. Please set API_KEY or CLIENT_ID"
            logger.error(error_msg)
            print(error_msg, file=sys.stderr)
            sys.exit(1)

        # Execute focused scraping
        success = run_focused_scrape(params)

        if success:
            logger.info("Successfully completed focused scraping")
            print("Successfully completed focused scraping")
            sys.exit(0)
        else:
            error_msg = "Focused scraping failed - check logs for details"
            logger.error(error_msg)
            print(error_msg, file=sys.stderr)
            sys.exit(1)

    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON parameters: {e}"
        logger.error(error_msg)
        print(error_msg, file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        error_msg = f"Scraping failed with exception: {str(e)}"
        logger.error(error_msg, exc_info=True)  # Include full traceback in logs
        print(error_msg, file=sys.stderr)
        import traceback
        traceback.print_exc()  # Print full traceback to stderr
        sys.exit(1)


if __name__ == "__main__":
    main()