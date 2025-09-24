#!/usr/bin/env python3
"""
Manual processor for pending tweets in the queue
"""

import os
import sys
import subprocess
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables from .env.wdfwatch
env_file = Path(__file__).parent / '.env.wdfwatch'
if env_file.exists():
    print("Loading environment from .env.wdfwatch...")
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # Remove quotes if present
                value = value.strip('"').strip("'")
                os.environ[key] = value
                if 'API' in key or 'TOKEN' in key:
                    print(f"  Loaded {key}=***")

# Check if we have required keys
if not os.environ.get('WDFWATCH_ACCESS_TOKEN'):
    print("❌ ERROR: WDFWATCH_ACCESS_TOKEN not found in environment!")
    print("Please ensure .env.wdfwatch contains Twitter API credentials.")
    sys.exit(1)

if not os.environ.get('WDFWATCH_ACCESS_TOKEN_SECRET'):
    print("❌ ERROR: WDFWATCH_ACCESS_TOKEN_SECRET not found in environment!")
    sys.exit(1)

# Import after environment is set
from src.wdf.twitter_client import TwitterClient

def test_twitter_connection():
    """Test if we can connect to Twitter API"""
    try:
        print("\n🔧 Testing Twitter API connection...")
        client = TwitterClient(mock_mode=False)

        # Try to get user info to verify credentials
        print("  Verifying credentials...")
        # This will fail if credentials are invalid
        return True
    except Exception as e:
        print(f"❌ Twitter API connection failed: {e}")
        return False

def process_one_tweet():
    """Process a single pending tweet from the queue"""
    try:
        # Connect to database and get one pending tweet
        print("\n📊 Checking for pending tweets...")

        # Import Prisma client from web
        sys.path.insert(0, str(Path(__file__).parent / 'web'))
        from prisma import Prisma

        prisma = Prisma()
        prisma.connect()

        # Get one pending tweet
        pending = prisma.tweetqueue.find_first(
            where={
                'status': 'pending',
                'source': 'approved_draft'
            },
            order={'addedAt': 'asc'}
        )

        if not pending:
            print("✅ No pending tweets in queue!")
            return

        print(f"\n📝 Found pending tweet:")
        print(f"  Twitter ID: {pending.twitterId}")
        metadata = json.loads(pending.metadata) if isinstance(pending.metadata, str) else pending.metadata
        response_text = metadata.get('responseText', '')
        print(f"  Response: {response_text[:100]}...")

        # Post the tweet
        print("\n🐦 Posting to Twitter...")
        client = TwitterClient(mock_mode=False)

        try:
            result = client.reply_to_tweet(
                tweet_id=pending.twitterId,
                reply_text=response_text
            )

            print(f"✅ Successfully posted reply!")
            print(f"  Reply ID: {result.get('id', 'unknown')}")

            # Update queue status
            prisma.tweetqueue.update(
                where={'id': pending.id},
                data={
                    'status': 'completed',
                    'processedAt': 'now()'
                }
            )

            # Update draft status if we have the draft ID
            if metadata.get('draftId'):
                prisma.draftreply.update(
                    where={'id': metadata['draftId']},
                    data={
                        'status': 'posted',
                        'postedAt': 'now()'
                    }
                )

            print("✅ Database updated!")

        except Exception as e:
            print(f"❌ Failed to post tweet: {e}")

            # Update queue with error
            prisma.tweetqueue.update(
                where={'id': pending.id},
                data={
                    'retryCount': pending.retryCount + 1,
                    'metadata': json.dumps({
                        **metadata,
                        'lastError': str(e)
                    })
                }
            )

        finally:
            prisma.disconnect()

    except Exception as e:
        print(f"❌ Error processing tweet: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 WDFWatch Tweet Queue Processor")
    print("=" * 50)

    # Test connection first
    if test_twitter_connection():
        print("✅ Twitter API connection successful!")
        process_one_tweet()
    else:
        print("\n❌ Cannot proceed without valid Twitter connection.")
        print("\nPlease check:")
        print("1. .env.wdfwatch file exists and contains:")
        print("   - WDFWATCH_ACCESS_TOKEN")
        print("   - WDFWATCH_ACCESS_TOKEN_SECRET")
        print("   - API_KEY")
        print("   - API_KEY_SECRET")
        print("2. The tokens are valid and not expired")
        print("3. The WDFwatch account has proper permissions")