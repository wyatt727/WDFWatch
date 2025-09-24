#!/usr/bin/env python3
"""
Manual Tweet Scraping Task

Handles manual scraping requests from the web UI with custom parameters.
This script acts as a bridge between the web UI and the standard scrape.py task.

Related files:
- /web/app/api/scraping/trigger/route.ts (API trigger)
- /src/wdf/tasks/scrape.py (Original scraping task)
- /src/wdf/web_bridge.py (Database integration)
"""

import json
import os
import sys
import subprocess
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

import structlog
from pydantic import BaseModel

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

logger = structlog.get_logger(__name__)


class ScrapeParams(BaseModel):
    """Parameters for manual scraping"""
    keywords: List[str]
    maxTweets: int = 100
    daysBack: int = 7
    minLikes: int = 0
    minRetweets: int = 0
    minReplies: int = 0
    excludeReplies: bool = False
    excludeRetweets: bool = False
    language: str = "en"
    run_id: str
    episode_id: Optional[str] = None


def run_manual_scrape(params: ScrapeParams) -> bool:
    """
    Run manual scraping by calling the standard scrape.py with manual trigger
    
    Args:
        params: Scraping parameters from web UI
        
    Returns:
        bool: True if successful
    """
    logger.info(
        "Starting manual scrape",
        run_id=params.run_id,
        keywords_count=len(params.keywords),
        max_tweets=params.maxTweets,
    )
    
    # Write keywords to JSON file for the scraper
    keywords_file = Path("transcripts/keywords.json")
    keywords_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Save current keywords and replace with manual keywords
    backup_keywords = None
    if keywords_file.exists():
        with open(keywords_file) as f:
            backup_keywords = json.load(f)
    
    try:
        # Write manual keywords
        with open(keywords_file, "w") as f:
            json.dump(params.keywords, f, indent=2)
        
        # Temporarily disable auto-scrape protection
        old_env = os.environ.get("WDF_NO_AUTO_SCRAPE")
        os.environ["WDF_NO_AUTO_SCRAPE"] = "false"
        
        # Run the standard scraper with manual trigger flag (as module to fix imports)
        cmd = [
            sys.executable,
            "-m",
            "src.wdf.tasks.scrape",
            f"--run-id={params.run_id}",
            f"--count={params.maxTweets}",
            "--manual-trigger"
        ]
        
        if params.episode_id:
            cmd.append(f"--episode-id={params.episode_id}")
        
        logger.info(f"Running command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("Manual scraping completed successfully")
            return True
        else:
            logger.error(f"Manual scraping failed: {result.stderr}")
            return False
            
    finally:
        # Restore original keywords
        if backup_keywords is not None:
            with open(keywords_file, "w") as f:
                json.dump(backup_keywords, f, indent=2)
        
        # Restore environment variable
        if old_env is not None:
            os.environ["WDF_NO_AUTO_SCRAPE"] = old_env
        elif "WDF_NO_AUTO_SCRAPE" in os.environ:
            del os.environ["WDF_NO_AUTO_SCRAPE"]


def main():
    """Main entry point for manual scraping"""
    parser = argparse.ArgumentParser(description="Manual tweet scraping")
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
        params = ScrapeParams(**params_dict)
        
        # Execute scraping
        success = run_manual_scrape(params)
        
        if success:
            print("Successfully completed manual scraping")
            sys.exit(0)
        else:
            print("Manual scraping failed")
            sys.exit(1)
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON parameters: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()