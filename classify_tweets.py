#!/Users/pentester/Tools/gemma-3n/venv/bin/python3
"""
classify_tweets.py - Directly run the tweet_classifier.py script on tweets.json

This script loads tweets from tweets.json, runs them through the tweet_classifier.py script
using the first 5 fewshots, and saves the results to classified.json.
This avoids the Prometheus metrics collision error that happens when running
the src.wdf.tasks.classify module directly.

Usage:
  python classify_tweets.py [--verbose]
"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

import structlog

# Set up structured logging
logger = structlog.get_logger()

# Constants
TWEETS_PATH = Path("transcripts/tweets.json")
FEWSHOTS_PATH = Path("transcripts/fewshots.json")
SUMMARY_PATH = Path("transcripts/summary.md")
CLASSIFIED_PATH = Path("transcripts/classified.json")


def load_tweets() -> list:
    """
    Load tweets from the tweets.json file
    
    Returns:
        List of tweet dictionaries
    """
    try:
        with open(TWEETS_PATH, "r") as f:
            tweets = json.load(f)
            
        logger.info(
            "Loaded tweets",
            count=len(tweets)
        )
        return tweets
        
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(
            "Failed to load tweets",
            error=str(e),
            path=str(TWEETS_PATH)
        )
        return []


def classify_tweets(tweets: list, verbose: bool = False) -> list:
    """
    Classify tweets using the tweet_classifier.py script
    
    Args:
        tweets: List of tweet dictionaries
        verbose: Enable verbose output
        
    Returns:
        List of tweet dictionaries with classifications added
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
        "--summary-file", str(SUMMARY_PATH),
        "--no-cache",  # Avoid caching for pipeline runs
        "--random",    # Use random examples for better diversity
        "--max-examples", "5",  # Use only first 20 fewshots as requested
    ]
    
    if verbose:
        cmd.append("--debug")
    
    # Run the classifier
    logger.info(
        "Running tweet_classifier.py with first 5 fewshots only",
        cmd=" ".join(cmd)
    )
    
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )
        
        # Parse the output using regex pattern matching
        import re
        
        # Look for lines like "Result: RELEVANT" or "Result: SKIP"
        result_pattern = re.compile(r"Result:\s*(RELEVANT|SKIP)")
        classifications = []
        
        lines = result.stdout.splitlines()
        
        for line in lines:
            match = result_pattern.search(line)
            if match:
                classification = match.group(1).strip()
                classifications.append(classification)
        
        # Add classifications to tweets
        if len(classifications) != len(tweets):
            logger.error(
                "Number of classifications doesn't match number of tweets",
                tweets=len(tweets),
                classifications=len(classifications)
            )
            raise ValueError("Classification count mismatch")
            
        for tweet, classification in zip(tweets, classifications):
            tweet["classification"] = classification
        
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
        
        # Clean up
        if tweets_file.exists():
            tweets_file.unlink()
            
        raise RuntimeError(f"tweet_classifier.py failed: {e}")
        
    except Exception as e:
        logger.error(
            "Error running tweet_classifier.py",
            error=str(e)
        )
        
        # Clean up
        if tweets_file.exists():
            tweets_file.unlink()
            
        raise


def save_classified_tweets(tweets: list) -> None:
    """
    Save classified tweets to classified.json
    
    Args:
        tweets: List of tweet dictionaries with classifications
    """
    with open(CLASSIFIED_PATH, "w") as f:
        json.dump(tweets, f, indent=2)
        
    logger.info(
        "Wrote classified tweets to file",
        path=str(CLASSIFIED_PATH),
        count=len(tweets),
        relevant_count=sum(1 for t in tweets if t.get("classification") == "RELEVANT"),
        skip_count=sum(1 for t in tweets if t.get("classification") == "SKIP")
    )


def main() -> int:
    """
    Main entry point
    
    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        description="Directly run the tweet_classifier.py script on tweets.json"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true", 
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )
    
    try:
        # Load tweets
        tweets = load_tweets()
        if not tweets:
            logger.error("No tweets found for classification")
            return 1
        
        # Classify tweets
        classified_tweets = classify_tweets(tweets, args.verbose)
        
        # Save results
        save_classified_tweets(classified_tweets)
        
        logger.info(
            "Classification completed successfully",
            tweet_count=len(classified_tweets)
        )
        
        return 0
        
    except Exception as e:
        logger.error(
            "Error during classification",
            error=str(e)
        )
        return 1


if __name__ == "__main__":
    sys.exit(main()) 