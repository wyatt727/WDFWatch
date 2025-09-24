#!/usr/bin/env python3
"""
Test script to verify the force refresh functionality for search cache.
This tests that the force_refresh parameter properly bypasses the cache.
"""

import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from search_cache_service import SearchCacheService, optimize_keyword_search


def test_force_refresh():
    """Test that force_refresh bypasses the cache"""
    print("🧪 TESTING FORCE REFRESH FUNCTIONALITY\n")
    print("=" * 60)
    
    # Initialize service
    service = SearchCacheService()
    
    # Test keywords
    test_keywords = ["constitutional", "federal power", "state autonomy"]
    
    # Step 1: Save some test data to cache
    print("\n💾 Step 1: Populating cache with test data...")
    for keyword in test_keywords:
        success = service.save_search_results(
            keyword=keyword,
            tweet_ids=[f"cached_{keyword}_{i}" for i in range(3)],
            search_params={'days_back': 7, 'max_results': 100},
            api_calls_used=1
        )
        if success:
            print(f"  ✅ Cached '{keyword}' with 3 test tweets")
    
    # Step 2: Check cache normally (should use cache)
    print("\n🔍 Step 2: Checking cache with force_refresh=False...")
    normal_results = optimize_keyword_search(
        keywords=test_keywords,
        max_tweets=100,
        force_refresh=False
    )
    
    print(f"  Cached keywords: {normal_results['cached_keywords']}")
    print(f"  Keywords to search: {normal_results['keywords_to_search']}")
    print(f"  Skip all API calls: {normal_results['skip_all_api_calls']}")
    
    # Verify cache was used
    assert len(normal_results['cached_keywords']) == len(test_keywords), \
        "Expected all keywords to be cached"
    assert len(normal_results['keywords_to_search']) == 0, \
        "Expected no keywords to need searching"
    print("  ✅ Cache is being used as expected")
    
    # Step 3: Check cache with force_refresh=True (should bypass cache)
    print("\n🔄 Step 3: Checking cache with force_refresh=True...")
    forced_results = optimize_keyword_search(
        keywords=test_keywords,
        max_tweets=100,
        force_refresh=True
    )
    
    print(f"  Cached keywords: {forced_results['cached_keywords']}")
    print(f"  Keywords to search: {forced_results['keywords_to_search']}")
    print(f"  Skip all API calls: {forced_results['skip_all_api_calls']}")
    
    # Verify cache was bypassed
    assert len(forced_results['cached_keywords']) == 0, \
        "Expected no keywords to be cached when force_refresh=True"
    assert len(forced_results['keywords_to_search']) == len(test_keywords), \
        "Expected all keywords to need searching when force_refresh=True"
    assert forced_results['skip_all_api_calls'] == False, \
        "Expected API calls to NOT be skipped when force_refresh=True"
    print("  ✅ Cache is being bypassed as expected")
    
    # Step 4: Verify recommendations
    print("\n💡 Step 4: Checking recommendations...")
    print("  Normal mode recommendations:")
    for rec in normal_results['recommendations'][:2]:
        print(f"    • {rec}")
    
    print("\n  Force refresh mode recommendations:")
    for rec in forced_results['recommendations'][:2]:
        print(f"    • {rec}")
    
    # Step 5: Clean up test data
    print("\n🧹 Step 5: Cleaning up test data...")
    # The test data will be automatically cleaned up after 4 days
    # or can be manually cleaned with: service.cleanup_expired_cache()
    print("  Test data will auto-expire in 4 days")
    
    print("\n" + "=" * 60)
    print("✅ FORCE REFRESH TEST COMPLETE")
    print("\nThe force refresh functionality is working correctly!")
    print("• force_refresh=False uses cached results (saves API calls)")
    print("• force_refresh=True bypasses cache (fetches fresh tweets)")
    

if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        test_force_refresh()
        
        print("\n🎉 All tests passed!")
        print("\nHow to use from the Web UI:")
        print("1. Go to Episode Details page")
        print("2. Find the 'Tweet Discovery' section")
        print("3. Check 'Force refresh (ignore 4-day cache and fetch fresh tweets)'")
        print("4. Click 'Run' to fetch fresh tweets ignoring cache")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)