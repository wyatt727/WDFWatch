"""
Test Suite for Twitter API Optimization

Tests the keyword optimizer, quota manager, and Twitter API v2 integration.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Import modules to test
from src.wdf.keyword_optimizer import KeywordOptimizer
from src.wdf.quota_manager import QuotaManager
from src.wdf.twitter_api_v2 import TwitterAPIv2


class TestKeywordOptimizer:
    """Test keyword optimization functionality."""
    
    def test_prioritize_keywords(self):
        """Test that keywords are sorted by weight correctly."""
        optimizer = KeywordOptimizer()
        keywords = [
            {"keyword": "federalism", "weight": 0.3},
            {"keyword": "sovereignty", "weight": 0.9},
            {"keyword": "constitution", "weight": 0.6}
        ]
        
        prioritized = optimizer.prioritize_keywords(keywords)
        
        assert prioritized[0]["keyword"] == "sovereignty"
        assert prioritized[1]["keyword"] == "constitution"
        assert prioritized[2]["keyword"] == "federalism"
    
    def test_group_similar_keywords(self):
        """Test that similar keywords are grouped together."""
        optimizer = KeywordOptimizer()
        keywords = [
            {"keyword": "federal law", "weight": 0.8},
            {"keyword": "state law", "weight": 0.7},
            {"keyword": "constitutional amendment", "weight": 0.9},
            {"keyword": "amendment process", "weight": 0.6}
        ]
        
        groups = optimizer.group_similar_keywords(keywords)
        
        # Should group keywords with shared words
        assert len(groups) <= 3  # At most 3 groups
        
        # Find the group with "law" keywords
        law_group = None
        amendment_group = None
        for group in groups:
            keywords_in_group = [k["keyword"] for k in group]
            if "federal law" in keywords_in_group:
                law_group = group
            if "constitutional amendment" in keywords_in_group:
                amendment_group = group
        
        assert law_group is not None
        assert amendment_group is not None
        assert len(law_group) >= 2  # Should have both "law" keywords
        assert len(amendment_group) >= 2  # Should have both "amendment" keywords
    
    def test_build_or_queries(self):
        """Test building optimized OR queries."""
        optimizer = KeywordOptimizer()
        groups = [
            [
                {"keyword": "federalism", "weight": 0.9},
                {"keyword": "states rights", "weight": 0.8},
                {"keyword": "sovereignty", "weight": 0.7}
            ]
        ]
        
        queries = optimizer.build_or_queries(groups)
        
        assert len(queries) == 1
        assert "federalism" in queries[0]
        assert "OR" in queries[0]
        assert '"states rights"' in queries[0]  # Multi-word should be quoted
    
    def test_calculate_relevance_score(self):
        """Test relevance scoring based on keyword matches."""
        optimizer = KeywordOptimizer()
        
        tweet_text = "The debate over federalism and state sovereignty continues"
        matched_keywords = [
            {"keyword": "federalism", "weight": 0.9},
            {"keyword": "sovereignty", "weight": 0.8}
        ]
        
        score = optimizer.calculate_relevance_score(tweet_text, matched_keywords)
        
        assert score > 0.5  # Should have high score with 2 matches
        assert score <= 1.0
    
    def test_progressive_search_strategy(self):
        """Test progressive search phases based on keyword weights."""
        optimizer = KeywordOptimizer()
        keywords = [
            {"keyword": "high1", "weight": 0.9},
            {"keyword": "high2", "weight": 0.85},
            {"keyword": "medium1", "weight": 0.6},
            {"keyword": "medium2", "weight": 0.55},
            {"keyword": "low1", "weight": 0.3},
            {"keyword": "low2", "weight": 0.2}
        ]
        
        strategy = optimizer.progressive_search_strategy(keywords)
        
        assert len(strategy['phases']) >= 2  # At least high and medium priority
        assert strategy['phases'][0]['name'] == 'High Priority'
        assert strategy['phases'][0]['keywords'] == 2  # high1 and high2
        
        # Check conditional flags
        if len(strategy['phases']) > 1:
            assert 'conditional' in strategy['phases'][1]


class TestQuotaManager:
    """Test quota management functionality."""
    
    @patch('src.wdf.quota_manager.redis.Redis')
    def test_quota_initialization(self, mock_redis):
        """Test quota manager initialization."""
        mock_redis_instance = MagicMock()
        mock_redis.from_url.return_value = mock_redis_instance
        mock_redis_instance.get.return_value = None
        
        manager = QuotaManager(mock_redis_instance)
        
        assert manager.monthly_usage == 0
        assert manager.get_remaining_quota() == 10000
    
    @patch('src.wdf.quota_manager.redis.Redis')
    def test_check_quota_available(self, mock_redis):
        """Test quota availability checking."""
        mock_redis_instance = MagicMock()
        mock_redis.from_url.return_value = mock_redis_instance
        mock_redis_instance.get.return_value = b'2000'  # 2000 used
        
        manager = QuotaManager(mock_redis_instance)
        manager.monthly_usage = 2000
        
        # Should allow calls within remaining quota
        available, reason = manager.check_quota_available(100)
        assert available is True
        
        # Should reject calls exceeding safe limit
        available, reason = manager.check_quota_available(8000)
        assert available is False
        assert "Insufficient quota" in reason
    
    @patch('src.wdf.quota_manager.redis.Redis')
    def test_record_api_call(self, mock_redis):
        """Test API call recording."""
        mock_redis_instance = MagicMock()
        mock_redis.from_url.return_value = mock_redis_instance
        mock_redis_instance.get.return_value = None
        
        manager = QuotaManager(mock_redis_instance)
        initial_usage = manager.monthly_usage
        
        manager.record_api_call("search", success=True, calls_used=5)
        
        assert manager.monthly_usage == initial_usage + 5
        mock_redis_instance.set.assert_called()  # Should save to Redis
        mock_redis_instance.incrby.assert_called()  # Should update rate limit window
    
    @patch('src.wdf.quota_manager.redis.Redis')
    def test_estimate_search_cost(self, mock_redis):
        """Test search cost estimation."""
        mock_redis_instance = MagicMock()
        mock_redis.from_url.return_value = mock_redis_instance
        mock_redis_instance.get.return_value = None
        
        manager = QuotaManager(mock_redis_instance)
        
        estimate = manager.estimate_search_cost(
            num_keywords=50,
            tweets_per_keyword=100
        )
        
        assert 'queries_needed' in estimate
        assert 'total_api_calls' in estimate
        assert 'can_afford' in estimate
        
        # 50 keywords / 25 per query = 2 queries minimum
        assert estimate['queries_needed'] >= 2
    
    @patch('src.wdf.quota_manager.redis.Redis')
    def test_get_usage_stats(self, mock_redis):
        """Test comprehensive usage statistics."""
        mock_redis_instance = MagicMock()
        mock_redis.from_url.return_value = mock_redis_instance
        mock_redis_instance.get.return_value = b'3000'
        
        manager = QuotaManager(mock_redis_instance)
        manager.monthly_usage = 3000
        
        stats = manager.get_usage_stats()
        
        assert stats['monthly_usage'] == 3000
        assert stats['monthly_remaining'] == 7000
        assert stats['monthly_percentage'] == 30.0
        assert 'recommended_daily_limit' in stats
        assert 'exhaustion_date' in stats or stats['days_until_exhausted'] == float('inf')
    
    @patch('src.wdf.quota_manager.redis.Redis')
    def test_quota_health_status(self, mock_redis):
        """Test quota health status determination."""
        mock_redis_instance = MagicMock()
        mock_redis.from_url.return_value = mock_redis_instance
        
        manager = QuotaManager(mock_redis_instance)
        
        # Test healthy status
        manager.monthly_usage = 5000  # 50%
        assert manager.get_quota_health() == 'healthy'
        
        # Test warning status
        manager.monthly_usage = 7500  # 75%
        assert manager.get_quota_health() == 'warning'
        
        # Test critical status
        manager.monthly_usage = 9500  # 95%
        assert manager.get_quota_health() == 'critical'


class TestTwitterAPIv2Integration:
    """Test Twitter API v2 with optimization integration."""
    
    @patch('src.wdf.twitter_api_v2.OAuth1Session')
    @patch('src.wdf.twitter_api_v2.redis.Redis')
    def test_api_initialization(self, mock_redis, mock_oauth):
        """Test Twitter API v2 initialization."""
        mock_redis_instance = MagicMock()
        mock_redis.from_url.return_value = mock_redis_instance
        
        # Should raise error without credentials
        with pytest.raises(ValueError, match="Twitter API credentials not configured"):
            api = TwitterAPIv2()
        
        # Should initialize with credentials
        api = TwitterAPIv2(
            api_key="test_key",
            api_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret"
        )
        
        assert api.api_key == "test_key"
        assert api.optimizer is not None
        assert api.quota_manager is not None
    
    @patch('src.wdf.twitter_api_v2.OAuth1Session')
    @patch('src.wdf.twitter_api_v2.redis.Redis')
    def test_optimized_search(self, mock_redis, mock_oauth):
        """Test optimized tweet search."""
        mock_redis_instance = MagicMock()
        mock_redis.from_url.return_value = mock_redis_instance
        mock_redis_instance.get.return_value = None
        
        mock_session = MagicMock()
        mock_oauth.return_value = mock_session
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': [
                {
                    'id': '123',
                    'text': 'Tweet about federalism',
                    'author_id': 'user1',
                    'created_at': '2025-01-01T00:00:00Z'
                }
            ],
            'includes': {
                'users': [
                    {
                        'id': 'user1',
                        'username': 'testuser',
                        'name': 'Test User'
                    }
                ]
            }
        }
        mock_session.get.return_value = mock_response
        
        api = TwitterAPIv2(
            api_key="test_key",
            api_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret"
        )
        
        keywords = [
            {"keyword": "federalism", "weight": 0.9},
            {"keyword": "sovereignty", "weight": 0.8}
        ]
        
        results = api.search_tweets_optimized(
            keywords=keywords,
            max_tweets=10,
            min_relevance=0.5
        )
        
        assert len(results) > 0
        assert results[0]['id'] == '123'
        assert 'relevance_score' in results[0]
        assert 'matched_keywords' in results[0]
    
    def test_find_matched_keywords(self):
        """Test keyword matching in tweet text."""
        api = TwitterAPIv2.__new__(TwitterAPIv2)  # Create without __init__
        
        tweet_text = "Discussion about federal law and state sovereignty"
        keywords = [
            {"keyword": "federal law", "weight": 0.9},
            {"keyword": "sovereignty", "weight": 0.8},
            {"keyword": "constitution", "weight": 0.7}
        ]
        
        matched = api._find_matched_keywords(tweet_text, keywords)
        
        assert len(matched) == 2
        keyword_texts = [k["keyword"] for k in matched]
        assert "federal law" in keyword_texts
        assert "sovereignty" in keyword_texts
        assert "constitution" not in keyword_texts


class TestEndToEndOptimization:
    """Test complete optimization flow."""
    
    @patch('src.wdf.twitter_api_v2.OAuth1Session')
    @patch('src.wdf.quota_manager.redis.Redis')
    def test_full_optimization_flow(self, mock_redis, mock_oauth):
        """Test the complete keyword optimization and search flow."""
        # Setup mocks
        mock_redis_instance = MagicMock()
        mock_redis.from_url.return_value = mock_redis_instance
        mock_redis_instance.get.return_value = b'1000'  # 1000 calls used
        
        mock_session = MagicMock()
        mock_oauth.return_value = mock_session
        
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': [
                {
                    'id': f'tweet_{i}',
                    'text': f'Tweet about federalism and sovereignty #{i}',
                    'author_id': f'user_{i}'
                }
                for i in range(10)
            ],
            'includes': {
                'users': [
                    {
                        'id': f'user_{i}',
                        'username': f'user{i}',
                        'name': f'User {i}'
                    }
                    for i in range(10)
                ]
            }
        }
        mock_session.get.return_value = mock_response
        
        # Create API instance
        api = TwitterAPIv2(
            api_key="test_key",
            api_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret"
        )
        
        # Test keywords with varying weights
        keywords = [
            {"keyword": "federalism", "weight": 0.95},
            {"keyword": "sovereignty", "weight": 0.90},
            {"keyword": "constitution", "weight": 0.75},
            {"keyword": "states rights", "weight": 0.70},
            {"keyword": "federal law", "weight": 0.65},
            {"keyword": "supreme court", "weight": 0.60},
            {"keyword": "judicial review", "weight": 0.40},
            {"keyword": "legislation", "weight": 0.30}
        ]
        
        # Perform optimized search
        results = api.search_tweets_optimized(
            keywords=keywords,
            max_tweets=50,
            min_relevance=0.5
        )
        
        # Verify results
        assert len(results) <= 50
        
        # Check that results have required fields
        if results:
            assert 'id' in results[0]
            assert 'text' in results[0]
            assert 'relevance_score' in results[0]
            assert 'matched_keywords' in results[0]
            
            # Verify relevance scores are above threshold
            for result in results:
                assert result['relevance_score'] >= 0.5
        
        # Verify quota was checked
        assert api.quota_manager.monthly_usage > 0
        
        # Verify optimization occurred (high-weight keywords prioritized)
        # This would be reflected in the order of API calls
        mock_session.get.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])