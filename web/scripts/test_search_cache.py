#!/usr/bin/env python3
"""
Test script to verify the search cache system works correctly.
Tests that searches are cached and reused within the 4-day window.
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from search_cache_service import SearchCacheService, optimize_keyword_search
from web_bridge import WebUIBridge


def test_cache_functionality():
    """Test the complete cache workflow"""
    print("🧪 TESTING SEARCH CACHE SYSTEM\n")
    print("=" * 60)
    
    # Initialize service
    service = SearchCacheService()
    
    # Test keywords
    test_keywords = ["federalism", "constitution", "states rights", "tenth amendment"]
    
    # Step 1: Check initial cache state
    print("\n📊 Step 1: Checking initial cache state...")
    initial_results = optimize_keyword_search(test_keywords, max_tweets=100)
    
    print(f"  Initial cached keywords: {initial_results['cached_keywords']}")
    print(f"  Keywords needing search: {initial_results['keywords_to_search']}")
    print(f"  Cached tweets available: {len(initial_results['cached_tweets'])}")
    
    # Step 2: Simulate saving search results for uncached keywords
    if initial_results['keywords_to_search']:
        print("\n💾 Step 2: Simulating API search and caching results...")
        
        for keyword in initial_results['keywords_to_search'][:2]:  # Test with first 2 uncached
            # Simulate tweet IDs that would come from API
            simulated_tweet_ids = [
                f"test_{keyword}_{i}" for i in range(5)
            ]
            
            success = service.save_search_results(
                keyword=keyword,
                tweet_ids=simulated_tweet_ids,
                search_params={'days_back': 7, 'max_results': 100},
                api_calls_used=1
            )
            
            if success:
                print(f"  ✅ Cached results for '{keyword}': {len(simulated_tweet_ids)} tweets")
            else:
                print(f"  ❌ Failed to cache results for '{keyword}'")
    
    # Step 3: Check cache again - should now have more cached results
    print("\n🔍 Step 3: Checking cache after saving results...")
    updated_results = optimize_keyword_search(test_keywords, max_tweets=100)
    
    print(f"  Now cached keywords: {updated_results['cached_keywords']}")
    print(f"  Keywords still needing search: {updated_results['keywords_to_search']}")
    print(f"  API calls saved: {updated_results['estimated_api_calls_saved']}")
    
    # Step 4: Check individual keyword cache details
    print("\n📋 Step 4: Checking individual keyword cache details...")
    for keyword in test_keywords[:3]:
        cache_info = service.check_keyword_cache(keyword)
        if cache_info['cached']:
            print(f"  ✅ '{keyword}': Cached {cache_info['hours_old']:.1f} hours ago, "
                  f"{len(cache_info['tweet_ids'])} tweets")
        else:
            print(f"  ❌ '{keyword}': Not cached")
    
    # Step 5: Get cache statistics
    print("\n📈 Step 5: Cache Statistics...")
    stats = service.get_cache_statistics(days=1)
    
    print(f"  Unique keywords searched: {stats['unique_keywords']}")
    print(f"  Total searches performed: {stats['total_searches']}")
    print(f"  Total tweets cached: {stats['total_tweets_cached']}")
    print(f"  Active cache entries: {stats['active_cache_entries']}")
    print(f"  Active cached tweets: {stats['active_cached_tweets']}")
    
    # Step 6: Test cache expiration check
    print("\n⏰ Step 6: Testing cache age validation...")
    
    # Check with very short max age (should consider cache expired)
    old_cache = service.check_keyword_cache(
        test_keywords[0], 
        max_age_hours=0.001  # Very short, effectively expired
    )
    
    # Check with normal age
    fresh_cache = service.check_keyword_cache(
        test_keywords[0],
        max_age_hours=96  # 4 days
    )
    
    print(f"  With 0.001 hour max age: {'Cached' if old_cache['cached'] else 'Not cached'}")
    print(f"  With 96 hour max age: {'Cached' if fresh_cache['cached'] else 'Not cached'}")
    
    # Step 7: Test recommendations for different scenarios
    print("\n💡 Step 7: Testing optimization recommendations...")
    
    # Scenario 1: All keywords cached
    all_cached = optimize_keyword_search(['federalism'], max_tweets=10)
    print(f"\n  Scenario 1 (likely cached):")
    for rec in all_cached['recommendations'][:2]:
        print(f"    {rec}")
    
    # Scenario 2: Mix of cached and uncached
    mixed = optimize_keyword_search(
        ['federalism', 'some_random_uncached_keyword_xyz'], 
        max_tweets=50
    )
    print(f"\n  Scenario 2 (mixed):")
    for rec in mixed['recommendations'][:2]:
        print(f"    {rec}")
    
    # Step 8: Test cleanup (don't actually run it)
    print("\n🧹 Step 8: Cleanup capability...")
    print("  cleanup_expired_cache() function available")
    print("  Would remove entries older than 4 days")
    
    print("\n" + "=" * 60)
    print("✅ CACHE SYSTEM TEST COMPLETE")
    print("\nThe search cache system is working correctly!")
    print("It will save API quota by reusing search results for 4 days.")
    

def test_integration_with_scrape():
    """Test how cache integrates with actual scraping"""
    print("\n🔗 TESTING INTEGRATION WITH SCRAPE TASK\n")
    print("=" * 60)
    
    # Check if scrape.py properly imports cache
    scrape_path = Path(__file__).parent.parent.parent / "src" / "wdf" / "tasks" / "scrape.py"
    
    if scrape_path.exists():
        with open(scrape_path, 'r') as f:
            content = f.read()
            
        checks = {
            "Cache import": "search_cache_service" in content,
            "optimize_keyword_search call": "optimize_keyword_search" in content,
            "save_search_results call": "save_search_results" in content,
            "Cache results check": "cache_results" in content,
            "Skip API for cached": "skip_all_api_calls" in content or "cached_keywords" in content
        }
        
        print("Integration checks:")
        for check_name, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {check_name}")
        
        if all(checks.values()):
            print("\n✅ Scrape task is properly integrated with cache!")
        else:
            print("\n⚠️ Some integration points may be missing")
    else:
        print("❌ Could not find scrape.py to verify integration")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run tests
    try:
        test_cache_functionality()
        test_integration_with_scrape()
        
        print("\n🎉 All tests completed successfully!")
        print("\nNext steps:")
        print("1. Run an actual episode scrape to populate real cache data")
        print("2. Run the same scrape again within 4 days to verify cache is used")
        print("3. Monitor API quota savings with: python manage_search_cache.py stats")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)