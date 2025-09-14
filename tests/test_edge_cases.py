"""
Edge Case Tests for Keyword System
Tests unusual scenarios and boundary conditions.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.wdf.keyword_optimizer import KeywordOptimizer
from src.wdf.twitter_query_builder import TwitterQueryBuilder
from src.wdf.keyword_learning import KeywordLearner
from src.wdf.tweet_cache import TweetCache


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""
    
    def test_zero_keywords(self):
        """Test system behavior with 0 keywords."""
        optimizer = KeywordOptimizer()
        
        # Empty keyword list
        strategy = optimizer.progressive_search_strategy([])
        
        self.assertEqual(len(strategy['phases']), 0)
        self.assertEqual(strategy['total_keywords'], 0)
        self.assertEqual(strategy['estimated_api_calls'], 0)
    
    def test_500_plus_keywords_stress(self):
        """Test system with 500+ keywords."""
        optimizer = KeywordOptimizer()
        
        # Create 500 keywords
        keywords = [
            {'keyword': f'keyword_{i}', 'weight': 0.5 + (i % 10) * 0.05}
            for i in range(500)
        ]
        
        strategy = optimizer.progressive_search_strategy(keywords)
        
        # Should handle large keyword set
        self.assertGreater(len(strategy['phases']), 0)
        
        # Should create multiple queries
        total_queries = sum(len(p.get('queries', [])) for p in strategy['phases'])
        self.assertGreater(total_queries, 10)  # Need many queries for 500 keywords
    
    def test_identical_weights(self):
        """Test keywords with all identical weights."""
        optimizer = KeywordOptimizer()
        
        # All keywords have same weight
        keywords = [
            {'keyword': f'keyword_{i}', 'weight': 0.5}
            for i in range(50)
        ]
        
        prioritized = optimizer.prioritize_keywords(keywords)
        
        # Order should be stable but all weights equal
        for kw in prioritized:
            self.assertEqual(kw['weight'], 0.5)
    
    def test_tweet_matching_multiple_keywords(self):
        """Test tweets that match multiple keywords."""
        optimizer = KeywordOptimizer()
        
        tweet_text = "Federal power and state sovereignty are key constitutional principles"
        keywords = [
            {'keyword': 'federal power', 'weight': 0.8},
            {'keyword': 'state sovereignty', 'weight': 0.9},
            {'keyword': 'constitutional', 'weight': 0.7}
        ]
        
        # All three keywords should match
        score = optimizer.calculate_relevance_score(tweet_text, keywords)
        
        # Score should be high (average of matched weights)
        self.assertGreater(score, 0.7)
    
    def test_no_matching_tweets(self):
        """Test when no tweets match any keywords."""
        from tests.test_keyword_system import MockTwitterAPIv2
        
        # Create mock with no relevant tweets
        mock_api = MockTwitterAPIv2(mock_tweets=[
            {
                'id': f'tweet_{i}',
                'text': 'Random unrelated content',
                'created_at': datetime.now().isoformat(),
                'user': f'@user_{i}',
                'likes': 0,
                'retweets': 0,
                'replies': 0
            }
            for i in range(10)
        ])
        
        # Search with keywords that won't match
        keywords = [{'keyword': 'nonexistent_keyword', 'weight': 1.0}]
        results = mock_api.search_tweets_optimized(keywords, max_tweets=100)
        
        # Should return empty or very few results
        self.assertEqual(len(results), 0)
    
    def test_all_irrelevant_tweets(self):
        """Test when all scraped tweets are classified as irrelevant."""
        learner = KeywordLearner()
        
        # Update keyword with only negative results
        for _ in range(10):
            learner.update_keyword_effectiveness(
                'bad_keyword',
                is_effective=False,
                tweets_found=10,
                search_days=7
            )
        
        # Apply to keywords
        keywords = [{'keyword': 'bad_keyword', 'weight': 0.8}]
        updated = learner.apply_learned_weights(keywords)
        
        # Weight should decrease significantly
        self.assertLess(updated[0]['weight'], 0.5)
    
    def test_extreme_engagement_thresholds(self):
        """Test with very high engagement thresholds."""
        builder = TwitterQueryBuilder()
        
        # Extremely high thresholds
        settings = {
            'minLikes': 10000,
            'minRetweets': 5000,
            'minReplies': 1000
        }
        
        query = builder.build_search_query(['test'], settings)
        
        # Should include all operators even with extreme values
        self.assertIn('min_faves:10000', query)
        self.assertIn('min_retweets:5000', query)
        self.assertIn('min_replies:1000', query)
    
    def test_malformed_keyword_format(self):
        """Test handling of malformed keyword data."""
        optimizer = KeywordOptimizer()
        
        # Mix of valid and invalid keyword formats
        keywords = [
            {'keyword': 'valid', 'weight': 0.5},
            {'keyword': '', 'weight': 0.8},  # Empty keyword
            {'keyword': 'no_weight'},  # Missing weight
            {'keyword': 'negative', 'weight': -0.5},  # Invalid weight
            {'keyword': 'too_high', 'weight': 2.0},  # Weight > 1
        ]
        
        # Should handle gracefully
        prioritized = optimizer.prioritize_keywords(keywords)
        
        # Empty keyword should be filtered or handled
        for kw in prioritized:
            self.assertNotEqual(kw['keyword'], '')
    
    def test_unicode_and_emoji_keywords(self):
        """Test keywords with unicode and emoji characters."""
        builder = TwitterQueryBuilder()
        
        keywords = [
            '政治',  # Chinese
            'política',  # Spanish with accent
            '🇺🇸 politics',  # With emoji
            'федерализм'  # Cyrillic
        ]
        
        query = builder.build_search_query(keywords, {})
        
        # Should handle unicode properly
        self.assertIsNotNone(query)
        # Multi-word with emoji should be quoted
        self.assertIn('"🇺🇸 politics"', query)
    
    def test_cache_with_duplicate_tweets(self):
        """Test cache handles duplicate tweet IDs correctly."""
        cache = TweetCache()
        
        # Add same tweet multiple times
        tweet = {
            'id': 'duplicate_123',
            'text': 'Test tweet',
            'created_at': datetime.now().isoformat()
        }
        
        cache.add_tweets([tweet])
        cache.add_tweets([tweet])  # Add again
        cache.add_tweets([tweet])  # And again
        
        stats = cache.get_stats()
        
        # Should only have one copy
        self.assertEqual(stats['total_tweets'], 1)
    
    def test_query_with_all_filters_combined(self):
        """Test query with ALL possible filters applied."""
        builder = TwitterQueryBuilder()
        
        settings = {
            'minLikes': 10,
            'minRetweets': 5,
            'minReplies': 2,
            'excludeReplies': True,
            'excludeRetweets': True,
            'language': 'en',
            'daysBack': 3
        }
        
        keywords = ['federalism', 'state power', 'constitutional']
        query = builder.build_search_query(keywords, settings)
        
        # Verify all components present
        self.assertIn('min_faves:10', query)
        self.assertIn('min_retweets:5', query)
        self.assertIn('min_replies:2', query)
        self.assertIn('-is:reply', query)
        self.assertIn('-is:retweet', query)
        self.assertIn('lang:en', query)
        
        # Keywords should be connected with OR
        self.assertIn(' OR ', query)
    
    def test_keyword_with_special_twitter_syntax(self):
        """Test keywords that contain Twitter search operators."""
        builder = TwitterQueryBuilder()
        
        # Keywords that look like operators
        keywords = [
            'from:user',  # Looks like from operator
            'to:someone',  # Looks like to operator
            'OR test',  # Contains OR
            'min_faves'  # Contains operator name
        ]
        
        query = builder.build_search_query(keywords, {})
        
        # Should escape or quote properly
        self.assertIn('"from:user"', query)
        self.assertIn('"to:someone"', query)
    
    def test_learning_with_zero_tweets_found(self):
        """Test keyword learning when no tweets are found."""
        learner = KeywordLearner()
        
        # Update with zero tweets
        learner.update_keyword_effectiveness(
            'rare_keyword',
            is_effective=False,
            tweets_found=0,
            search_days=7
        )
        
        stats = learner.get_keyword_stats()
        
        # Should handle zero tweets gracefully
        self.assertIn('rare_keyword', stats)
        self.assertEqual(stats['rare_keyword']['tweets_per_day'], 0)
    
    def test_very_long_keyword(self):
        """Test handling of extremely long keywords."""
        builder = TwitterQueryBuilder()
        
        # Create a very long keyword
        long_keyword = ' '.join(['word'] * 50)  # 50 words
        
        query = builder.build_search_query([long_keyword], {})
        
        # Query should still respect 512 char limit
        self.assertLessEqual(len(query), 512)
    
    def test_days_back_zero(self):
        """Test with days_back set to 0 (today only)."""
        from tests.test_keyword_system import MockTwitterAPIv2
        
        mock_api = MockTwitterAPIv2()
        
        # Search with 0 days back
        results = mock_api.search_tweets_optimized(
            [{'keyword': 'test', 'weight': 1.0}],
            max_tweets=100,
            days_back=0
        )
        
        # Should only return today's tweets (if any)
        for tweet in results:
            tweet_date = datetime.fromisoformat(tweet['created_at'])
            self.assertEqual(tweet_date.date(), datetime.now().date())
    
    def test_weight_update_with_nan_values(self):
        """Test handling of NaN or infinite values in calculations."""
        optimizer = KeywordOptimizer()
        
        # Force edge case with empty matched keywords
        score = optimizer.calculate_relevance_score('test tweet', [])
        
        # Should return 0, not NaN
        self.assertEqual(score, 0.0)
        self.assertFalse(float('inf') == score)
        self.assertFalse(float('-inf') == score)


class TestNetworkErrors(unittest.TestCase):
    """Test network error handling and recovery."""
    
    @patch('requests.Session')
    def test_network_timeout(self, mock_session):
        """Test handling of network timeouts."""
        from src.wdf.twitter_api_v2 import TwitterAPIv2
        
        # Setup mock to raise timeout
        mock_response = Mock()
        mock_response.status_code = 408  # Request Timeout
        mock_session.return_value.get.side_effect = TimeoutError("Connection timed out")
        
        api = TwitterAPIv2(
            api_key='test',
            api_secret='test',
            access_token='test',
            access_token_secret='test'
        )
        
        # Should handle timeout gracefully
        results = api._search_single_query('test query')
        self.assertEqual(results, [])
    
    @patch('requests.Session')
    def test_rate_limit_recovery(self, mock_session):
        """Test rate limit error recovery."""
        from src.wdf.twitter_api_v2 import TwitterAPIv2
        
        # Setup mock for rate limit response
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {'x-rate-limit-reset': str(int(datetime.now().timestamp()) + 1)}
        mock_session.return_value.get.return_value = mock_response
        
        api = TwitterAPIv2(
            api_key='test',
            api_secret='test',
            access_token='test',
            access_token_secret='test'
        )
        
        # Should wait and retry (but we'll just test it doesn't crash)
        with patch('time.sleep'):  # Don't actually sleep in test
            results = api._search_single_query('test query')
        
        # Should return empty on persistent rate limit
        self.assertEqual(results, [])
    
    @patch('requests.Session')
    def test_invalid_json_response(self, mock_session):
        """Test handling of invalid JSON in API response."""
        from src.wdf.twitter_api_v2 import TwitterAPIv2
        
        # Setup mock with invalid JSON
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
        mock_response.text = "Invalid JSON response"
        mock_session.return_value.get.return_value = mock_response
        
        api = TwitterAPIv2(
            api_key='test',
            api_secret='test',
            access_token='test',
            access_token_secret='test'
        )
        
        # Should handle JSON error gracefully
        results = api._search_single_query('test query')
        self.assertEqual(results, [])
    
    @patch('requests.Session')
    def test_api_authentication_failure(self, mock_session):
        """Test handling of authentication failures."""
        from src.wdf.twitter_api_v2 import TwitterAPIv2
        
        # Setup mock for auth failure
        mock_response = Mock()
        mock_response.status_code = 401  # Unauthorized
        mock_response.text = "Invalid or expired token"
        mock_session.return_value.get.return_value = mock_response
        
        api = TwitterAPIv2(
            api_key='invalid',
            api_secret='invalid',
            access_token='invalid',
            access_token_secret='invalid'
        )
        
        # Should handle auth failure gracefully
        results = api._search_single_query('test query')
        self.assertEqual(results, [])


class TestDataIntegrity(unittest.TestCase):
    """Test data integrity and persistence."""
    
    def test_concurrent_cache_access(self):
        """Test cache handles concurrent access correctly."""
        import threading
        
        cache = TweetCache()
        
        def add_tweets(thread_id):
            tweets = [
                {
                    'id': f'tweet_{thread_id}_{i}',
                    'text': f'Thread {thread_id} tweet {i}',
                    'created_at': datetime.now().isoformat()
                }
                for i in range(10)
            ]
            cache.add_tweets(tweets)
        
        # Start multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=add_tweets, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Should have all tweets
        stats = cache.get_stats()
        self.assertEqual(stats['total_tweets'], 50)
    
    def test_keyword_file_corruption_recovery(self):
        """Test recovery from corrupted keyword files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            # Write corrupted JSON
            f.write("{'invalid': json, 'syntax': }")
            temp_file = f.name
        
        try:
            # Try to load corrupted file
            from src.wdf.tasks import scrape
            
            with patch('src.wdf.tasks.scrape.KEYWORDS_PATH', Path(temp_file)):
                keywords = scrape.load_keywords()
            
            # Should return empty list on corruption
            self.assertEqual(keywords, [])
        finally:
            import os
            os.unlink(temp_file)
    
    def test_partial_pipeline_failure_recovery(self):
        """Test recovery when pipeline fails mid-execution."""
        # Simulate partial results
        partial_tweets = [
            {'id': '1', 'text': 'Tweet 1', 'classification': 'RELEVANT'},
            {'id': '2', 'text': 'Tweet 2'}  # Missing classification
        ]
        
        tracker = KeywordTracker()
        
        # Should handle partial data
        for tweet in partial_tweets:
            if 'classification' in tweet:
                tracker.track_keyword_performance(
                    'test',
                    tweet['classification'],
                    tweets_found=1,
                    days_searched=7
                )
        
        stats = tracker.get_keyword_statistics()
        
        # Should have processed what it could
        self.assertIn('test', stats)


if __name__ == '__main__':
    unittest.main(verbosity=2)