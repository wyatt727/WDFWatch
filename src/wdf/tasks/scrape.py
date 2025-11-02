"""
Twitter scraping task

This module handles scraping tweets based on keywords extracted from the podcast summary.
Integrates with: web_bridge.py (when WDF_WEB_MODE=true)
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List
from dotenv import load_dotenv

import structlog
from prometheus_client import Counter, Histogram

# CRITICAL: Load WDFwatch tokens first (not account manager keys!)
wdfwatch_env_path = Path(__file__).parent.parent.parent.parent / ".env.wdfwatch"
if wdfwatch_env_path.exists():
    load_dotenv(wdfwatch_env_path, override=True)
    logging.info(f"✅ Loaded WDFwatch tokens from {wdfwatch_env_path}")
else:
    logging.warning(f"⚠️  .env.wdfwatch not found at {wdfwatch_env_path}")

# Now load main .env (but WDFwatch tokens take precedence due to override=True above)
main_env_path = Path(__file__).parent.parent.parent.parent / ".env"
if main_env_path.exists():
    load_dotenv(main_env_path, override=False)  # Don't override WDFwatch tokens

from ..settings import settings
from ..twitter_client import Tweet, get_twitter_client
from ..tweet_cache import get_tweet_cache
from backend.api.app.services.episodes_repo import get_episode_file_manager

# Import web bridge for database sync
try:
    web_scripts_path = Path(__file__).parent.parent.parent.parent / "web" / "scripts"
    sys.path.insert(0, str(web_scripts_path))
    from web_bridge import sync_if_web_mode, get_keywords_if_web_mode
    logger_import = structlog.get_logger()
    logger_import.debug("Web bridge imported successfully")
except ImportError:
    # Web bridge not available, continue without it
    def sync_if_web_mode(tweets):
        pass
    def get_keywords_if_web_mode(episode_id=None):
        return None
    logger_import = structlog.get_logger()
    logger_import.debug("Web bridge not available, continuing without database sync")

# Set up structured logging
logger = structlog.get_logger()

# Prometheus metrics - handle duplicate registration gracefully
try:
    SCRAPE_LATENCY = Histogram(
        "scrape_latency_seconds", 
        "Time taken to scrape tweets",
        buckets=[1, 5, 10, 30, 60, 120, 300]
    )
    TWEETS_SCRAPED = Counter(
        "tweets_scraped_total",
        "Number of tweets scraped"
    )
    SCRAPE_ERRORS = Counter(
        "scrape_errors_total",
        "Number of tweet scraping errors"
    )
except ValueError as e:
    # Metrics already registered, get them from the registry
    logger.info("Prometheus metrics already registered, retrieving existing collectors")
    from prometheus_client import REGISTRY, Histogram, Counter
    
    # Initialize with dummy values first
    SCRAPE_LATENCY = None
    TWEETS_SCRAPED = None
    SCRAPE_ERRORS = None
    
    # Try to find existing collectors
    for collector in REGISTRY._collector_to_names:
        if hasattr(collector, '_name'):
            if collector._name == "scrape_latency_seconds":
                SCRAPE_LATENCY = collector
            elif collector._name == "tweets_scraped_total":
                TWEETS_SCRAPED = collector
            elif collector._name == "scrape_errors_total":
                SCRAPE_ERRORS = collector
    
    # If we couldn't find them, create no-op versions
    if SCRAPE_LATENCY is None:
        class NoOpHistogram:
            def observe(self, *args, **kwargs): pass
        SCRAPE_LATENCY = NoOpHistogram()
    
    if TWEETS_SCRAPED is None:
        class NoOpCounter:
            def inc(self, *args, **kwargs): pass
        TWEETS_SCRAPED = NoOpCounter()
    
    if SCRAPE_ERRORS is None:
        class NoOpCounter:
            def inc(self, *args, **kwargs): pass
        SCRAPE_ERRORS = NoOpCounter()

# File paths
KEYWORDS_PATH = Path(settings.transcript_dir) / "keywords.json"
TWEETS_PATH = Path(settings.transcript_dir) / "tweets.json"


def load_keywords(episode_id: str = None, file_manager=None, apply_learning: bool = True) -> List[dict]:
    """
    Load keywords with weights from database (if web mode) or keywords.json file
    
    Args:
        episode_id: Optional episode ID for episode-specific keywords
        file_manager: Optional episode file manager
        apply_learning: Whether to apply learned weights from historical performance
        
    Returns:
        List[dict]: List of keyword dictionaries with 'keyword' and 'weight' keys
    """
    # First try to get keywords from database if in web mode
    db_keywords = get_keywords_if_web_mode(episode_id)
    if db_keywords is not None:
        # Convert to dict format with weights if needed
        if db_keywords and isinstance(db_keywords[0], str):
            # Simple list of strings - assign equal weights
            keyword_dicts = [{"keyword": kw, "weight": 1.0} for kw in db_keywords]
        else:
            # Assume already in dict format
            keyword_dicts = db_keywords
            
        logger.info(
            "Loaded keywords from database",
            count=len(keyword_dicts),
            keywords=[k["keyword"] for k in keyword_dicts[:5]],  # Log first 5 for debugging
            source="database"
        )
        
        # Apply learned weights if enabled
        if apply_learning and keyword_dicts:
            try:
                from ..keyword_learning import KeywordLearner
                learner = KeywordLearner()
                keyword_dicts = learner.apply_learned_weights(keyword_dicts, episode_context=episode_id)
                logger.info("Applied learned weights to database keywords")
            except Exception as e:
                logger.warning(f"Failed to apply learned weights: {e}")
        
        return keyword_dicts
    
    # Try episode file manager if provided
    if file_manager:
        try:
            keywords_text = file_manager.read_input('keywords')
            keywords = json.loads(keywords_text)
            
            # Handle both formats: list of strings or list of dicts
            if isinstance(keywords, list):
                if keywords and isinstance(keywords[0], str):
                    # List of strings - assign equal weights
                    keyword_dicts = [{"keyword": kw, "weight": 1.0} for kw in keywords]
                elif keywords and isinstance(keywords[0], dict):
                    # Already in dict format
                    keyword_dicts = keywords
                else:
                    logger.error(
                        "Keywords file has invalid format",
                        expected="list of strings or dicts",
                        path=str(file_manager.get_output_path('keywords'))
                    )
                    return []
            else:
                logger.error(
                    "Keywords file has invalid format",
                    expected="list",
                    path=str(file_manager.get_output_path('keywords'))
                )
                return []
                
            logger.info(
                "Loaded keywords from episode file",
                count=len(keyword_dicts),
                keywords=[k["keyword"] for k in keyword_dicts[:5]],  # Log first 5 for debugging
                source="episode_file",
                episode_dir=file_manager.episode_dir
            )
            
            # Apply learned weights if enabled
            if apply_learning and keyword_dicts:
                try:
                    from ..keyword_learning import KeywordLearner
                    learner = KeywordLearner()
                    keyword_dicts = learner.apply_learned_weights(keyword_dicts, episode_context=episode_id)
                    logger.info("Applied learned weights to episode keywords")
                except Exception as e:
                    logger.warning(f"Failed to apply learned weights: {e}")
            
            return keyword_dicts
            
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.warning(
                "Failed to load keywords from episode file",
                error=str(e),
                episode_dir=file_manager.episode_dir
            )
    
    # Fall back to JSON file
    try:
        with open(KEYWORDS_PATH, "r") as f:
            keywords = json.load(f)
            
        # Handle both formats
        if isinstance(keywords, list):
            if keywords and isinstance(keywords[0], str):
                # List of strings - assign equal weights
                keyword_dicts = [{"keyword": kw, "weight": 1.0} for kw in keywords]
            elif keywords and isinstance(keywords[0], dict):
                # Already in dict format
                keyword_dicts = keywords
            else:
                logger.error(
                    "Keywords file has invalid format",
                    expected="list of strings or dicts",
                    path=str(KEYWORDS_PATH)
                )
                return []
        else:
            logger.error(
                "Keywords file has invalid format",
                expected="list",
                path=str(KEYWORDS_PATH)
            )
            return []
            
        logger.info(
            "Loaded keywords from legacy file",
            count=len(keyword_dicts),
            keywords=[k["keyword"] for k in keyword_dicts[:5]],  # Log first 5 for debugging
            source="legacy_file"
        )
        
        # Apply learned weights if enabled
        if apply_learning and keyword_dicts:
            try:
                from ..keyword_learning import KeywordLearner
                learner = KeywordLearner()
                
                original_weights = {k['keyword']: k.get('weight', 1.0) for k in keyword_dicts}
                keyword_dicts = learner.apply_learned_weights(keyword_dicts, episode_context=episode_id)
                
                # Log weight adjustments
                adjustments = []
                for kw in keyword_dicts[:5]:  # Log first 5
                    if kw['keyword'] in original_weights:
                        orig = original_weights[kw['keyword']]
                        new = kw['weight']
                        if abs(orig - new) > 0.1:
                            adjustments.append(f"{kw['keyword']}: {orig:.2f}→{new:.2f}")
                
                if adjustments:
                    logger.info(
                        "Applied learned keyword weights",
                        adjustments=adjustments,
                        total_adjusted=sum(1 for kw in keyword_dicts if kw.get('adjustment_type') == 'learned')
                    )
            except Exception as e:
                logger.warning(f"Failed to apply learned weights: {e}")
        
        return keyword_dicts
        
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(
            "Failed to load keywords",
            error=str(e),
            path=str(KEYWORDS_PATH)
        )
        return []


def run(run_id: str = None, count: int = None, episode_id: str = None, manual_trigger: bool = False, days_back: int = None, force_refresh: bool = False) -> Path:
    """
    Run the tweet scraping task
    
    Args:
        run_id: Optional run ID for artefact storage
        count: Number of tweets to scrape
        episode_id: Optional episode ID for episode-specific keywords
        manual_trigger: If True, actually call Twitter API. If False, skip API calls.
        days_back: Number of days to search back (for volume calculations)
        
    Returns:
        Path: Path to the tweets file
    """
    # Load scraping settings from database if in web mode
    scraping_settings = {}
    if os.getenv('WDF_WEB_MODE', 'false').lower() == 'true':
        try:
            import subprocess
            result = subprocess.run(
                ['python', 'scripts/load_scraping_settings.py'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                scraping_settings = json.loads(result.stdout)
                # Use settings from database
                if count is None:
                    count = scraping_settings.get('maxTweets', 100)
                if days_back is None:
                    days_back = scraping_settings.get('daysBack', 7)
                logger.info(
                    "Loaded scraping settings from database",
                    settings=scraping_settings,
                    max_tweets=count,
                    days_back=days_back
                )
        except Exception as e:
            logger.warning(f"Failed to load scraping settings: {e}")
            scraping_settings = {}
    
    # Use defaults if not set
    if count is None:
        count = 100
    if days_back is None:
        days_back = 7
    
    # Ensure settings has all values
    scraping_settings['maxTweets'] = count
    scraping_settings['daysBack'] = days_back
    
    # Run pre-flight checks if manual trigger
    if manual_trigger and not settings.mock_mode:
        try:
            from ..preflight_check import PreflightChecker
            from ..api_monitor import get_api_monitor
            
            # Initialize monitors
            checker = PreflightChecker(scraping_settings)
            monitor = get_api_monitor()
            
            # Load keywords for estimation
            test_keywords = load_keywords(episode_id)[:50]  # Check with first 50 keywords
            
            # Run pre-flight checks
            safe_to_proceed, check_results = checker.run_all_checks(
                keywords=[k['keyword'] if isinstance(k, dict) else k for k in test_keywords],
                settings=scraping_settings
            )
            
            if not safe_to_proceed:
                logger.error(
                    "Pre-flight checks failed - aborting to protect API quota",
                    errors=check_results.get('errors', []),
                    warnings=check_results.get('warnings', [])
                )
                # Return empty results instead of making unsafe API calls
                empty_tweets = []
                if use_episode_files:
                    file_manager = get_episode_file_manager(episode_id)
                    file_manager.write_output('tweets', empty_tweets)
                    return file_manager.get_output_path('tweets')
                else:
                    with open(TWEETS_PATH, 'w') as f:
                        json.dump(empty_tweets, f)
                    return TWEETS_PATH
            
            logger.info(
                "Pre-flight checks passed",
                recommendations=check_results.get('recommendations', [])
            )
            
            # Set safety limits on monitor
            monitor.set_safety_limits(
                max_credits=scraping_settings.get('maxApiCallsPerSession', 100),
                max_rate=10  # 10 calls per minute
            )
            
        except ImportError:
            logger.warning("Pre-flight check module not available, proceeding without checks")
        except Exception as e:
            logger.warning(f"Pre-flight checks failed: {e}, proceeding with caution")
    
    logger.info(
        "Starting tweet scraping task",
        run_id=run_id,
        count=count,
        episode_id=episode_id,
        manual_trigger=manual_trigger,
        days_back=days_back,
        with_safety_checks=manual_trigger and not settings.mock_mode
    )
    
    # Use episode file manager if episode_id provided
    use_episode_files = episode_id or os.environ.get('WDF_EPISODE_ID')
    if use_episode_files:
        file_manager = get_episode_file_manager(episode_id)
        logger.info(
            "Using episode file manager",
            episode_dir=file_manager.episode_dir
        )
    
    # Create artefacts directory if run_id is provided
    if run_id:
        artefact_dir = settings.get_run_dir(run_id)
        artefact_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if automatic scraping is disabled
    if not manual_trigger:
        # Check environment variable to enforce no-auto-scraping
        if os.getenv("WDF_NO_AUTO_SCRAPE", "false").lower() == "true":
            logger.warning(
                "Automatic Twitter scraping is disabled",
                reason="WDF_NO_AUTO_SCRAPE is set to true",
                action="Checking for previously scraped tweets"
            )
            
            # Try to use cached tweets
            tweet_cache = get_tweet_cache()
            
            # Load keywords first to filter cached tweets
            keywords = load_keywords(episode_id, file_manager if use_episode_files else None)
            
            # First check the tweet cache (extract just keyword strings for cache)
            keyword_strings = [k["keyword"] for k in keywords] if keywords and isinstance(keywords[0], dict) else keywords
            tweet_dicts = tweet_cache.get_tweets(count=count, keywords=keyword_strings)
            
            if tweet_dicts:
                logger.info(
                    "Using cached tweets for testing",
                    count=len(tweet_dicts),
                    cache_stats=tweet_cache.get_stats()
                )
            else:
                # No cached tweets, check if we can generate samples
                if os.getenv("WDF_GENERATE_SAMPLES", "true").lower() == "true":
                    try:
                        from scripts.generate_sample_tweets import generate_sample_tweets
                        tweet_dicts = generate_sample_tweets(count=count, relevant_ratio=0.25)
                        logger.info("Generated sample tweets as fallback", count=len(tweet_dicts))
                    except ImportError:
                        logger.warning("No cached tweets available and sample generator unavailable")
                        tweet_dicts = []
                else:
                    logger.warning("No cached tweets available and sample generation disabled")
                    tweet_dicts = []
            
            # Write tweets file
            if use_episode_files:
                file_manager.write_output('tweets', tweet_dicts)
                tweets_path = file_manager.get_output_path('tweets')
            else:
                with open(TWEETS_PATH, "w") as f:
                    json.dump(tweet_dicts, f, indent=2)
                tweets_path = TWEETS_PATH
            
            logger.info(
                "Created tweets file (no API calls made)",
                path=str(tweets_path),
                tweet_count=len(tweet_dicts),
                source="historical" if tweet_dicts else "empty",
                using_episode_files=use_episode_files
            )
            
            # Copy to artefacts directory if run_id is provided
            if run_id:
                artefact_tweets = artefact_dir / "tweets.json"
                if use_episode_files:
                    artefact_tweets.write_text(json.dumps(tweet_dicts, indent=2))
                else:
                    artefact_tweets.write_text(TWEETS_PATH.read_text())
            
            return tweets_path
    
    # Load keywords
    keywords = load_keywords(episode_id, file_manager if use_episode_files else None)
    if not keywords:
        raise RuntimeError("No keywords found for scraping tweets")
    
    # For manual trigger, temporarily override mock mode to get real client
    original_mock_mode = settings.mock_mode
    if manual_trigger:
        logger.info("Manual trigger detected - forcing real Twitter API client")
        settings.mock_mode = False
    
    # Get Twitter client (will be real if manual_trigger is True)
    client = get_twitter_client()
    
    # For manual trigger, use optimized API search
    if manual_trigger:
        # Import optimization modules
        try:
            from ..twitter_api_v2 import TwitterAPIv2
            from ..quota_manager import QuotaManager
            
            # Check search cache BEFORE making API calls (4-day cache)
            cached_tweets = []
            keywords_to_search = keywords.copy()
            
            if os.getenv("WDF_WEB_MODE", "false").lower() == "true":
                try:
                    # Import search cache service
                    cache_script = Path(__file__).parent.parent.parent.parent / "web" / "scripts" / "search_cache_service.py"
                    if cache_script.exists():
                        import importlib.util
                        spec = importlib.util.spec_from_file_location("search_cache_service", cache_script)
                        cache_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(cache_module)
                        
                        # Check cache for all keywords
                        keyword_strings = [k["keyword"] if isinstance(k, dict) else k for k in keywords]
                        cache_results = cache_module.optimize_keyword_search(
                            keywords=keyword_strings,
                            max_tweets=count,
                            episode_id=episode_id,
                            force_refresh=force_refresh  # Pass force_refresh flag from UI
                        )
                        
                        logger.info(
                            "Search cache check complete",
                            force_refresh=force_refresh,
                            cached_tweets=len(cache_results['cached_tweets']),
                            cached_keywords=len(cache_results['cached_keywords']),
                            keywords_to_search=len(cache_results['keywords_to_search']),
                            api_calls_saved=cache_results['estimated_api_calls_saved']
                        )
                        
                        # Log recommendations
                        for rec in cache_results['recommendations']:
                            logger.info(f"Cache: {rec}")
                        
                        # If we have enough cached tweets, skip API entirely
                        if cache_results['skip_all_api_calls']:
                            logger.info(
                                "Using cached search results, skipping ALL Twitter API calls",
                                cached_tweet_count=len(cache_results['cached_tweets']),
                                api_calls_saved=cache_results['estimated_api_calls_saved']
                            )
                            
                            # Use cached tweets
                            tweet_dicts = cache_results['cached_tweets'][:count]  # Limit to requested count
                            
                            # Sync to web (will update any metadata)
                            sync_if_web_mode(tweet_dicts)
                            
                            # Write tweets file and return
                            if use_episode_files:
                                file_manager.write_output('tweets', tweet_dicts)
                                tweets_path = file_manager.get_output_path('tweets')
                            else:
                                with open(TWEETS_PATH, "w") as f:
                                    json.dump(tweet_dicts, f, indent=2)
                                tweets_path = TWEETS_PATH
                            
                            # Copy to artefacts if needed
                            if run_id:
                                artefact_tweets = artefact_dir / "tweets.json"
                                artefact_tweets.write_text(json.dumps(tweet_dicts, indent=2))
                            
                            # Restore original mock mode
                            settings.mock_mode = original_mock_mode
                            
                            return tweets_path
                        
                        # Otherwise, store cached tweets and only search uncached keywords
                        else:
                            cached_tweets = cache_results['cached_tweets']
                            
                            # Update keywords to only search uncached ones
                            if cache_results['keywords_to_search']:
                                # Filter keywords list to only include uncached ones
                                keywords_to_search = []
                                for kw in keywords:
                                    kw_str = kw["keyword"] if isinstance(kw, dict) else kw
                                    if kw_str in cache_results['keywords_to_search']:
                                        keywords_to_search.append(kw)
                                
                                logger.info(
                                    f"Searching only {len(keywords_to_search)} uncached keywords "
                                    f"(skipping {len(cache_results['cached_keywords'])} cached)"
                                )
                                
                                # Adjust count based on cached tweets
                                if cached_tweets:
                                    original_count = count
                                    count = max(10, count - len(cached_tweets))  # Fetch at least 10 new
                                    logger.info(
                                        f"Adjusting fetch count from {original_count} to {count} "
                                        f"(already have {len(cached_tweets)} cached tweets)"
                                    )
                            else:
                                # All keywords are cached, but we need more tweets
                                logger.info("All keywords cached but need more tweets, will fetch fresh")
                                
                except Exception as e:
                    logger.warning(f"Search cache check failed: {e}, proceeding normally")
                    cached_tweets = []
                    keywords_to_search = keywords
            
            # Check quota before proceeding
            quota_mgr = QuotaManager()
            quota_ok, reason = quota_mgr.check_quota_available(required_calls=10)
            
            if not quota_ok:
                logger.error(
                    "Cannot proceed with Twitter API scraping",
                    reason=reason,
                    quota_stats=quota_mgr.get_usage_stats()
                )
                raise RuntimeError(f"Quota check failed: {reason}")
            
            # Use optimized Twitter API v2 with settings
            twitter_v2 = TwitterAPIv2(scraping_settings=scraping_settings)
            
            logger.info(
                "Using optimized Twitter API v2 for scraping",
                keyword_count=len(keywords),
                target_tweets=count
            )
            
            with SCRAPE_LATENCY.time():
                tweet_results = twitter_v2.search_tweets_optimized(
                    keywords=keywords_to_search,  # Use filtered keywords (uncached only)
                    max_tweets=count,
                    min_relevance=0.5,
                    days_back=days_back
                )
            
            # Store enriched data directly without losing fields
            # We now have comprehensive data from "one-pass enriched fetch"
            tweet_dicts = tweet_results  # Use the enriched dictionaries directly
            
            # Save search results to cache for future use (4-day cache)
            if os.getenv("WDF_WEB_MODE", "false").lower() == "true" and tweet_dicts:
                try:
                    # Track which keywords returned which tweets
                    keyword_tweet_map = {}
                    for tweet in tweet_dicts:
                        # Get matched keywords from tweet metadata if available
                        matched_kws = tweet.get('matched_keywords', [])
                        if not matched_kws:
                            # Fallback: check which keywords appear in tweet text
                            tweet_text_lower = tweet.get('text', '').lower()
                            for kw in keywords_to_search:
                                kw_str = kw["keyword"] if isinstance(kw, dict) else kw
                                if kw_str.lower() in tweet_text_lower:
                                    matched_kws.append(kw_str)
                        
                        # Map tweets to keywords
                        for kw in matched_kws:
                            if kw not in keyword_tweet_map:
                                keyword_tweet_map[kw] = []
                            keyword_tweet_map[kw].append(tweet.get('id'))
                    
                    # Save each keyword's results to cache
                    cache_service = cache_module.SearchCacheService()
                    for kw_str, tweet_ids in keyword_tweet_map.items():
                        cache_service.save_search_results(
                            keyword=kw_str,
                            tweet_ids=tweet_ids,
                            episode_id=episode_id,
                            search_params={'days_back': days_back, 'max_results': count},
                            api_calls_used=1  # Each keyword search uses at least 1 API call
                        )
                        logger.info(f"Cached {len(tweet_ids)} tweets for keyword '{kw_str}'")
                    
                except Exception as e:
                    logger.warning(f"Failed to save search results to cache: {e}")
            
            # Combine cached tweets with new results
            if cached_tweets:
                logger.info(f"Combining {len(cached_tweets)} cached tweets with {len(tweet_dicts)} new tweets")
                tweet_dicts = cached_tweets + tweet_dicts
            
            logger.info(
                "Received enriched tweet data",
                tweet_count=len(tweet_dicts),
                sample_fields=list(tweet_dicts[0].keys()) if tweet_dicts else [],
                has_user_metrics='user_metrics' in (tweet_dicts[0] if tweet_dicts else {}),
                has_context='context_annotations' in (tweet_dicts[0] if tweet_dicts else {}),
                has_source='source' in (tweet_dicts[0] if tweet_dicts else {})
            )
            
            # Set tweets variable for legacy code path compatibility
            tweets = tweet_dicts  # Ensure downstream code works
            
            logger.info(
                "Optimized search complete",
                tweets_found=len(tweet_dicts),
                api_stats=quota_mgr.get_usage_stats()
            )
            
        except ImportError as e:
            logger.warning(
                "Optimization modules not available, falling back to standard search",
                error=str(e)
            )
            # Fall back to standard search
            with SCRAPE_LATENCY.time():
                # Convert keywords to strings for legacy client
                keyword_strings = [k["keyword"] for k in keywords] if keywords and isinstance(keywords[0], dict) else keywords
                tweets = client.search_by_keywords(keyword_strings, count=count)
    else:
        # Mock mode or non-manual trigger - use standard client
        with SCRAPE_LATENCY.time():
            # Convert keywords to strings for legacy client
            keyword_strings = [k["keyword"] for k in keywords] if keywords and isinstance(keywords[0], dict) else keywords
            tweets = client.search_by_keywords(keyword_strings, count=count)
    
    # Process all tweets regardless of path (optimized or standard)
    # Check both tweet_dicts (from optimized path) and tweets (from legacy path)
    if 'tweet_dicts' not in locals() and 'tweets' in locals() and tweets:
        # Legacy path: convert Tweet objects to dicts
        logger.info(
            "Processing tweets for storage (legacy path)",
            count=len(tweets),
            has_metadata=any(hasattr(t, 'relevance_score') for t in tweets)
        )
        TWEETS_SCRAPED.inc(len(tweets))
        
        # Convert to dict for JSON serialization
        tweet_dicts = []
        for tweet in tweets:
            tweet_dict = tweet.model_dump()
            # Preserve ALL metadata for post-processing analysis
            if hasattr(tweet, 'matched_keywords'):
                tweet_dict['matched_keywords'] = tweet.matched_keywords
            if hasattr(tweet, 'relevance_score'):
                tweet_dict['relevance_score'] = tweet.relevance_score
            if hasattr(tweet, 'pre_classification_score'):
                tweet_dict['pre_classification_score'] = tweet.pre_classification_score
            if hasattr(tweet, 'api_credits_used'):
                tweet_dict['api_credits_used'] = tweet.api_credits_used
            if hasattr(tweet, 'fetch_reason'):
                tweet_dict['fetch_reason'] = tweet.fetch_reason
            tweet_dicts.append(tweet_dict)
    
    # Now process tweet_dicts (from either path)
    if 'tweet_dicts' in locals() and tweet_dicts:
        
        # Add metadata about the search
        api_credits_total = sum(t.get('api_credits_used', 1) for t in tweet_dicts)
        tweets_metadata = {
            'tweets': tweet_dicts,
            'metadata': {
                'days_back': days_back,
                'count_requested': count,
                'count_found': len(tweet_dicts),
                'avg_pre_classification_score': sum(t.get('relevance_score', 0) for t in tweet_dicts) / len(tweet_dicts) if tweet_dicts else 0,
                'api_credits_used': api_credits_total,
                'search_timestamp': datetime.utcnow().isoformat(),
                'settings': scraping_settings  # Save all settings for analysis
            }
        }
        
        # Add ALL tweets to cache for future use (including irrelevant ones!)
        tweet_cache = get_tweet_cache()
        tweet_cache.add_tweets(tweet_dicts)
        logger.info(
            "Added ALL scraped tweets to cache",
            total_cached=len(tweet_dicts),
            has_scores=sum(1 for t in tweet_dicts if 'relevance_score' in t),
            api_credits_saved=sum(t.get('api_credits_used', 1) for t in tweet_dicts)
        )
        
        # Write to file (maintain backward compatibility)
        if use_episode_files:
            file_manager.write_output('tweets', tweet_dicts)
            # Skip metadata for now - file manager doesn't support this key yet
            # file_manager.write_output('tweets_metadata', tweets_metadata)
            tweets_path = file_manager.get_output_path('tweets')
        else:
            with open(TWEETS_PATH, "w") as f:
                json.dump(tweet_dicts, f, indent=2)
            # Also write metadata file
            metadata_path = TWEETS_PATH.parent / "tweets_metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(tweets_metadata, f, indent=2)
            tweets_path = TWEETS_PATH
            
        logger.info(
            "Wrote tweets to file",
            path=str(tweets_path),
            total_count=len(tweet_dicts),
            avg_score=sum(t.get('relevance_score', 0) for t in tweet_dicts) / len(tweet_dicts) if tweet_dicts else 0,
            api_credits_used=sum(t.get('api_credits_used', 1) for t in tweet_dicts),
            using_episode_files=use_episode_files
        )
        
        # Sync to web UI database if enabled
        try:
            sync_if_web_mode(tweet_dicts)
            logger.info("Synced tweets to web UI database")
        except Exception as e:
            logger.warning(
                "Failed to sync tweets to web UI",
                error=str(e)
            )
        
        # Copy to artefacts directory if run_id is provided
        if run_id:
            artefact_tweets = artefact_dir / "tweets.json"
            if use_episode_files:
                artefact_tweets.write_text(json.dumps(tweet_dicts, indent=2))
            else:
                artefact_tweets.write_text(tweets_path.read_text())
            
            logger.info(
                "Copied tweets to artefacts directory",
                path=str(artefact_tweets)
            )
            
            # Restore original mock mode if we changed it
            if manual_trigger:
                settings.mock_mode = original_mock_mode
            return artefact_tweets
            
        # Restore original mock mode if we changed it
        if manual_trigger:
            settings.mock_mode = original_mock_mode
        return tweets_path
    
    # If no tweets were found or processed, return empty result
    logger.warning("No tweets were scraped or processed")
    if use_episode_files:
        file_manager = get_episode_file_manager(episode_id)
        file_manager.write_output('tweets', [])
        return file_manager.get_output_path('tweets')
    else:
        with open(TWEETS_PATH, "w") as f:
            json.dump([], f)
        return TWEETS_PATH


if __name__ == "__main__":
    import argparse
    
    # Configure logging when run directly
    logging.basicConfig(level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Scrape tweets based on keywords")
    parser.add_argument("--run-id", type=str, help="Run ID for artefact storage")
    parser.add_argument("--count", type=int, default=100, help="Number of tweets to scrape")
    parser.add_argument("--episode-id", type=str, help="Episode ID for episode-specific keywords")
    parser.add_argument("--manual-trigger", action="store_true", help="Indicates manual trigger from UI")
    parser.add_argument("--force-refresh", action="store_true", help="Ignore cache and fetch fresh tweets")
    
    args = parser.parse_args()
    
    # Run the task
    run(
        run_id=args.run_id,
        count=args.count,
        episode_id=args.episode_id,
        manual_trigger=args.manual_trigger,
        force_refresh=args.force_refresh
    ) 