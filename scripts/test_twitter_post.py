#!/usr/bin/env python3
"""
Test script to verify Twitter/X API connection by posting a test tweet.
This script posts "I'M ALIVE!!!!" to the WDFwatch account.

Usage:
    python scripts/test_twitter_post.py
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from .env file in root directory
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"Loaded environment variables from {env_path}")

# ALSO load WDFwatch-specific tokens if they exist
wdfwatch_env_path = Path(__file__).parent.parent / ".env.wdfwatch"
if wdfwatch_env_path.exists():
    load_dotenv(wdfwatch_env_path, override=True)
    print(f"✅ Loaded WDFwatch tokens from {wdfwatch_env_path}")

from src.wdf.twitter_api_v2 import TwitterAPIv2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def post_test_tweet():
    """Post a test tweet to verify API connection."""
    
    # CRITICAL SAFETY CHECK #1: ABSOLUTELY REFUSE to use ACCESS_TOKEN
    if os.getenv("ACCESS_TOKEN"):
        logger.error("=" * 60)
        logger.error("🚨 CRITICAL: ACCESS_TOKEN detected in environment!")
        logger.error("This is the WDF_Show (managing) account token!")
        logger.error("REFUSING TO CONTINUE - This could post to wrong account!")
        logger.error("=" * 60)
        # Do NOT proceed if the dangerous token is present
        # Force user to use WDFWATCH tokens only
    
    # CRITICAL SAFETY CHECK #2: ONLY use WDFWATCH_ACCESS_TOKEN
    wdfwatch_token = os.getenv("WDFWATCH_ACCESS_TOKEN")
    
    if not wdfwatch_token:
        logger.error("=" * 60)
        logger.error("❌ WDFWATCH_ACCESS_TOKEN not found!")
        logger.error("This script REQUIRES WDFwatch-specific tokens.")
        logger.error("Run: python scripts/generate_wdfwatch_tokens.py")
        logger.error("=" * 60)
        return False
    
    # SAFE: Use ONLY WDFwatch tokens
    logger.info("✅ Using WDFWATCH_ACCESS_TOKEN (automated account)")
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_KEY_SECRET")
    access_token = wdfwatch_token
    access_token_secret = None  # OAuth 2.0 doesn't need this
    
    # Check if credentials are available
    if not all([api_key, api_secret, access_token]):
        logger.error("Missing required credentials!")
        logger.info("Please ensure your .env file contains:")
        logger.info("  - API_KEY (or CLIENT_ID)")
        logger.info("  - API_KEY_SECRET (or CLIENT_SECRET)")
        logger.info("  - WDFWATCH_ACCESS_TOKEN")
        return False
    
    try:
        # Initialize Twitter API client
        logger.info("Initializing Twitter API v2 client...")
        twitter = TwitterAPIv2(
            api_key=api_key,
            api_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret if access_token_secret else ""
        )
        
        # CRITICAL: Verify which account we're using
        logger.info("Verifying account identity...")
        user_response = twitter.session.get(f"{twitter.BASE_URL}/users/me")
        
        if user_response.status_code == 200:
            user_data = user_response.json()
            username = user_data.get('data', {}).get('username', 'unknown')
            user_id = user_data.get('data', {}).get('id', 'unknown')
            
            logger.info("=" * 60)
            logger.info(f"🔍 ACCOUNT VERIFICATION")
            logger.info(f"   Username: @{username}")
            logger.info(f"   User ID: {user_id}")
            
            if username.lower() == "wdfwatch" or username.lower() == "wdf_watch":
                logger.info("✅ CORRECT: This is the WDFwatch automated account")
            elif username.lower() == "wdf_show":
                logger.error("❌ WRONG ACCOUNT: This is the WDF_Show managing account!")
                logger.error("DO NOT POST! You need to generate tokens for WDFwatch")
                logger.error("Run: python scripts/generate_wdfwatch_tokens.py")
                return False
            else:
                logger.warning(f"⚠️  Unexpected account: @{username}")
                response = input("Continue anyway? (yes/no): ")
                if response.lower() != "yes":
                    return False
            logger.info("=" * 60)
        else:
            logger.warning("Could not verify account identity")
            logger.warning(f"Response: {user_response.status_code}")
        
        # Prepare the test tweet
        tweet_text = "I'M ALIVE!!!!"
        
        logger.info(f"Attempting to post tweet: {tweet_text}")
        
        # Post the tweet using the tweets endpoint directly
        endpoint = f"{twitter.BASE_URL}/tweets"
        payload = {'text': tweet_text}
        
        response = twitter.session.post(endpoint, json=payload)
        
        if response.status_code == 201:
            logger.info("✅ SUCCESS! Tweet posted successfully!")
            tweet_data = response.json()
            if 'data' in tweet_data and 'id' in tweet_data['data']:
                tweet_id = tweet_data['data']['id']
                logger.info(f"Tweet ID: {tweet_id}")
                logger.info(f"View at: https://twitter.com/WDF_Show/status/{tweet_id}")
            return True
        else:
            logger.error(f"❌ FAILED to post tweet!")
            logger.error(f"Status code: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error posting tweet: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Twitter/X API Connection Test")
    logger.info("=" * 60)
    
    # Try to load API keys from the database if in web mode
    if os.getenv('WDF_WEB_MODE', 'false').lower() == 'true':
        logger.info("Loading API keys from database...")
        try:
            import subprocess
            result = subprocess.run(
                ['python', 'scripts/load_api_keys.py'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Parse the output to set environment variables
                for line in result.stdout.strip().split('\n'):
                    if line.startswith('export '):
                        var_assignment = line.replace('export ', '')
                        if '=' in var_assignment:
                            key, value = var_assignment.split('=', 1)
                            # Remove quotes if present
                            value = value.strip('"').strip("'")
                            os.environ[key] = value
                logger.info("API keys loaded from database")
        except Exception as e:
            logger.warning(f"Could not load API keys from database: {e}")
    
    # Post the test tweet
    success = post_test_tweet()
    
    if success:
        logger.info("=" * 60)
        logger.info("🎉 Test completed successfully!")
        logger.info("The WDFwatch Twitter account is connected and working.")
        logger.info("=" * 60)
        sys.exit(0)
    else:
        logger.error("=" * 60)
        logger.error("Test failed. Please check your API credentials.")
        logger.error("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()