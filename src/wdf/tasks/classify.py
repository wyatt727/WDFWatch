"""
Tweet classification task

This module handles scoring tweets for relevancy (0.00-1.00) using the configured model.
It wraps the existing tweet_classifier.py script with task-specific functionality.
Integrates with: web_bridge.py (when WDF_WEB_MODE=true)
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import structlog
from prometheus_client import Counter, Histogram

from ..settings import settings
from ..episode_files import get_episode_file_manager

# Import web bridge for classification sync
try:
    web_scripts_path = Path(__file__).parent.parent.parent.parent / "web" / "scripts"
    sys.path.insert(0, str(web_scripts_path))
    from web_bridge import notify_classification_if_web_mode
    logger_import = structlog.get_logger()
    logger_import.debug("Web bridge imported successfully")
except ImportError:
    # Web bridge not available, continue without it
    def notify_classification_if_web_mode(classified):
        pass
    logger_import = structlog.get_logger()
    logger_import.debug("Web bridge not available, continuing without database sync")

# Set up structured logging
logger = structlog.get_logger()

# Prometheus metrics - handle duplicate registration gracefully
try:
    CLASSIFY_LATENCY = Histogram(
        "classify_latency_seconds", 
        "Time taken to classify tweets",
        ["run_id"],
        buckets=[1, 5, 10, 30, 60, 120, 300, 600]
    )
    TWEETS_CLASSIFIED = Counter(
        "tweets_classified_total",
        "Number of tweets classified"
    )
    TWEETS_RELEVANT = Counter(
        "tweets_relevant_total",
        "Number of tweets classified as RELEVANT"
    )
    TWEETS_SKIPPED = Counter(
        "tweets_skipped_total",
        "Number of tweets classified as SKIP"
    )
    CLASSIFY_ERRORS = Counter(
        "classify_errors_total",
        "Number of classification errors"
    )
except ValueError as e:
    # Metrics already registered, create no-op versions
    logger.info("Prometheus metrics already registered, using no-op collectors")
    
    class NoOpHistogram:
        def labels(self, **kwargs):
            return self
        def observe(self, *args, **kwargs): 
            pass
        def time(self):
            from contextlib import contextmanager
            @contextmanager
            def noop_timer():
                yield
            return noop_timer()
    
    class NoOpCounter:
        def inc(self, *args, **kwargs): 
            pass
    
    CLASSIFY_LATENCY = NoOpHistogram()
    TWEETS_CLASSIFIED = NoOpCounter()
    TWEETS_RELEVANT = NoOpCounter()
    TWEETS_SKIPPED = NoOpCounter()
    CLASSIFY_ERRORS = NoOpCounter()

# File paths
TWEETS_PATH = Path(settings.transcript_dir) / "tweets.json"
FEWSHOTS_PATH = Path(settings.transcript_dir) / "fewshots.json"
SUMMARY_PATH = Path(settings.transcript_dir) / "summary.md"
CLASSIFIED_PATH = Path(settings.transcript_dir) / "classified.json"


def load_tweets(file_manager=None) -> List[Dict]:
    """
    Load tweets from the tweets.json file
    
    Args:
        file_manager: Optional episode file manager
    
    Returns:
        List[Dict]: List of tweet dictionaries
    """
    try:
        if file_manager:
            tweets_text = file_manager.read_input('tweets')
            tweets = json.loads(tweets_text)
            path = file_manager.get_output_path('tweets')
        else:
            with open(TWEETS_PATH, "r") as f:
                tweets = json.load(f)
            path = TWEETS_PATH
            
        if not isinstance(tweets, list):
            logger.error(
                "Tweets file has invalid format",
                expected="list of tweet objects",
                path=str(path)
            )
            return []
            
        logger.info(
            "Loaded tweets",
            count=len(tweets),
            using_episode_files=bool(file_manager)
        )
        return tweets
        
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(
            "Failed to load tweets",
            error=str(e),
            path=str(path if 'path' in locals() else TWEETS_PATH)
        )
        return []


def run_3n_classifier(tweets: List[Dict], fewshots_path: Path = FEWSHOTS_PATH, summary_path: Path = SUMMARY_PATH, run_id: str = "unknown", search_days: int = 7) -> List[Dict]:
    """
    Run the tweet_classifier.py script on the tweets
    
    Args:
        tweets: List of tweet dictionaries
        fewshots_path: Path to the few-shot examples file
        summary_path: Path to the summary file
        run_id: Run ID for metrics labeling
        search_days: Number of days the search covered (for volume calculations)
        
    Returns:
        List[Dict]: List of tweet dictionaries with relevance score and classification added
    """
    # Create a temporary file with one tweet per line
    tweets_file = Path("temp_tweets_to_classify.txt")
    with open(tweets_file, "w") as f:
        for tweet in tweets:
            f.write(f"{tweet['text']}\n")
    
    # Build the command
    cmd = [
        sys.executable,
        "tweet_classifier.py",
        "--input-file", str(tweets_file),
        "--summary-file", str(summary_path),
        "--no-cache",  # Avoid caching for pipeline runs
        "--random",    # Use random examples for better diversity
        "--examples", "5",       # Use only 5 examples for faster processing
        "--max-examples", "5",  # Limit to first 20 fewshots as the pool
        "--workers", "8",        # Use more workers for faster processing
        "--debug"      # Enable debug output
    ]
    
    # Run the classifier
    logger.info(
        "Running tweet_classifier.py with first 20 fewshots only",
        cmd=" ".join(cmd)
    )
    
    try:
        with CLASSIFY_LATENCY.labels(run_id=run_id).time():
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            
        # Parse the output using regex pattern matching
        import re
        from ..score_utils import score_to_classification
        
        # Look for lines like "Score: 0.85 (Relevant) - RELEVANT"
        score_pattern = re.compile(r"Score:\s*(\d*\.?\d+)")
        scores = []
        
        lines = result.stdout.splitlines()
        tweet_index = 0
        
        for line in lines:
            match = score_pattern.search(line)
            if match:
                score = float(match.group(1))
                if tweet_index < len(tweets):
                    scores.append(score)
                    tweet_index += 1
        
        # Add scores and classifications to tweets
        if len(scores) != len(tweets):
            logger.error(
                "Number of scores doesn't match number of tweets",
                tweets=len(tweets),
                scores=len(scores)
            )
            raise ValueError("Score count mismatch")
            
        for tweet, score in zip(tweets, scores):
            tweet["relevance_score"] = score
            tweet["classification"] = score_to_classification(score)
            
            # Track keyword effectiveness AFTER classification
            if 'matched_keywords' in tweet:
                try:
                    from ..keyword_tracker import KeywordTracker
                    tracker = KeywordTracker()
                    
                    # Record the actual classification result for each keyword
                    for keyword in tweet['matched_keywords']:
                        # Track the classification outcome with actual search window
                        tracker.record_classification_result(
                            keyword=keyword,
                            classification=tweet['classification'],
                            score=score,
                            tweet_id=tweet.get('id'),
                            search_window_days=search_days
                        )
                        
                        logger.debug(
                            f"Tracked keyword classification",
                            keyword=keyword,
                            classification=tweet['classification'],
                            score=score
                        )
                except Exception as e:
                    logger.warning(f"Failed to track keyword effectiveness: {e}")
            
        # Update metrics
        from ..constants import RELEVANCY_THRESHOLD
        TWEETS_CLASSIFIED.inc(len(tweets))
        TWEETS_RELEVANT.inc(sum(1 for t in tweets if t.get("relevance_score", 0) >= RELEVANCY_THRESHOLD))
        TWEETS_SKIPPED.inc(sum(1 for t in tweets if t.get("relevance_score", 0) < RELEVANCY_THRESHOLD))
        
        # Clean up
        tweets_file.unlink()
        
        return tweets
        
    except subprocess.CalledProcessError as e:
        logger.error(
            "tweet_classifier.py failed",
            returncode=e.returncode,
            stdout=e.stdout,
            stderr=e.stderr
        )
        CLASSIFY_ERRORS.inc()
        
        # Clean up
        if tweets_file.exists():
            tweets_file.unlink()
            
        raise RuntimeError(f"tweet_classifier.py failed: {e}")
        
    except Exception as e:
        logger.error(
            "Error running tweet_classifier.py",
            error=str(e)
        )
        CLASSIFY_ERRORS.inc()
        
        # Clean up
        if tweets_file.exists():
            tweets_file.unlink()
            
        raise


def load_search_metadata(file_manager=None) -> Dict:
    """
    Load search metadata including days_back parameter.
    
    Args:
        file_manager: Optional episode file manager
        
    Returns:
        Dict with metadata including days_back
    """
    metadata = {'days_back': 7}  # Default
    
    try:
        if file_manager:
            # Try episode-specific metadata
            try:
                metadata_text = file_manager.read_input('tweets_metadata')
                metadata_data = json.loads(metadata_text)
                if 'metadata' in metadata_data:
                    metadata = metadata_data['metadata']
            except:
                pass
        else:
            # Try legacy metadata file
            metadata_path = TWEETS_PATH.parent / "tweets_metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata_data = json.load(f)
                    if 'metadata' in metadata_data:
                        metadata = metadata_data['metadata']
    except Exception as e:
        logger.warning(f"Could not load search metadata: {e}")
    
    return metadata

def run(run_id: str = None, fewshots_path: Path = None, episode_id: str = None, update_learning: bool = True) -> Path:
    """
    Run the tweet classification task
    
    Args:
        run_id: Optional run ID for artefact storage
        fewshots_path: Optional path to few-shot examples file
        episode_id: Optional episode ID for file management
        
    Returns:
        Path: Path to the classified tweets file
    """
    logger.info(
        "Starting tweet scoring task",
        run_id=run_id,
        episode_id=episode_id
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
    
    # Load tweets
    tweets = load_tweets(file_manager if use_episode_files else None)
    if not tweets:
        raise RuntimeError("No tweets found for classification")
    
    # Load search metadata to get actual days_back
    metadata = load_search_metadata(file_manager if use_episode_files else None)
    search_days = metadata.get('days_back', 7)
    logger.info(f"Using search window of {search_days} days for keyword tracking")
    
    # Determine paths based on episode files or legacy
    if use_episode_files:
        # Use episode paths
        if not fewshots_path:
            fewshots_path = file_manager.get_output_path('fewshots')
        summary_path = file_manager.get_output_path('summary')
        classified_path = file_manager.get_output_path('classified')
    else:
        # Use legacy paths
        fewshots_path = fewshots_path or FEWSHOTS_PATH
        summary_path = SUMMARY_PATH
        classified_path = CLASSIFIED_PATH
    
    # Run classifier with actual search days
    classified_tweets = run_3n_classifier(
        tweets, 
        fewshots_path, 
        summary_path, 
        run_id=run_id or "unknown",
        search_days=search_days
    )
    
    # Write to file
    if use_episode_files:
        file_manager.write_output('classified', classified_tweets)
    else:
        with open(classified_path, "w") as f:
            json.dump(classified_tweets, f, indent=2)
    
    # Calculate statistics
    from ..constants import RELEVANCY_THRESHOLD
    total_count = len(classified_tweets)
    relevant_count = sum(1 for t in classified_tweets if t.get("relevance_score", 0) >= RELEVANCY_THRESHOLD)
    skip_count = sum(1 for t in classified_tweets if t.get("relevance_score", 0) < RELEVANCY_THRESHOLD)
    avg_score = sum(t.get("relevance_score", 0) for t in classified_tweets) / total_count if total_count > 0 else 0
    relevancy_percentage = (relevant_count / total_count * 100) if total_count > 0 else 0
        
    logger.info(
        "Wrote scored tweets to file",
        path=str(classified_path),
        count=total_count,
        avg_score=f"{avg_score:.2f}",
        relevant_count=relevant_count,
        skip_count=skip_count,
        relevancy_percentage=f"{relevancy_percentage:.1f}%",
        using_episode_files=use_episode_files
    )
    
    # Update keyword learning based on classification results
    if update_learning:
        try:
            from ..keyword_learning import KeywordLearner
            learner = KeywordLearner()
            learner.update_learned_weights(episode_id=episode_id or run_id)
            
            # Get and log recommendations
            recommendations = learner.get_keyword_recommendations()
            if recommendations.get('low_performers'):
                logger.warning(
                    "Keywords performing poorly",
                    count=len(recommendations['low_performers']),
                    worst=recommendations['low_performers'][:3]
                )
            if recommendations.get('recommendations'):
                for rec in recommendations['recommendations'][:2]:
                    logger.info(f"Keyword recommendation: {rec}")
                    
        except Exception as e:
            logger.warning(f"Failed to update keyword learning: {e}")
    
    # Sync scores and classifications to web UI database if enabled
    try:
        notify_classification_if_web_mode(classified_tweets)
        logger.info("Synced scores to web UI database")
    except Exception as e:
        logger.warning(
            "Failed to sync scores to web UI",
            error=str(e)
        )
    
    # Copy to artefacts directory if run_id is provided
    if run_id:
        artefact_classified = artefact_dir / "classified.json"
        if use_episode_files:
            artefact_classified.write_text(json.dumps(classified_tweets, indent=2))
        else:
            artefact_classified.write_text(classified_path.read_text())
        
        logger.info(
            "Copied scored tweets to artefacts directory",
            path=str(artefact_classified)
        )
        
        return artefact_classified
        
    return classified_path


if __name__ == "__main__":
    # Configure logging when run directly
    logging.basicConfig(level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )
    
    # Run the task
    run() 