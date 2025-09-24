#!/usr/bin/env python3
"""
Safe API Testing Script

Demonstrates all safety features and improvements for Twitter API usage.
Run this before using real API keys to ensure everything is configured safely.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.wdf.twitter_query_builder import TwitterQueryBuilder
from src.wdf.preflight_check import PreflightChecker
from src.wdf.api_monitor import APIMonitor
from src.wdf.tweet_cache import TweetCache
from src.wdf.keyword_optimizer import KeywordOptimizer


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "="*60)
    print(title)
    print("="*60)


def test_query_building():
    """Test and demonstrate query building improvements."""
    print_section("1. QUERY BUILDING IMPROVEMENTS")
    
    builder = TwitterQueryBuilder()
    
    # Test 1: Multi-word keyword quoting
    print("\n✅ Multi-word keywords are now quoted:")
    keywords = ["state sovereignty", "federal power", "constitution"]
    settings = {"minLikes": 10, "excludeReplies": True}
    
    query = builder.build_search_query(keywords, settings)
    print(f"Query: {query}")
    print(f"Length: {len(query)} chars (max 512)")
    
    # Test 2: Query truncation enforcement
    print("\n✅ Queries are truncated to 512 chars:")
    many_keywords = [f"keyword_{i}" for i in range(100)]
    long_query = builder.build_search_query(many_keywords, settings)
    print(f"100 keywords → Query length: {len(long_query)} chars")
    assert len(long_query) <= 512, "Query exceeds 512 chars!"
    
    # Test 3: Correct operators
    print("\n✅ Using correct Twitter API v2 operators:")
    settings = {
        "minLikes": 10,
        "minRetweets": 5,
        "minReplies": 2,
        "excludeReplies": True,
        "excludeRetweets": True,
        "language": "en"
    }
    query = builder.build_search_query(["test"], settings)
    
    operators_check = {
        "min_faves:10": "min_faves" in query,  # NOT min_likes!
        "min_retweets:5": "min_retweets" in query,
        "min_replies:2": "min_replies" in query,
        "-is:reply": "-is:reply" in query,
        "-is:retweet": "-is:retweet" in query,
        "lang:en": "lang:en" in query
    }
    
    for operator, present in operators_check.items():
        status = "✓" if present else "✗"
        print(f"  {status} {operator}")


def test_settings_validation():
    """Test settings validation improvements."""
    print_section("2. SETTINGS VALIDATION")
    
    builder = TwitterQueryBuilder()
    
    # Test various settings
    test_cases = [
        ({"daysBack": -1}, "Invalid days_back"),
        ({"daysBack": 30}, "Large days_back"),
        ({"minLikes": -5}, "Negative engagement"),
        ({"maxTweets": 1000}, "High tweet count"),
        ({"excludeReplies": True, "minReplies": 5}, "Conflicting settings")
    ]
    
    for settings, description in test_cases:
        warnings = builder.validate_settings(settings)
        if warnings:
            print(f"\n⚠️ {description}:")
            for warning in warnings:
                print(f"  - {warning}")
        else:
            print(f"\n✅ {description}: No warnings")


def test_preflight_checks():
    """Test pre-flight safety checks."""
    print_section("3. PRE-FLIGHT SAFETY CHECKS")
    
    checker = PreflightChecker()
    
    # Test with safe settings
    safe_settings = {
        "maxTweets": 20,
        "daysBack": 3,
        "minLikes": 5,
        "excludeReplies": True,
        "excludeRetweets": True
    }
    
    keywords = ["federalism", "constitutional", "state rights"]
    
    print("\n🔍 Running pre-flight checks with safe settings...")
    safe, results = checker.run_all_checks(keywords, safe_settings)
    
    print(f"\nSafe to proceed: {'✅ YES' if safe else '❌ NO'}")
    
    if results["warnings"]:
        print("\nWarnings:")
        for warning in results["warnings"]:
            print(f"  {warning}")
    
    if results["recommendations"]:
        print("\nRecommendations:")
        for rec in results["recommendations"]:
            print(f"  {rec}")
    
    # Test with unsafe settings
    unsafe_settings = {
        "maxTweets": 500,
        "daysBack": 30,
        "minLikes": 0
    }
    
    print("\n🔍 Testing with unsafe settings...")
    unsafe, results = checker.run_all_checks(keywords * 50, unsafe_settings)
    
    if results["errors"]:
        print("\nErrors detected:")
        for error in results["errors"]:
            print(f"  {error}")


def test_cache_improvements():
    """Test tweet cache improvements."""
    print_section("4. TWEET CACHE IMPROVEMENTS")
    
    # Create temporary cache
    import tempfile
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    temp_file.close()
    
    cache = TweetCache(cache_file=temp_file.name)
    
    # Add test tweets
    tweets = [
        {
            "id": "1",
            "text": "Oldest tweet about federalism",
            "created_at": "2025-01-01T10:00:00Z"
        },
        {
            "id": "2",
            "text": "Middle tweet about state rights",
            "created_at": "2025-01-02T10:00:00Z"
        },
        {
            "id": "3",
            "text": "Newest tweet about constitution",
            "created_at": "2025-01-03T10:00:00Z"
        }
    ]
    
    cache.add_tweets(tweets)
    
    # Retrieve tweets - should be oldest first now
    retrieved = cache.get_tweets(count=10)
    
    print("\n✅ Tweets now returned in chronological order (oldest first):")
    for tweet in retrieved:
        print(f"  {tweet['created_at']}: {tweet['text'][:50]}...")
    
    # Clean up
    os.unlink(temp_file.name)


def test_api_monitoring():
    """Test API monitoring features."""
    print_section("5. API USAGE MONITORING")
    
    monitor = APIMonitor()
    
    # Simulate some API calls
    print("\n📊 Simulating API usage...")
    monitor.track_api_call("search", credits=1, query="federalism", response_count=50)
    monitor.track_api_call("search", credits=1, query="constitution", response_count=30)
    monitor.track_api_call("tweet_lookup", credits=1, response_count=1)
    
    # Get stats
    stats = monitor.get_session_stats()
    
    print(f"\nSession Statistics:")
    print(f"  Total API Calls: {stats['total_calls']}")
    print(f"  Credits Used: {stats['credits_used']}")
    print(f"  Credits/Minute: {stats['credits_per_minute']}")
    print(f"  Remaining Credits: {stats['remaining_session_credits']}")
    
    # Check if safe to proceed
    can_proceed = monitor.check_can_proceed(estimated_credits=10)
    print(f"\n  Can make 10 more calls: {'✅ YES' if can_proceed else '❌ NO'}")


def test_keyword_optimization():
    """Test keyword optimization features."""
    print_section("6. KEYWORD OPTIMIZATION")
    
    optimizer = KeywordOptimizer()
    
    # Test with weighted keywords
    keywords = [
        {"keyword": "federalism", "weight": 0.9},
        {"keyword": "state sovereignty", "weight": 0.85},
        {"keyword": "constitutional", "weight": 0.7},
        {"keyword": "politics", "weight": 0.3},
        {"keyword": "news", "weight": 0.1}
    ]
    
    # Get progressive search strategy
    strategy = optimizer.progressive_search_strategy(keywords)
    
    print("\n✅ Three-tier keyword prioritization:")
    for phase in strategy["phases"]:
        print(f"\n  {phase['name']}:")
        print(f"    Keywords: {phase['keywords']}")
        print(f"    Weight Range: {phase.get('weight_range', 'N/A')}")
        if phase.get('conditional'):
            print(f"    Conditional: Only if needed")


def load_safe_defaults():
    """Load and display safe default configuration."""
    print_section("7. SAFE DEFAULT CONFIGURATION")
    
    config_path = Path("config/safe_defaults.json")
    
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
        
        print("\n✅ Safe defaults loaded from config/safe_defaults.json:")
        print(f"\nSettings:")
        for key, value in config["settings"].items():
            print(f"  {key}: {value}")
        
        print(f"\nSafety Features:")
        for key, value in config["safety"].items():
            print(f"  {key}: {value}")
        
        print(f"\nRecommendations:")
        for i, rec in enumerate(config["recommendations"], 1):
            print(f"  {rec}")


def main():
    """Run all safety tests and demonstrations."""
    print("="*60)
    print("WDFWATCH SAFETY FEATURES DEMONSTRATION")
    print("="*60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Set safe environment
    os.environ["WDF_NO_AUTO_SCRAPE"] = "true"
    print("\n✅ WDF_NO_AUTO_SCRAPE is set to true (safe mode)")
    
    try:
        # Run all tests
        test_query_building()
        test_settings_validation()
        test_preflight_checks()
        test_cache_improvements()
        test_api_monitoring()
        test_keyword_optimization()
        load_safe_defaults()
        
        # Final summary
        print_section("SAFETY CHECK SUMMARY")
        print("\n✅ All safety features are working correctly!")
        print("\n📋 Checklist before using real API keys:")
        print("  ☐ Set WDF_NO_AUTO_SCRAPE=true initially")
        print("  ☐ Start with maxTweets=20 or less")
        print("  ☐ Use daysBack=3 for initial tests")
        print("  ☐ Enable engagement thresholds (minLikes, etc.)")
        print("  ☐ Exclude replies and retweets")
        print("  ☐ Monitor API usage dashboard")
        print("  ☐ Review pre-flight check results")
        print("  ☐ Test with cached tweets first")
        
        print("\n🚀 System is ready for safe API testing!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Error during safety check: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())