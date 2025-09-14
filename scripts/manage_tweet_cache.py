#!/usr/bin/env python3
"""
Tweet Cache Management Script

Provides CLI commands to manage the tweet cache used for testing
without making API calls.

Usage:
    python scripts/manage_tweet_cache.py stats     # Show cache statistics
    python scripts/manage_tweet_cache.py clean     # Remove old tweets
    python scripts/manage_tweet_cache.py clear     # Clear entire cache
    python scripts/manage_tweet_cache.py import <file>  # Import tweets from JSON file
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.wdf.tweet_cache import get_tweet_cache

def show_stats():
    """Display cache statistics"""
    cache = get_tweet_cache()
    stats = cache.get_stats()
    
    print("\n📊 Tweet Cache Statistics")
    print("=" * 50)
    print(f"Total tweets: {stats['total_tweets']}")
    print(f"Cache file: {stats['cache_file']}")
    
    if stats['total_tweets'] > 0:
        print(f"Oldest tweet: {stats['oldest_tweet']}")
        print(f"Newest tweet: {stats['newest_tweet']}")
    
    if stats['last_updated']:
        print(f"Last updated: {stats['last_updated']}")
    print()

def clean_cache():
    """Remove old tweets from cache"""
    cache = get_tweet_cache()
    
    print("🧹 Cleaning tweet cache...")
    stats_before = cache.get_stats()
    cache.clear_old_tweets()
    stats_after = cache.get_stats()
    
    removed = stats_before['total_tweets'] - stats_after['total_tweets']
    print(f"✅ Removed {removed} old tweets")
    print(f"   Remaining tweets: {stats_after['total_tweets']}")

def clear_cache():
    """Clear entire cache"""
    cache = get_tweet_cache()
    
    stats = cache.get_stats()
    if stats['total_tweets'] == 0:
        print("ℹ️  Cache is already empty")
        return
    
    # Ask for confirmation
    response = input(f"⚠️  This will delete {stats['total_tweets']} cached tweets. Continue? [y/N]: ")
    if response.lower() != 'y':
        print("❌ Cancelled")
        return
    
    # Clear by setting empty cache
    cache._cache = {"tweets": [], "last_updated": None}
    cache._save_cache()
    print("✅ Cache cleared")

def import_tweets(file_path: str):
    """Import tweets from a JSON file"""
    cache = get_tweet_cache()
    
    try:
        with open(file_path) as f:
            tweets = json.load(f)
        
        if not isinstance(tweets, list):
            print("❌ Error: File must contain a JSON array of tweets")
            return 1
        
        print(f"📥 Importing {len(tweets)} tweets...")
        cache.add_tweets(tweets)
        
        stats = cache.get_stats()
        print(f"✅ Import complete. Total cached tweets: {stats['total_tweets']}")
        
    except FileNotFoundError:
        print(f"❌ Error: File not found: {file_path}")
        return 1
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in file: {e}")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0

def preview_cache(count: int = 5):
    """Preview cached tweets"""
    cache = get_tweet_cache()
    tweets = cache.get_tweets(count=count)
    
    if not tweets:
        print("ℹ️  No tweets in cache")
        return
    
    print(f"\n📋 Preview of {len(tweets)} cached tweets:")
    print("=" * 50)
    
    for i, tweet in enumerate(tweets, 1):
        print(f"\n{i}. @{tweet.get('user', 'unknown')}")
        print(f"   {tweet.get('text', '')[:100]}...")
        print(f"   Created: {tweet.get('created_at', 'unknown')}")
        metrics = tweet.get('metrics', {})
        print(f"   Engagement: {metrics.get('like_count', 0)} likes, "
              f"{metrics.get('retweet_count', 0)} RTs, "
              f"{metrics.get('reply_count', 0)} replies")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Manage tweet cache for testing without API calls"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Stats command
    subparsers.add_parser('stats', help='Show cache statistics')
    
    # Clean command
    subparsers.add_parser('clean', help='Remove old tweets (>90 days)')
    
    # Clear command
    subparsers.add_parser('clear', help='Clear entire cache')
    
    # Import command
    import_parser = subparsers.add_parser('import', help='Import tweets from JSON file')
    import_parser.add_argument('file', help='Path to JSON file containing tweets')
    
    # Preview command
    preview_parser = subparsers.add_parser('preview', help='Preview cached tweets')
    preview_parser.add_argument('--count', type=int, default=5, help='Number of tweets to preview')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == 'stats':
        show_stats()
    elif args.command == 'clean':
        clean_cache()
    elif args.command == 'clear':
        clear_cache()
    elif args.command == 'import':
        return import_tweets(args.file)
    elif args.command == 'preview':
        preview_cache(args.count)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())