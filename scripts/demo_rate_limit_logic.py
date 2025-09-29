#!/usr/bin/env python3
"""
Demo of the automatic rate limit recovery logic.
Shows how the queue handles Twitter's 50 tweets/15 minutes limit.
"""

from datetime import datetime, timedelta

def calculate_next_window_reset():
    """Calculate when the next 15-minute rate limit window resets."""
    now = datetime.now()
    current_minute = now.minute

    # Twitter uses 15-minute windows starting at :00, :15, :30, :45
    window_start = (current_minute // 15) * 15
    next_window_start = (window_start + 15) % 60

    # Create next reset time
    reset_time = datetime(now.year, now.month, now.day, now.hour, next_window_start, 0, 0)

    # If next window is in the past (we're near hour boundary), add an hour
    if reset_time <= now:
        reset_time = reset_time.replace(hour=(reset_time.hour + 1) % 24)
        # Handle day boundary
        if reset_time.hour == 0:
            reset_time = reset_time + timedelta(days=1)

    return reset_time

def demo_rate_limit_handling():
    """Demonstrate the rate limit handling logic."""
    print("=" * 70)
    print("TWITTER RATE LIMIT AUTO-RECOVERY DEMO")
    print("=" * 70)

    # Simulate different scenarios
    scenarios = [
        ("Current time: 14:12", datetime(2024, 1, 1, 14, 12, 30)),
        ("Current time: 14:29", datetime(2024, 1, 1, 14, 29, 45)),
        ("Current time: 14:44", datetime(2024, 1, 1, 14, 44, 50)),
        ("Current time: 14:59", datetime(2024, 1, 1, 14, 59, 30)),
    ]

    for description, simulated_now in scenarios:
        print(f"\n{description}")
        print("-" * 40)

        # Calculate reset for this scenario
        # (In real code, we use actual current time)
        current_minute = simulated_now.minute
        window_start = (current_minute // 15) * 15
        next_window_start = (window_start + 15) % 60

        reset_time = datetime(
            simulated_now.year, simulated_now.month, simulated_now.day,
            simulated_now.hour, next_window_start, 0, 0
        )

        # Handle hour boundary
        if reset_time <= simulated_now:
            reset_time = reset_time.replace(hour=(reset_time.hour + 1) % 24)

        wait_seconds = (reset_time - simulated_now).total_seconds()
        wait_minutes = wait_seconds / 60

        print(f"  Current window: :{window_start:02d}-:{window_start+14:02d}")
        print(f"  Next reset at: {reset_time.strftime('%H:%M:%S')}")
        print(f"  Wait time: {wait_minutes:.1f} minutes ({wait_seconds:.0f} seconds)")
        print(f"  Action: Wait {wait_minutes:.1f} min, then continue automatically")

def simulate_queue_processing():
    """Simulate the actual queue processing with rate limits."""
    print("\n" + "=" * 70)
    print("SIMULATED QUEUE PROCESSING")
    print("=" * 70)

    total_tweets = 120  # Simulate 120 tweets to process
    tweets_posted = 0

    print(f"\nStarting to process {total_tweets} tweets...")

    while tweets_posted < total_tweets:
        # Process up to 50 tweets
        batch_size = min(50, total_tweets - tweets_posted)

        print(f"\n📤 Processing batch: tweets {tweets_posted + 1}-{tweets_posted + batch_size}")

        # Simulate hitting rate limit after 50 tweets
        if tweets_posted > 0 and tweets_posted % 50 == 0:
            reset_time = calculate_next_window_reset()
            now = datetime.now()
            wait_seconds = (reset_time - now).total_seconds()
            wait_minutes = wait_seconds / 60

            print(f"\n⏰ RATE LIMITED after {tweets_posted} tweets")
            print(f"📊 Successfully posted {tweets_posted} tweets so far")
            print(f"🔄 Rate limit resets at {reset_time.strftime('%H:%M:%S')}")
            print(f"⏳ Waiting {wait_minutes:.1f} minutes for reset...")
            print(f"✅ Will automatically continue processing remaining {total_tweets - tweets_posted} tweets")
            print(f"\n[Simulated wait of {wait_minutes:.1f} minutes...]")
            print(f"\n🎉 Rate limit reset! Continuing to process remaining tweets...")

        tweets_posted += batch_size
        print(f"✅ Posted {tweets_posted}/{total_tweets} tweets")

    print(f"\n🎊 COMPLETE! All {total_tweets} tweets processed successfully!")
    print("The queue handled rate limits automatically without manual intervention.")

if __name__ == "__main__":
    # Show the calculation logic
    demo_rate_limit_handling()

    # Show how it works in practice
    simulate_queue_processing()

    print("\n" + "=" * 70)
    print("KEY FEATURES:")
    print("- Automatically calculates rate limit reset time")
    print("- Waits the exact amount needed (no wasted time)")
    print("- Continues processing automatically after wait")
    print("- Clear user feedback about what's happening")
    print("- Handles hour/day boundaries correctly")
    print("=" * 70)