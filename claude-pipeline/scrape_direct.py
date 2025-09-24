#!/usr/bin/env python3
"""
Direct Twitter scraping for episodes - bypasses orchestrator dependency issues
"""

import json
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

def scrape_tweets_for_episode(episode_id: str):
    """Scrape tweets using Twitter API for the given episode"""

    # Get episode directory
    episode_dir = Path(__file__).parent / "episodes" / episode_id
    if not episode_dir.exists():
        print(f"Error: Episode directory not found: {episode_dir}")
        return 1

    # Load keywords
    keywords_file = episode_dir / "keywords.json"
    if not keywords_file.exists():
        print(f"Error: Keywords file not found: {keywords_file}")
        return 1

    with open(keywords_file) as f:
        keywords_data = json.load(f)

    keywords = [kw['keyword'] if isinstance(kw, dict) else str(kw) for kw in keywords_data]
    print(f"Scraping tweets for keywords: {', '.join(keywords)}")

    # Set up environment for scraping
    project_root = Path(__file__).parent.parent
    env = os.environ.copy()

    # Load credentials from .env files
    env_file = project_root / '.env'
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip().strip('"').strip("'")
                        env[key] = value

    wdfwatch_env = project_root / '.env.wdfwatch'
    if wdfwatch_env.exists():
        with open(wdfwatch_env, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip().strip('"').strip("'")
                        env[key] = value

    # Check for credentials
    has_wdfwatch = 'WDFWATCH_ACCESS_TOKEN' in env
    has_api_keys = 'API_KEY' in env and 'API_KEY_SECRET' in env

    if not (has_wdfwatch or has_api_keys):
        print("Warning: No Twitter API credentials found")
        print("Generating sample tweets instead...")

        # Generate sample tweets
        from generate_sample_tweets import generate_tweets_for_keywords
        tweets = generate_tweets_for_keywords(keywords, count=20)

        tweets_file = episode_dir / "tweets.json"
        with open(tweets_file, 'w') as f:
            json.dump(tweets, f, indent=2)

        print(f"Generated {len(tweets)} sample tweets")
        return 0

    print("Twitter credentials found - making API calls...")

    # Set environment for real scraping
    env['WDF_WEB_MODE'] = 'false'
    env['WDF_EPISODE_ID'] = episode_id
    env['WDF_NO_AUTO_SCRAPE'] = 'false'  # Allow API calls
    env['WDF_BYPASS_QUOTA_CHECK'] = 'true'  # Bypass quota for manual trigger
    env['PYTHONPATH'] = str(project_root)

    # Call scrape.py directly
    cmd = [
        sys.executable, '-m', 'src.wdf.tasks.scrape',
        '--episode-id', episode_id,
        '--count', '100'
    ]

    print(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            env=env,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            print("Scraping completed successfully")

            # Check if tweets were saved
            tweets_file = episode_dir / "tweets.json"
            if tweets_file.exists():
                with open(tweets_file) as f:
                    tweets = json.load(f)
                print(f"Scraped {len(tweets)} tweets")

                # Show sample
                if tweets:
                    print(f"\nSample tweet: {tweets[0].get('text', 'NO TEXT')[:100]}...")
            else:
                print("Warning: No tweets file created")

            return 0
        else:
            print(f"Scraping failed with return code {result.returncode}")
            if result.stderr:
                print(f"Error: {result.stderr[:500]}")
            return 1

    except subprocess.TimeoutExpired:
        print("Scraping timed out after 60 seconds")
        return 1
    except Exception as e:
        print(f"Error running scrape: {e}")
        return 1

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scrape_direct.py <episode_id>")
        sys.exit(1)

    episode_id = sys.argv[1]
    sys.exit(scrape_tweets_for_episode(episode_id))