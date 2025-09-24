#!/usr/bin/env python3
"""
Process a few pending tweets from the queue
"""

import subprocess
import sys
import time
import json
from pathlib import Path

# Add project root to path
web_dir = Path(__file__).parent / 'web'
sys.path.insert(0, str(web_dir))

# Import Prisma
try:
    from lib.prisma import prisma
except ImportError:
    # Alternative import path
    sys.path.insert(0, str(web_dir / 'lib'))
    from prisma import prisma

def process_few_pending(limit=5):
    """Process a limited number of pending tweets"""

    try:
        # Get a few pending tweets
        pending_tweets = prisma.tweetqueue.find_many(
            where={
                'status': 'pending',
                'source': 'approved_draft'
            },
            order={'addedAt': 'asc'},
            take=limit
        )

        total = len(pending_tweets)
        print(f"\n📊 Processing {total} pending tweets (out of many more)")

        if total == 0:
            print("✅ No pending tweets!")
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
                    print(f"  Error: {result.stderr[:200] if result.stderr else 'Unknown'}")
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

                # Small delay between tweets (10 seconds for this test run)
                if i < total:
                    print("  ⏳ Waiting 10 seconds before next tweet...")
                    time.sleep(10)

            except Exception as e:
                print(f"  ❌ Error: {e}")
                fail_count += 1

        print("\n" + "=" * 60)
        print(f"📊 Processing Complete!")
        print(f"✅ Success: {success_count}")
        print(f"❌ Failed: {fail_count}")

        # Check remaining
        remaining = prisma.tweetqueue.count(
            where={
                'status': 'pending',
                'source': 'approved_draft'
            }
        )

        if remaining > 0:
            print(f"📋 Remaining in queue: {remaining} tweets")
            print(f"💡 Run 'python process_all_pending.py' to process all")

        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error in main processing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 WDFWatch Queue Processor (Limited Run)")
    print("=" * 60)

    # Check for command line argument
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=5, help='Number of tweets to process')
    args = parser.parse_args()

    process_few_pending(args.limit)