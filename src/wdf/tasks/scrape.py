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
from ..episode_files import get_episode_file_manager

# Import web bridge for database sync - TRY MULTIPLE PATHS
HAS_WEB_BRIDGE = False
sync_if_web_mode = None
get_keywords_if_web_mode = None

# Try different import paths for web_bridge
import_attempts = []

# Method 1: Try importing from claude-pipeline (using symlink)
try:
    claude_pipeline_path = Path(__file__).parent.parent.parent.parent / "claude-pipeline"
    if str(claude_pipeline_path) not in sys.path:
        sys.path.insert(0, str(claude_pipeline_path))
    from web_bridge import sync_if_web_mode as sync_func, get_keywords_if_web_mode as keywords_func
    sync_if_web_mode = sync_func
    get_keywords_if_web_mode = keywords_func
    HAS_WEB_BRIDGE = True
    import_attempts.append(("claude-pipeline symlink", "SUCCESS"))
except ImportError as e:
    import_attempts.append(("claude-pipeline symlink", f"FAILED: {e}"))

# Method 2: Try importing from web/scripts if first method failed
if not HAS_WEB_BRIDGE:
    try:
        web_scripts_path = Path(__file__).parent.parent.parent.parent / "web" / "scripts"
        if str(web_scripts_path) not in sys.path:
            sys.path.insert(0, str(web_scripts_path))
        from web_bridge import sync_if_web_mode as sync_func, get_keywords_if_web_mode as keywords_func
        sync_if_web_mode = sync_func
        get_keywords_if_web_mode = keywords_func
        HAS_WEB_BRIDGE = True
        import_attempts.append(("web/scripts direct", "SUCCESS"))
    except ImportError as e:
        import_attempts.append(("web/scripts direct", f"FAILED: {e}"))

# If all imports failed, create stub functions but LOG LOUDLY
if not HAS_WEB_BRIDGE:
    logger_import = structlog.get_logger()
    logger_import.error(
        "❌ WEB BRIDGE IMPORT FAILED - Database sync will NOT work!",
        import_attempts=import_attempts,
        cwd=os.getcwd(),
        sys_path=sys.path[:5],  # First 5 paths for debugging
        web_mode=os.getenv("WDF_WEB_MODE")
    )

    def sync_if_web_mode(tweets):
        """Stub function when web_bridge is not available"""
        if os.getenv("WDF_WEB_MODE", "false").lower() == "true":
            logger = structlog.get_logger()
            logger.error(
                "❌ CRITICAL: sync_if_web_mode called but web_bridge not imported! Tweets NOT synced to database!",
                tweet_count=len(tweets) if tweets else 0
            )
        pass

    def get_keywords_if_web_mode(episode_id=None):
        """Stub function when web_bridge is not available"""
        if os.getenv("WDF_WEB_MODE", "false").lower() == "true":
            logger = structlog.get_logger()
            logger.warning(
                "⚠️ get_keywords_if_web_mode called but web_bridge not imported!",
                episode_id=episode_id
            )
        return None
else:
    logger_import = structlog.get_logger()
    logger_import.info(
        "✅ Web bridge imported successfully",
        import_method=import_attempts[-1][0] if import_attempts else "unknown",
        all_attempts=import_attempts
    )

# Set up structured logging
logger = structlog.get_logger()


def get_existing_tweet_ids_from_db(episode_id: str = None) -> set:
    """
    Get Twitter IDs of tweets that already exist in the database for this episode.
    Optionally filter to only tweets that already have drafts (to avoid re-scraping processed tweets).

    Args:
        episode_id: Episode ID or directory name to check

    Returns:
        Set of Twitter IDs (strings) that already exist in database
    """
    if not HAS_WEB_BRIDGE:
        return set()

    if not os.getenv("WDF_WEB_MODE", "false").lower() == "true":
        return set()

    try:
        from pathlib import Path
        import sys
        project_root = Path(__file__).parent.parent.parent.parent
        sys.path.insert(0, str(project_root / "web" / "scripts"))

        from web_bridge import get_bridge
        bridge = get_bridge()

        # Get database episode ID from directory name
        db_episode_id = None
        if episode_id:
            with bridge.connection.cursor() as cursor:
                cursor.execute("""
                    SELECT id FROM podcast_episodes
                    WHERE claude_episode_dir = %s OR CAST(id AS TEXT) = %s
                """, (episode_id, episode_id))
                result = cursor.fetchone()
                if result:
                    db_episode_id = result[0]

        if not db_episode_id:
            logger.debug("No database episode found, will not filter existing tweets")
            return set()

        # Get ALL tweets for this episode (we'll filter them appropriately)
        with bridge.connection.cursor() as cursor:
            # Get tweets that already have ANY draft (pending, approved, posted, rejected)
            # These tweets should not be re-scraped
            cursor.execute("""
                SELECT DISTINCT t.twitter_id
                FROM tweets t
                LEFT JOIN draft_replies dr ON t.id = dr.tweet_id
                WHERE t.episode_id = %s
            """, (db_episode_id,))

            existing_ids = {row[0] for row in cursor.fetchall()}

        logger.info(
            f"Found {len(existing_ids)} tweets already in database for episode {episode_id}",
            episode_id=episode_id,
            db_episode_id=db_episode_id,
            existing_count=len(existing_ids)
        )

        return existing_ids

    except Exception as e:
        logger.warning(f"Failed to get existing tweet IDs from database: {e}")
        return set()


def get_tweets_needing_drafts(episode_id: str = None) -> int:
    """
    Count how many tweets in the database need drafts created.

    Returns number of tweets that are classified but don't have drafts yet.
    """
    if not HAS_WEB_BRIDGE:
        return 0

    if not os.getenv("WDF_WEB_MODE", "false").lower() == "true":
        return 0

    try:
        from pathlib import Path
        import sys
        project_root = Path(__file__).parent.parent.parent.parent
        sys.path.insert(0, str(project_root / "web" / "scripts"))

        from web_bridge import get_bridge
        bridge = get_bridge()

        # Get database episode ID
        db_episode_id = None
        if episode_id:
            with bridge.connection.cursor() as cursor:
                cursor.execute("""
                    SELECT id FROM podcast_episodes
                    WHERE claude_episode_dir = %s OR CAST(id AS TEXT) = %s
                """, (episode_id, episode_id))
                result = cursor.fetchone()
                if result:
                    db_episode_id = result[0]

        if not db_episode_id:
            return 0

        # Count tweets that are classified as relevant but don't have drafts
        with bridge.connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*)
                FROM tweets t
                LEFT JOIN draft_replies dr ON t.id = dr.tweet_id
                WHERE t.episode_id = %s
                  AND t.status = 'relevant'
                  AND dr.id IS NULL
            """, (db_episode_id,))

            count = cursor.fetchone()[0]

        logger.info(
            f"Found {count} tweets needing drafts for episode {episode_id}",
            episode_id=episode_id,
            db_episode_id=db_episode_id,
            needing_drafts=count
        )

        return count

    except Exception as e:
        logger.warning(f"Failed to count tweets needing drafts: {e}")
        return 0

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
    logger = structlog.get_logger()

    logger.info(
        "🔍 KEYWORD LOADING DEBUG - Starting keyword loading",
        episode_id=episode_id,
        has_file_manager=file_manager is not None,
        file_manager_path=str(file_manager.base_path) if file_manager else None,
        web_mode=os.getenv("WDF_WEB_MODE", "false"),
        has_web_bridge=get_keywords_if_web_mode is not None
    )

    # First try to get keywords from database if in web mode
    # IMPORTANT: For Claude pipeline episodes (with keyword_ prefix), skip database and use file
    is_claude_episode = episode_id and (
        episode_id.startswith('keyword_') or
        episode_id.startswith('episode_') or
        'claude-pipeline/episodes' in str(file_manager.base_path if file_manager else '')
    )

    if is_claude_episode:
        logger.info("🔍 KEYWORD LOADING DEBUG - Claude pipeline episode detected, skipping database", episode_id=episode_id)
        db_keywords = None  # Force file-based loading for Claude episodes
    else:
        logger.info("🔍 KEYWORD LOADING DEBUG - Trying database lookup", episode_id=episode_id)
        db_keywords = get_keywords_if_web_mode(episode_id)
        logger.info("🔍 KEYWORD LOADING DEBUG - Database result", db_keywords=db_keywords, result_type=type(db_keywords))

    if db_keywords is not None and db_keywords:  # Only use database keywords if not empty
        # Convert to dict format with weights if needed
        if isinstance(db_keywords[0], str):
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
    elif db_keywords is not None and not db_keywords:
        # Database returned empty list, log this and fall through to file-based loading
        logger.info(
            "Database returned empty keywords list, falling back to file-based loading",
            episode_id=episode_id
        )
    
    # Try episode file manager if provided
    logger.info("🔍 KEYWORD LOADING DEBUG - Trying episode file manager", has_file_manager=file_manager is not None)
    if file_manager:
        try:
            logger.info("🔍 KEYWORD LOADING DEBUG - File manager details",
                       base_path=str(file_manager.base_path),
                       episode_dir=file_manager.episode_dir,
                       episode_id=file_manager.episode_id)

            keywords_path = file_manager.get_input_path('keywords')
            logger.info("🔍 KEYWORD LOADING DEBUG - Keywords file path",
                       path=str(keywords_path),
                       exists=keywords_path.exists())

            keywords_text = file_manager.read_input('keywords')
            logger.info("🔍 KEYWORD LOADING DEBUG - Read keywords text",
                       length=len(keywords_text),
                       preview=keywords_text[:100])

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
    logger.info("🔍 KEYWORD LOADING DEBUG - Falling back to legacy keywords file", path=str(KEYWORDS_PATH))
    try:
        with open(KEYWORDS_PATH, "r") as f:
            keywords = json.load(f)
            logger.info("🔍 KEYWORD LOADING DEBUG - Loaded legacy keywords", count=len(keywords) if keywords else 0)
            
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
    print(f"🔍 SCRAPE DEBUG: run() found episode_id={episode_id}, manual_trigger={manual_trigger}, count={count}")
    # Load scraping settings from database if in web mode
    scraping_settings = {}
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

    # Create episode file manager early if episode_id provided (needed for keyword loading)
    file_manager = None
    use_episode_files = episode_id or os.environ.get('WDF_EPISODE_ID')
    if use_episode_files:
        print(f"🔍 SCRAPE DEBUG: found use_episode_files=True, creating file_manager for episode_id={episode_id}")
        try:
            file_manager = get_episode_file_manager(episode_id)
            print(f"🔍 SCRAPE DEBUG: found file_manager with base_path={file_manager.base_path}")
        except Exception as e:
            print(f"🔍 SCRAPE ERROR: failed to create file_manager: {e}")
            raise

    # Run pre-flight checks if manual trigger
    if manual_trigger and not settings.mock_mode:
        try:
            from ..preflight_check import PreflightChecker
            from ..api_monitor import get_api_monitor

            # Initialize monitors
            checker = PreflightChecker(scraping_settings)
            monitor = get_api_monitor()

            # Load keywords for estimation (now with file_manager if available)
            test_keywords = load_keywords(episode_id, file_manager)[:50]  # Check with first 50 keywords
            
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
        with_safety_checks=manual_trigger and not settings.mock_mode,
        has_web_bridge=HAS_WEB_BRIDGE
    )

    # Log episode file manager status (already created earlier if needed)
    if file_manager:
        logger.info(
            "Using episode file manager",
            episode_dir=file_manager.episode_dir
        )
    
    # Create artefacts directory if run_id is provided
    if run_id:
        artefact_dir = settings.get_run_dir(run_id)
        artefact_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if automatic scraping is disabled
    print(f"🔍 SCRAPE DEBUG: found manual_trigger={manual_trigger}, WDF_NO_AUTO_SCRAPE={os.getenv('WDF_NO_AUTO_SCRAPE', 'false')}")
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
            keywords = load_keywords(episode_id, file_manager)
            
            # First check the tweet cache (extract just keyword strings for cache)
            keyword_strings = [k["keyword"] for k in keywords] if keywords and isinstance(keywords[0], dict) else keywords
            print(f"🔍 SCRAPE DEBUG: found keywords={keyword_strings}, count={count}")
            tweet_dicts = tweet_cache.get_tweets(count=count, keywords=keyword_strings)
            print(f"🔍 SCRAPE DEBUG: get_tweets found {len(tweet_dicts) if tweet_dicts else 0} tweets")
            
            if tweet_dicts:
                print(f"🔍 SCRAPE DEBUG: found {len(tweet_dicts)} tweets from cache")
                logger.info(
                    "Using cached tweets for testing",
                    count=len(tweet_dicts),
                    cache_stats=tweet_cache.get_stats()
                )
            else:
                # No cached tweets, generate keyword-specific samples
                if os.getenv("WDF_GENERATE_SAMPLES", "true").lower() == "true":
                    try:
                        # Generate tweets that actually contain our keywords
                        from scripts.generate_relevant_tweets import generate_keyword_tweets
                        keyword_list = [kw['keyword'] if isinstance(kw, dict) else str(kw) for kw in keywords]
                        tweet_dicts = generate_keyword_tweets(keyword_list, count=count)
                        logger.info(
                            "Generated keyword-specific sample tweets",
                            count=len(tweet_dicts),
                            keywords=keyword_list
                        )
                        print(f"🔍 SCRAPE DEBUG: Generated {len(tweet_dicts)} tweets about: {', '.join(keyword_list)}")
                    except ImportError as e:
                        logger.warning(f"Failed to import tweet generator: {e}")
                        # Fallback to simple generation
                        keyword_list = [kw['keyword'] if isinstance(kw, dict) else str(kw) for kw in keywords]
                        tweet_dicts = []
                        for i in range(min(count, 20)):
                            keyword = keyword_list[i % len(keyword_list)]
                            tweet_dicts.append({
                                "id": f"t{i}_{datetime.now().timestamp()}",
                                "text": f"Discussion about {keyword} and federalism. States need more autonomy.",
                                "user": f"@user{i}",
                                "created_at": datetime.now().isoformat() + "Z",
                                "matched_keyword": keyword
                            })
                        logger.info(f"Generated simple fallback tweets about {keyword_list}")
                else:
                    logger.warning("No cached tweets available and sample generation disabled")
                    tweet_dicts = []

            # CRITICAL FIX: Filter out existing tweets even for cache/sample path
            if episode_id and tweet_dicts:
                existing_ids = get_existing_tweet_ids_from_db(episode_id)
                if existing_ids:
                    original_count = len(tweet_dicts)
                    tweet_dicts = [t for t in tweet_dicts if t.get('id') not in existing_ids]
                    filtered_count = original_count - len(tweet_dicts)

                    if filtered_count > 0:
                        logger.info(
                            f"🔍 Filtered {filtered_count} cached/sample tweets that already exist in database",
                            original_count=original_count,
                            new_tweets=len(tweet_dicts),
                            episode_id=episode_id
                        )

            # Write tweets file
            if use_episode_files:
                print(f"🔍 SCRAPE DEBUG: found {len(tweet_dicts)} tweets - writing via file_manager")
                file_manager.write_output('tweets', tweet_dicts)
                tweets_path = file_manager.get_output_path('tweets')
                print(f"🔍 SCRAPE DEBUG: saved tweets to {tweets_path}")
            else:
                print(f"🔍 SCRAPE DEBUG: found {len(tweet_dicts)} tweets - writing to {TWEETS_PATH}")
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
    keywords = load_keywords(episode_id, file_manager)
    if not keywords:
        raise RuntimeError("No keywords found for scraping tweets")

    keyword_strings = [k.get('keyword', k) if isinstance(k, dict) else k for k in keywords]
    logger.info(
        "Keywords loaded for scraping",
        episode_id=episode_id,
        keyword_count=len(keywords),
        keywords=keyword_strings[:10]  # Show first 10
    )
    
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

                            # CRITICAL FIX: Filter out existing tweets from cached results
                            if episode_id and tweet_dicts:
                                existing_ids = get_existing_tweet_ids_from_db(episode_id)
                                if existing_ids:
                                    original_count = len(tweet_dicts)
                                    tweet_dicts = [t for t in tweet_dicts if t.get('id') not in existing_ids]
                                    filtered_count = original_count - len(tweet_dicts)

                                    if filtered_count > 0:
                                        logger.info(
                                            f"🔍 Filtered {filtered_count} cached search results that already exist in database",
                                            original_count=original_count,
                                            new_tweets=len(tweet_dicts),
                                            episode_id=episode_id
                                        )

                                        if len(tweet_dicts) < count:
                                            logger.warning(
                                                f"⚠️  After filtering, only {len(tweet_dicts)} new tweets available from cache "
                                                f"(requested {count}). Consider force_refresh=True to get fresh tweets."
                                            )

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
            
            # Use Smart Tweet Fetcher for proper pagination and deduplication
            try:
                from ..tweet_deduplication import TweetDeduplicationService
                from ..smart_tweet_fetcher import SmartTweetFetcher

                # Initialize deduplication service
                dedup_service = TweetDeduplicationService()

                # Initialize smart fetcher with API and dedup service
                smart_fetcher = SmartTweetFetcher(twitter_v2, dedup_service)

                logger.info(
                    "Using SmartTweetFetcher with pagination and deduplication",
                    target_count=count,
                    keyword_count=len(keywords_to_search),
                    days_back=days_back
                )

                # SmartTweetFetcher uses two strategies based on keyword count:
                # 1. DEEP PAGINATION (≤2 keywords):
                #    - Fetches up to 100 tweets per keyword per API call
                #    - Uses pagination tokens to get more tweets from same keyword
                #    - Continues until target count of FRESH tweets is reached
                #    - Best for focused searches with specific keywords
                #
                # 2. SHALLOW SEARCH (>2 keywords):
                #    - Fetches smaller batches spread across many keywords
                #    - Only one pass per keyword (no deep pagination)
                #    - Stops when target is reached or all keywords searched once
                #    - Prevents excessive API calls when many keywords present
                #    - Example: 30 keywords would be capped instead of 30*100=3000 tweets

                # Fetch exactly the requested number of FRESH tweets
                with SCRAPE_LATENCY.time():
                    tweet_dicts, fetch_stats = smart_fetcher.fetch_fresh_tweets(
                        keywords=keywords_to_search,
                        target_count=count,
                        episode_id=episode_id,
                        days_back=days_back,
                        max_api_calls=10  # Safety limit
                    )

                # Log comprehensive statistics
                logger.info(
                    "🎯 Smart fetching complete",
                    extra={
                        'requested': count,
                        'delivered': len(tweet_dicts),
                        'total_fetched': fetch_stats['total_fetched'],
                        'duplicates_filtered': fetch_stats['duplicates_filtered'],
                        'fresh_tweets': fetch_stats['fresh_tweets'],
                        'api_calls': fetch_stats['api_calls'],
                        'keywords_searched': len(fetch_stats['keywords_searched']),
                        'keywords_exhausted': len(fetch_stats['keywords_exhausted']),
                        'efficiency': f"{(fetch_stats['fresh_tweets']/fetch_stats['total_fetched']*100):.1f}%" if fetch_stats['total_fetched'] > 0 else "N/A"
                    }
                )

                # Clean up
                if dedup_service:
                    dedup_service.close()

            except ImportError as e:
                logger.warning(
                    f"Smart fetching not available, falling back to standard search: {e}"
                )
                # Fall back to standard search without smart deduplication
                with SCRAPE_LATENCY.time():
                    tweet_dicts = twitter_v2.search_tweets_optimized(
                        keywords=keywords_to_search,
                        max_tweets=count,
                        min_relevance=0.5,
                        days_back=days_back,
                        force_refresh=force_refresh
                    )
                logger.info(f"Standard search returned {len(tweet_dicts)} tweets")

            except Exception as e:
                logger.error(f"Smart fetching failed: {e}")
                # Fall back to standard search
                with SCRAPE_LATENCY.time():
                    tweet_dicts = twitter_v2.search_tweets_optimized(
                        keywords=keywords_to_search,
                        max_tweets=count,
                        min_relevance=0.5,
                        days_back=days_back,
                        force_refresh=force_refresh
                    )
            
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

        # CRITICAL FIX: Filter out tweets that already exist in database
        # This prevents re-scraping the same tweets and wasting API quota
        if episode_id:
            existing_ids = get_existing_tweet_ids_from_db(episode_id)
            if existing_ids:
                original_count = len(tweet_dicts)
                tweet_dicts = [t for t in tweet_dicts if t.get('id') not in existing_ids]
                filtered_count = original_count - len(tweet_dicts)

                if filtered_count > 0:
                    logger.info(
                        f"🔍 Filtered out {filtered_count} tweets that already exist in database",
                        original_count=original_count,
                        existing_in_db=len(existing_ids),
                        new_tweets=len(tweet_dicts),
                        episode_id=episode_id
                    )

                    # If we don't have enough new tweets, log a warning
                    if len(tweet_dicts) < count:
                        shortage = count - len(tweet_dicts)
                        logger.warning(
                            f"⚠️  Only found {len(tweet_dicts)} new tweets (requested {count}, short by {shortage}). "
                            f"Filtered out {filtered_count} existing tweets. "
                            "Consider running scraping again with different keywords, longer time range, or force_refresh=True."
                        )
                else:
                    logger.info(
                        f"✅ All {original_count} scraped tweets are new (not in database)",
                        episode_id=episode_id
                    )
            else:
                logger.info(
                    f"✅ No existing tweets in database for episode {episode_id}, all scraped tweets are new",
                    tweet_count=len(tweet_dicts)
                )

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
        
        # Sync to web UI database if enabled - CRITICAL FIX
        if HAS_WEB_BRIDGE and os.getenv("WDF_WEB_MODE", "false").lower() == "true":
            try:
                logger.info(
                    "🔄 Attempting to sync tweets to database",
                    tweet_count=len(tweet_dicts),
                    episode_id=episode_id
                )
                sync_if_web_mode(tweet_dicts)
                logger.info(
                    "✅ Successfully synced tweets to web UI database",
                    tweet_count=len(tweet_dicts)
                )
            except Exception as e:
                logger.error(
                    "❌ FAILED to sync tweets to web UI database",
                    error=str(e),
                    has_web_bridge=HAS_WEB_BRIDGE,
                    web_mode=os.getenv("WDF_WEB_MODE")
                )
        elif not HAS_WEB_BRIDGE:
            logger.error(
                "❌ CRITICAL: Web bridge NOT imported, tweets NOT synced to database!",
                web_mode=os.getenv("WDF_WEB_MODE"),
                episode_id=episode_id
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
    
    # If no tweets were found or processed, check if we should preserve existing data
    logger.warning("No tweets were scraped or processed")
    if use_episode_files:
        file_manager = get_episode_file_manager(episode_id)
        tweets_path = file_manager.get_output_path('tweets')
        # Only write empty array if file doesn't exist yet
        # This prevents overwriting good data from previous successful runs
        if not tweets_path.exists():
            file_manager.write_output('tweets', [])
            logger.info("Created empty tweets file (no existing data to preserve)")
        else:
            logger.info("Preserving existing tweets file (not overwriting with empty array)")
        return tweets_path
    else:
        # Legacy path - only write empty if file doesn't exist
        if not TWEETS_PATH.exists():
            with open(TWEETS_PATH, "w") as f:
                json.dump([], f)
            logger.info("Created empty tweets file (no existing data to preserve)")
        else:
            logger.info("Preserving existing tweets file (not overwriting with empty array)")
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
    result = run(
        run_id=args.run_id,
        count=args.count,
        episode_id=args.episode_id,
        manual_trigger=args.manual_trigger,
        force_refresh=args.force_refresh
    )

    # Log completion and exit explicitly
    logger.info("Scraping task completed", result_path=str(result) if result else None)

    # Force exit to ensure process terminates
    import sys
    sys.exit(0) 