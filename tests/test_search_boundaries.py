#!/usr/bin/env python3
"""
Test Search Boundary Checkpoint System

Verifies that the boundary tracking system correctly avoids re-fetching tweets.
Tests the logic for determining when to search forward, backward, or both.

Related files:
- src/wdf/search_boundaries.py (Boundary management)
- src/wdf/twitter_api_v2.py (Integration)
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.wdf.search_boundaries import SearchBoundary, SearchBoundaryManager


def test_boundary_logic():
    """Test the core boundary logic for different scenarios."""
    
    # Create temporary directory for test storage
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "boundaries.json"
        manager = SearchBoundaryManager(storage_path=storage_path)
        
        logger.info("=" * 60)
        logger.info("Testing Search Boundary Logic")
        logger.info("=" * 60)
        
        # Test 1: Initial search (no boundaries)
        logger.info("\n1. Initial search for 'federalism'")
        params = manager.get_search_params('federalism', max_results=10)
        assert params['search_type'] == 'initial'
        assert 'since_id' not in params
        assert 'until_id' not in params
        logger.info(f"   ✓ Correctly identified as initial search")
        
        # Test 2: Update boundaries after finding 10 tweets (full results)
        logger.info("\n2. After finding 10 tweets (full results)")
        mock_tweets = [{'id': f'100{i}'} for i in range(10)]
        manager.update_boundaries('federalism', mock_tweets)
        
        # Next search should look for new AND old tweets
        params = manager.get_search_params('federalism', max_results=10)
        assert params['search_type'] == 'new_and_old'
        assert params['since_id'] == '1000'  # Newest tweet
        assert params['until_id'] == '1009'  # Oldest tweet
        logger.info(f"   ✓ Will search for new tweets (since_id=1000)")
        logger.info(f"   ✓ Will search for old tweets (until_id=1009)")
        logger.info(f"   Reason: Got full 10 results, likely more available")
        
        # Test 3: Update boundaries after finding only 3 tweets
        logger.info("\n3. Testing with partial results (3 tweets)")
        manager.reset_keyword('sovereignty')
        mock_tweets = [{'id': f'200{i}'} for i in range(3)]
        manager.update_boundaries('sovereignty', mock_tweets)
        
        # Next search should ONLY look for new tweets
        params = manager.get_search_params('sovereignty', max_results=10)
        assert params['search_type'] == 'new_only'
        assert params['since_id'] == '2000'  # Newest tweet
        assert 'until_id' not in params  # Should NOT search older
        logger.info(f"   ✓ Will search for new tweets only (since_id=2000)")
        logger.info(f"   ✓ Will NOT search for old tweets")
        logger.info(f"   Reason: Only found 3/10, exhausted search window")
        
        # Test 4: Search window expansion
        logger.info("\n4. Testing search window expansion")
        params = manager.get_search_params('federalism', max_results=10, search_window_days=30)
        assert params['search_type'] == 'initial'  # Reset due to window change
        logger.info(f"   ✓ Reset boundaries due to window expansion (7→30 days)")
        
        # Test 5: Persistence
        logger.info("\n5. Testing persistence")
        manager._save_boundaries()
        
        # Create new manager instance
        manager2 = SearchBoundaryManager(storage_path=storage_path)
        assert 'sovereignty' in manager2.boundaries
        assert manager2.boundaries['sovereignty'].results_count == 3
        logger.info(f"   ✓ Boundaries persisted and reloaded correctly")
        
        # Test 6: Savings estimation
        logger.info("\n6. Testing savings estimation")
        savings = manager.estimate_savings()
        logger.info(f"   Keywords tracked: {savings['keywords_tracked']}")
        logger.info(f"   Duplicates avoided: {savings['estimated_duplicates_avoided']}")
        logger.info(f"   Quota saved: {savings['percentage_of_monthly_quota_saved']:.2f}%")
        

def test_real_world_scenario():
    """Simulate a real-world usage pattern over multiple days."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "boundaries.json"
        manager = SearchBoundaryManager(storage_path=storage_path)
        
        logger.info("\n" + "=" * 60)
        logger.info("Simulating Real-World Usage Pattern")
        logger.info("=" * 60)
        
        keywords = [
            ('federalism', 8),     # 8 tweets available
            ('sovereignty', 3),    # Only 3 tweets
            ('constitutional', 15), # More than 10 available
        ]
        
        total_api_calls = 0
        total_tweets_fetched = 0
        duplicate_tweets_avoided = 0
        
        # Day 1: Initial search
        logger.info("\n📅 Day 1: Initial searches")
        for keyword, available in keywords:
            params = manager.get_search_params(keyword, max_results=10)
            
            # Simulate finding tweets
            count = min(available, 10)
            mock_tweets = [{'id': f'{keyword[:3]}_{i:04d}'} for i in range(count)]
            manager.update_boundaries(keyword, mock_tweets)
            
            total_api_calls += 1
            total_tweets_fetched += count
            
            logger.info(f"  {keyword}: Found {count}/10 tweets")
        
        # Day 2: Follow-up searches
        logger.info("\n📅 Day 2: Follow-up searches")
        for keyword, available in keywords:
            params = manager.get_search_params(keyword, max_results=10)
            
            logger.info(f"  {keyword}: Search type = {params['search_type']}")
            
            if params['search_type'] == 'new_only':
                # Simulate 2 new tweets
                new_tweets = [{'id': f'{keyword[:3]}_new_{i:04d}'} for i in range(2)]
                manager.update_boundaries(keyword, new_tweets)
                total_tweets_fetched += 2
                total_api_calls += 1
                duplicate_tweets_avoided += min(available, 10)  # Avoided re-fetching
                
            elif params['search_type'] == 'new_and_old':
                # Simulate finding 2 new and 5 old tweets
                new_tweets = [{'id': f'{keyword[:3]}_new_{i:04d}'} for i in range(2)]
                old_tweets = [{'id': f'{keyword[:3]}_old_{i:04d}'} for i in range(5)]
                all_tweets = new_tweets + old_tweets
                manager.update_boundaries(keyword, all_tweets)
                total_tweets_fetched += 7
                total_api_calls += 2  # Two API calls needed
                duplicate_tweets_avoided += 10  # Avoided re-fetching the original 10
        
        # Summary
        logger.info("\n📊 Two-Day Summary:")
        logger.info(f"  Total API calls: {total_api_calls}")
        logger.info(f"  Total tweets fetched: {total_tweets_fetched}")
        logger.info(f"  Duplicate tweets avoided: {duplicate_tweets_avoided}")
        logger.info(f"  API efficiency gain: {(duplicate_tweets_avoided / (total_tweets_fetched + duplicate_tweets_avoided)) * 100:.1f}%")
        
        # Without boundaries, we would have made:
        without_boundaries_calls = len(keywords) * 2  # All keywords, both days
        without_boundaries_tweets = sum(min(a, 10) for _, a in keywords) * 2  # Same tweets twice
        
        logger.info(f"\n💰 Savings with boundaries:")
        logger.info(f"  API calls: {total_api_calls} vs {without_boundaries_calls} (saved {without_boundaries_calls - total_api_calls})")
        logger.info(f"  Duplicate avoidance: {duplicate_tweets_avoided} tweets not re-fetched")
        logger.info(f"  Monthly quota saved: {(duplicate_tweets_avoided / 10000) * 100:.2f}%")


if __name__ == '__main__':
    test_boundary_logic()
    test_real_world_scenario()