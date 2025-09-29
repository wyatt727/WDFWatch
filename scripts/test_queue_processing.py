#!/usr/bin/env python3
"""
Test the tweet queue processing with the new logic.
This script simulates queue processing to verify the behavior.
"""

import json
import requests
import time

def test_queue_processing():
    """Test the queue processing logic."""

    # Simulated queue processing logic
    MAX_CONSECUTIVE_FAILURES = 10
    DELAY_BETWEEN_POSTS = 2  # seconds
    RATE_LIMIT_DELAY = 30  # seconds

    # Simulate a queue of tweets
    queue_items = [f"tweet_{i}" for i in range(50)]  # 50 tweets to process

    results = []
    success_count = 0
    consecutive_failures = 0

    print(f"Processing {len(queue_items)} tweets from queue...")

    for i, item in enumerate(queue_items):
        # Check if we should stop
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            print(f"\n❌ Stopping - {consecutive_failures} consecutive failures reached")
            break

        # Add delay between posts (except for first)
        if i > 0:
            print(f"Post {i + 1}/{len(queue_items)} - waiting {DELAY_BETWEEN_POSTS}s...")
            time.sleep(DELAY_BETWEEN_POSTS)

        # Simulate posting (with various outcomes)
        import random
        outcome = random.choice(['success'] * 7 + ['failure'] * 2 + ['rate_limit'] * 1)

        if outcome == 'success':
            success_count += 1
            consecutive_failures = 0  # Reset on success
            results.append({'id': item, 'status': 'completed'})
            print(f"✅ Post {i + 1}/{len(queue_items)} successful ({success_count} total)")

        elif outcome == 'rate_limit':
            # Rate limit doesn't count as failure
            print(f"⚠️  Post {i + 1} rate limited - pausing {RATE_LIMIT_DELAY}s...")
            time.sleep(RATE_LIMIT_DELAY)
            results.append({'id': item, 'status': 'rate_limited'})
            # Don't increment consecutive_failures

        else:  # failure
            consecutive_failures += 1
            results.append({'id': item, 'status': 'failed'})
            print(f"❌ Failure {consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}")

    # Final summary
    stopped_early = consecutive_failures >= MAX_CONSECUTIVE_FAILURES

    print("\n" + "=" * 60)
    print("QUEUE PROCESSING SUMMARY")
    print("=" * 60)
    print(f"Total in queue: {len(queue_items)}")
    print(f"Processed: {len(results)}")
    print(f"Successful: {sum(1 for r in results if r['status'] == 'completed')}")
    print(f"Failed: {sum(1 for r in results if r['status'] == 'failed')}")
    print(f"Rate limited: {sum(1 for r in results if r['status'] == 'rate_limited')}")
    print(f"Remaining: {len(queue_items) - len(results)}")

    if stopped_early:
        print(f"\n⚠️  Processing stopped early after {consecutive_failures} consecutive failures")
    else:
        print("\n✅ All tweets processed successfully")

    return {
        'message': f"Queue processing {'stopped early' if stopped_early else 'completed'}",
        'processed': len(results),
        'totalInQueue': len(queue_items),
        'successful': sum(1 for r in results if r['status'] == 'completed'),
        'failed': sum(1 for r in results if r['status'] == 'failed'),
        'remaining': len(queue_items) - len(results),
        'stoppedEarly': stopped_early
    }

if __name__ == "__main__":
    print("Testing Tweet Queue Processing Logic")
    print("=" * 60)
    print("Configuration:")
    print("- Process ALL tweets (not just 10)")
    print("- 2 second delay between posts")
    print("- Stop after 10 consecutive failures")
    print("- Rate limits don't count as failures")
    print("=" * 60)
    print()

    result = test_queue_processing()
    print("\nFinal result:", json.dumps(result, indent=2))