#!/usr/bin/env python3
"""
Search Cache Management Tool
Command-line utility for managing the keyword search cache
"""

import sys
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from search_cache_service import SearchCacheService, optimize_keyword_search


def view_cache_status(service: SearchCacheService):
    """View current cache status and statistics"""
    print("\n🔍 SEARCH CACHE STATUS\n")
    
    stats = service.get_cache_statistics(days=30)
    
    # Overall statistics
    print("📊 Overall Statistics (Last 30 Days)")
    print("=" * 50)
    print(f"  Unique keywords searched: {stats['unique_keywords']}")
    print(f"  Total searches performed: {stats['total_searches']}")
    print(f"  Total tweets cached: {stats['total_tweets_cached']}")
    print(f"  Total API calls used: {stats['total_api_calls_used']}")
    print(f"  Average tweets per search: {stats['avg_tweets_per_search']:.1f}")
    
    # Active cache
    print(f"\n💾 Active Cache")
    print("=" * 50)
    print(f"  Active cache entries: {stats['active_cache_entries']}")
    print(f"  Active cached tweets: {stats['active_cached_tweets']}")
    
    # Efficiency metrics
    if stats['total_searches'] > 0:
        avg_api_per_search = stats['total_api_calls_used'] / stats['total_searches']
        print(f"\n📈 Efficiency Metrics")
        print("=" * 50)
        print(f"  Average API calls per search: {avg_api_per_search:.2f}")
        print(f"  Tweets per API call: {stats['total_tweets_cached'] / max(1, stats['total_api_calls_used']):.1f}")
    
    # Top keywords
    if stats.get('top_keywords'):
        print(f"\n🔝 Top 10 Keywords")
        print("=" * 50)
        for kw in stats['top_keywords']:
            print(f"  {kw['keyword']:<30} {kw['count']:>5} searches")


def view_active_cache(service: SearchCacheService):
    """View active cache entries"""
    print("\n💾 ACTIVE CACHE ENTRIES\n")
    
    try:
        with service.bridge.connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    keyword,
                    searched_at,
                    tweet_count,
                    array_length(tweet_ids, 1) as actual_count,
                    EXTRACT(EPOCH FROM (expires_at - CURRENT_TIMESTAMP))/3600 as hours_until_expiry,
                    episode_id
                FROM keyword_search_cache
                WHERE expires_at > CURRENT_TIMESTAMP
                ORDER BY searched_at DESC
                LIMIT 20
            """)
            
            results = cursor.fetchall()
            
            if not results:
                print("No active cache entries found.")
                return
            
            table_data = []
            for row in results:
                keyword, searched_at, tweet_count, actual_count, hours_left, episode_id = row
                table_data.append([
                    keyword[:30],  # Truncate long keywords
                    searched_at.strftime("%Y-%m-%d %H:%M"),
                    tweet_count,
                    actual_count or 0,
                    f"{hours_left:.1f}h",
                    episode_id or "Global"
                ])
            
            print(f"{'Keyword':<30} {'Searched At':<18} {'Tweets':<8} {'Actual':<8} {'Expires':<10} {'Episode':<10}")
            print("-" * 90)
            for row in table_data:
                print(f"{row[0]:<30} {row[1]:<18} {row[2]:<8} {row[3]:<8} {row[4]:<10} {row[5]:<10}")
            
            print(f"\nShowing {len(results)} most recent cache entries")
            
    except Exception as e:
        print(f"Error: {e}")


def cleanup_cache(service: SearchCacheService, force: bool = False):
    """Clean up expired cache entries"""
    print("\n🧹 CACHE CLEANUP\n")
    
    if not force:
        response = input("This will delete expired cache entries. Continue? [y/N]: ")
        if response.lower() != 'y':
            print("Cleanup cancelled.")
            return
    
    deleted = service.cleanup_expired_cache()
    
    if deleted > 0:
        print(f"✅ Deleted {deleted} expired cache entries")
    else:
        print("No expired entries to clean up")
    
    # Show remaining cache size
    stats = service.get_cache_statistics(days=1)
    print(f"\nRemaining active cache entries: {stats['active_cache_entries']}")


def test_keyword(service: SearchCacheService, keyword: str):
    """Test cache for a specific keyword"""
    print(f"\n🔍 TESTING CACHE FOR KEYWORD: '{keyword}'\n")
    
    # Check cache
    result = service.check_keyword_cache(keyword)
    
    if result['cached']:
        print(f"✅ CACHED")
        print(f"  Searched: {result['searched_at'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Age: {result['hours_old']:.1f} hours")
        print(f"  Tweets: {len(result['tweet_ids'])}")
        print(f"  Tweet IDs: {result['tweet_ids'][:5]}..." if len(result['tweet_ids']) > 5 else f"  Tweet IDs: {result['tweet_ids']}")
    else:
        print(f"❌ NOT CACHED")
        print(f"  This keyword would require an API call")
    
    # Show optimization recommendation
    print(f"\n💡 Optimization Test")
    opt_result = optimize_keyword_search([keyword], max_tweets=100)
    
    for rec in opt_result['recommendations']:
        print(f"  {rec}")


def simulate_search(service: SearchCacheService, keywords: list):
    """Simulate a search to show cache benefits"""
    print(f"\n🔬 SIMULATING SEARCH FOR {len(keywords)} KEYWORDS\n")
    
    # Check optimization
    results = optimize_keyword_search(keywords, max_tweets=100)
    
    print(f"📊 Cache Analysis:")
    print(f"  Keywords to check: {len(keywords)}")
    print(f"  Cached keywords: {len(results['cached_keywords'])}")
    print(f"  Uncached keywords: {len(results['keywords_to_search'])}")
    print(f"  Cache hit rate: {results['cache_stats']['cache_hit_rate']:.1f}%")
    
    print(f"\n💰 API Savings:")
    print(f"  Cached tweets available: {len(results['cached_tweets'])}")
    print(f"  API calls saved: {results['estimated_api_calls_saved']}")
    
    if results['cached_keywords']:
        print(f"\n✅ Cached Keywords:")
        for kw in results['cached_keywords'][:10]:
            print(f"    • {kw}")
    
    if results['keywords_to_search']:
        print(f"\n❌ Uncached Keywords (would need API):")
        for kw in results['keywords_to_search'][:10]:
            print(f"    • {kw}")
    
    print(f"\n💡 Recommendations:")
    for rec in results['recommendations']:
        print(f"  {rec}")


def reset_cache(service: SearchCacheService):
    """Reset/clear all cache entries (dangerous!)"""
    print("\n⚠️  CACHE RESET WARNING\n")
    print("This will DELETE ALL cache entries, including active ones!")
    print("This action cannot be undone.")
    
    response = input("\nType 'DELETE ALL CACHE' to confirm: ")
    if response != 'DELETE ALL CACHE':
        print("Reset cancelled.")
        return
    
    try:
        with service.bridge.connection.cursor() as cursor:
            cursor.execute("DELETE FROM keyword_search_cache")
            deleted = cursor.rowcount
            service.bridge.connection.commit()
            
            print(f"\n✅ Deleted {deleted} cache entries")
            print("Cache has been reset.")
            
    except Exception as e:
        service.bridge.connection.rollback()
        print(f"❌ Failed to reset cache: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Manage keyword search cache",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s status              # View cache statistics
  %(prog)s active              # View active cache entries
  %(prog)s cleanup             # Clean up expired entries
  %(prog)s test federalism     # Test cache for keyword
  %(prog)s simulate -k federalism constitution  # Simulate search
  %(prog)s reset               # Reset entire cache (dangerous!)
        """
    )
    
    parser.add_argument('command', 
                       choices=['status', 'active', 'cleanup', 'test', 'simulate', 'reset'],
                       help='Command to execute')
    
    parser.add_argument('keyword', nargs='?', 
                       help='Keyword to test (for test command)')
    
    parser.add_argument('-k', '--keywords', nargs='+',
                       help='Keywords for simulation')
    
    parser.add_argument('--force', action='store_true',
                       help='Skip confirmation prompts')
    
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Set up logging
    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)
    
    # Initialize service
    service = SearchCacheService()
    
    # Execute command
    try:
        if args.command == 'status':
            view_cache_status(service)
        
        elif args.command == 'active':
            view_active_cache(service)
        
        elif args.command == 'cleanup':
            cleanup_cache(service, force=args.force)
        
        elif args.command == 'test':
            if not args.keyword:
                print("Error: keyword required for test command")
                sys.exit(1)
            test_keyword(service, args.keyword)
        
        elif args.command == 'simulate':
            keywords = args.keywords or ['federalism', 'constitution', 'states rights']
            simulate_search(service, keywords)
        
        elif args.command == 'reset':
            reset_cache(service)
        
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()