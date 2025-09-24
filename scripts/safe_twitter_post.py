#!/usr/bin/env python3
"""
SAFE Twitter posting script that ONLY uses WDFwatch tokens.
This script is designed to be absolutely bulletproof against posting to the wrong account.

SAFETY FEATURES:
1. NEVER loads ACCESS_TOKEN or ACCESS_TOKEN_SECRET (WDF_Show tokens)
2. ONLY uses WDFWATCH_ACCESS_TOKEN
3. Verifies account identity before posting
4. Multiple safety checks and confirmations

Usage:
    python scripts/safe_twitter_post.py [--message "Your message here"]
"""

import os
import sys
import logging
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_safe_environment():
    """Load ONLY safe environment variables, excluding dangerous tokens."""
    
    # First, load the base .env but we'll ignore dangerous variables
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        # Load into a dict first so we can filter
        from dotenv import dotenv_values
        env_vars = dotenv_values(env_path)
        
        # CRITICAL: Remove dangerous tokens that could post to WDF_Show
        dangerous_keys = ['ACCESS_TOKEN', 'ACCESS_TOKEN_SECRET', 'TWITTER_TOKEN', 'TWITTER_TOKEN_SECRET']
        for key in dangerous_keys:
            if key in env_vars:
                logger.warning(f"⚠️  Ignoring {key} (WDF_Show token)")
                env_vars.pop(key)
        
        # Now load the safe variables
        for key, value in env_vars.items():
            if key not in os.environ:  # Don't override if already set
                os.environ[key] = value
        
        logger.info(f"Loaded safe environment variables from {env_path}")
    
    # Now load WDFwatch-specific tokens (these override everything)
    wdfwatch_env = Path(__file__).parent.parent / ".env.wdfwatch" 
    if wdfwatch_env.exists():
        load_dotenv(wdfwatch_env, override=True)
        logger.info(f"✅ Loaded WDFwatch tokens from {wdfwatch_env}")
    else:
        # Check if WDFWATCH tokens are in main .env
        if 'WDFWATCH_ACCESS_TOKEN' in env_vars:
            logger.info("✅ Found WDFWATCH_ACCESS_TOKEN in main .env")

def post_safe_tweet(message=None):
    """Post a tweet using ONLY WDFwatch account tokens."""
    
    # Load environment safely
    load_safe_environment()
    
    # CRITICAL: Verify we have ONLY WDFwatch tokens
    if os.getenv("ACCESS_TOKEN"):
        logger.error("=" * 60)
        logger.error("🚨 FATAL: ACCESS_TOKEN (WDF_Show) is in environment!")
        logger.error("This script refuses to run with WDF_Show tokens present.")
        logger.error("=" * 60)
        sys.exit(1)
    
    wdfwatch_token = os.getenv("WDFWATCH_ACCESS_TOKEN")
    if not wdfwatch_token:
        logger.error("=" * 60)
        logger.error("❌ WDFWATCH_ACCESS_TOKEN not found!")
        logger.error("This script ONLY works with WDFwatch tokens.")
        logger.error("=" * 60)
        sys.exit(1)
    
    # Get other required credentials
    api_key = os.getenv("API_KEY") or os.getenv("CLIENT_ID")
    api_secret = os.getenv("API_KEY_SECRET") or os.getenv("CLIENT_SECRET")
    
    if not all([api_key, api_secret]):
        logger.error("Missing API_KEY or API_KEY_SECRET")
        sys.exit(1)
    
    # Import Twitter API
    from src.wdf.twitter_api_v2 import TwitterAPIv2
    
    # Initialize client with WDFwatch token
    logger.info("Initializing Twitter API v2 client with WDFwatch token...")
    twitter = TwitterAPIv2(
        api_key=api_key,
        api_secret=api_secret,
        access_token=wdfwatch_token,
        access_token_secret=""  # Not needed for OAuth 2.0
    )
    
    # CRITICAL: Verify account identity
    logger.info("🔍 Verifying account identity...")
    user_response = twitter.session.get(f"{twitter.BASE_URL}/users/me")
    
    if user_response.status_code != 200:
        logger.error(f"Failed to verify account: {user_response.status_code}")
        logger.error(f"Response: {user_response.text}")
        sys.exit(1)
    
    user_data = user_response.json()
    username = user_data.get('data', {}).get('username', 'unknown')
    user_id = user_data.get('data', {}).get('id', 'unknown')
    
    # CRITICAL: Ensure it's WDFwatch
    logger.info("=" * 60)
    logger.info(f"Account: @{username} (ID: {user_id})")
    
    if username.lower() not in ['wdfwatch', 'wdf_watch']:
        if username.lower() == 'wdf_show':
            logger.error("=" * 60)
            logger.error("🚨 FATAL: This is the WDF_Show account!")
            logger.error("ABORTING - Will NOT post to managing account!")
            logger.error("=" * 60)
            sys.exit(1)
        else:
            logger.error(f"❌ Unexpected account: @{username}")
            logger.error("This script only posts to @WDFwatch")
            sys.exit(1)
    
    logger.info("✅ Confirmed: This is the WDFwatch automated account")
    logger.info("=" * 60)
    
    # Determine message to post
    if not message:
        message = "I'M ALIVE!!!!"
    
    logger.info(f"Posting: {message}")
    
    # Post the tweet
    endpoint = f"{twitter.BASE_URL}/tweets"
    payload = {'text': message}
    
    response = twitter.session.post(endpoint, json=payload)
    
    if response.status_code == 201:
        logger.info("✅ Tweet posted successfully!")
        tweet_data = response.json()
        if 'data' in tweet_data and 'id' in tweet_data['data']:
            tweet_id = tweet_data['data']['id']
            logger.info(f"Tweet ID: {tweet_id}")
            logger.info(f"View at: https://twitter.com/WDFwatch/status/{tweet_id}")
        return True
    else:
        logger.error(f"❌ Failed to post tweet!")
        logger.error(f"Status: {response.status_code}")
        logger.error(f"Response: {response.text}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Safely post to WDFwatch account')
    parser.add_argument('--message', '-m', type=str, help='Message to tweet')
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("WDFwatch Safe Twitter Poster")
    logger.info("This script ONLY posts to @WDFwatch")
    logger.info("=" * 60)
    
    success = post_safe_tweet(args.message)
    
    if success:
        logger.info("=" * 60)
        logger.info("🎉 Successfully posted to @WDFwatch!")
        logger.info("=" * 60)
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()