#!/usr/bin/env python3
"""
Process all pending tweets from the queue
"""

import subprocess
import sys
import time
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent / 'web'))

from prisma import Prisma

def process_all_pending():
    """Process all pending tweets in the queue"""

    prisma = Prisma()
    prisma.connect()

    try:
        # Get all pending tweets
        pending_tweets = prisma.tweetqueue.find_many(
            where={
                'status': 'pending',
                'source': 'approved_draft'
            },
            order={'addedAt': 'asc'}
        )

        total = len(pending_tweets)
        print(f"\n📊 Found {total} pending tweets to process")

        if total == 0:
            print("✅ No pending tweets!")
            return

        # Process confirmation
        confirm = input(f"\nProcess all {total} tweets? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Cancelled.")
            return

        success_count = 0
        fail_count = 0

        for i, tweet in enumerate(pending_tweets, 1):
            try:
                metadata = json.loads(tweet.metadata) if isinstance(tweet.metadata, str) else tweet.metadata
                response_text = metadata.get('responseText', '')
                twitter_id = tweet.twitterId

                print(f"\n[{i}/{total}] Processing tweet {twitter_id}")
                print(f"  Response: {response_text[:80]}...")

                # Call the safe Twitter reply script
                cmd = [
                    './venv/bin/python',
                    'scripts/safe_twitter_reply.py',
                    '--tweet-id', twitter_id,
                    '--message', response_text
                ]

                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode == 0 and "Successfully replied" in result.stdout:
                    print(f"  ✅ Posted successfully!")
                    success_count += 1

                    # Update queue status
                    prisma.tweetqueue.update(
                        where={'id': tweet.id},
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
                else:
                    print(f"  ❌ Failed to post")
                    fail_count += 1

                    # Update retry count
                    prisma.tweetqueue.update(
                        where={'id': tweet.id},
                        data={
                            'retryCount': tweet.retryCount + 1,
                            'metadata': json.dumps({
                                **metadata,
                                'lastError': result.stderr[:500] if result.stderr else 'Unknown error'
                            })
                        }
                    )

                # Rate limiting - Twitter allows 300 posts per 3 hours
                # That's about 1 post per 36 seconds, so let's be safe
                if i < total:
                    print("  ⏳ Waiting 40 seconds before next tweet...")
                    time.sleep(40)

            except Exception as e:
                print(f"  ❌ Error: {e}")
                fail_count += 1

        print("\n" + "=" * 60)
        print(f"📊 Processing Complete!")
        print(f"✅ Success: {success_count}")
        print(f"❌ Failed: {fail_count}")
        print("=" * 60)

    finally:
        prisma.disconnect()

if __name__ == "__main__":
    print("🚀 WDFWatch Queue Processor")
    print("=" * 60)
    process_all_pending()