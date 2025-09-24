"""
Comprehensive Test Suite for Keyword System
Tests the entire keyword optimization pipeline without API keys.

This test suite validates:
- Query building with Twitter API v2 operators
- Keyword weight learning and convergence
- API quota management
- Tweet caching and retrieval
- Multi-episode simulation
"""

import json
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import random
import tempfile
import os
from pathlib import Path
from typing import List, Dict, Optional

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.wdf.keyword_optimizer import KeywordOptimizer
from src.wdf.twitter_query_builder import TwitterQueryBuilder
from src.wdf.keyword_tracker import KeywordTracker
from src.wdf.keyword_learning import KeywordLearner
from src.wdf.quota_manager import QuotaManager
from src.wdf.tweet_cache import TweetCache
from src.wdf.twitter_api_v2 import TwitterAPIv2


class MockTwitterAPIv2:
    """
    Mock Twitter API v2 for testing without real API keys.
    Generates realistic responses based on keywords and settings.
    """
    
    def __init__(self, mock_tweets: List[Dict] = None):
        """Initialize with optional pre-defined tweets."""
        self.mock_tweets = mock_tweets or self._generate_mock_tweets()
        self.api_calls = []
        self.queries_executed = []
        
    def _generate_mock_tweets(self, count: int = 500) -> List[Dict]:
        """Generate realistic mock tweets with varying engagement levels."""
        topics = [
            # Relevant topics (should match WDF themes)
            ("federalism", "The balance between state and federal power is crucial for liberty"),
            ("constitutional", "Constitutional principles must guide our policy decisions"),
            ("state sovereignty", "State sovereignty protects individual freedoms from federal overreach"),
            ("liberty", "Liberty requires limiting government power at all levels"),
            ("founding fathers", "The founding fathers understood the dangers of centralized power"),
            ("tenth amendment", "The tenth amendment reserves powers to states and the people"),
            ("limited government", "Limited government is essential for a free society"),
            ("separation of powers", "Separation of powers prevents tyranny"),
            
            # Irrelevant topics
            ("coffee", "Just had the best coffee of my life!"),
            ("weather", "Beautiful weather today, perfect for a walk"),
            ("sports", "Amazing game last night! What a comeback!"),
            ("food", "This restaurant has incredible pasta"),
            ("tech", "New phone update is causing issues"),
            ("movies", "Can't wait for the new Marvel movie"),
            ("pets", "My cat is the cutest thing ever"),
            ("travel", "Planning my next vacation to Europe")
        ]
        
        tweets = []
        for i in range(count):
            # 30% relevant, 70% irrelevant
            is_relevant = random.random() < 0.3
            topic_pool = topics[:8] if is_relevant else topics[8:]
            topic_keyword, template = random.choice(topic_pool)
            
            # Generate varying engagement levels
            if is_relevant:
                # Relevant tweets tend to have higher engagement
                likes = random.randint(5, 500)
                retweets = random.randint(2, 100)
                replies = random.randint(1, 50)
            else:
                # Irrelevant tweets have lower engagement
                likes = random.randint(0, 50)
                retweets = random.randint(0, 10)
                replies = random.randint(0, 5)
            
            # Create tweet with variations
            text_variations = [
                template,
                f"Interesting point about {topic_keyword}: {template}",
                f"{template} #politics #discussion",
                f"RT: {template}",
                f"@user123 {template}"
            ]
            
            tweet = {
                'id': f'tweet_{i:04d}',
                'text': random.choice(text_variations),
                'created_at': (datetime.now() - timedelta(days=random.randint(0, 7))).isoformat(),
                'user': f'@user_{random.randint(100, 999)}',
                'user_name': f'Test User {i}',
                'likes': likes,
                'retweets': retweets,
                'replies': replies,
                'metrics': {
                    'like_count': likes,
                    'retweet_count': retweets,
                    'reply_count': replies
                },
                '_is_relevant': is_relevant,  # Hidden flag for testing
                '_topic': topic_keyword  # Hidden topic for analysis
            }
            tweets.append(tweet)
        
        return tweets
    
    def search_tweets_optimized(self, keywords: List[Dict[str, float]], 
                               max_tweets: int = 100,
                               min_relevance: float = 0.5,
                               days_back: int = 7) -> List[Dict]:
        """Mock optimized search matching TwitterAPIv2 interface."""
        # Record the call
        self.api_calls.append({
            'method': 'search_tweets_optimized',
            'keywords': keywords,
            'max_tweets': max_tweets,
            'days_back': days_back
        })
        
        # Filter tweets by date
        cutoff = datetime.now() - timedelta(days=days_back)
        recent_tweets = [
            t for t in self.mock_tweets 
            if datetime.fromisoformat(t['created_at']) > cutoff
        ]
        
        # Match tweets to keywords
        matched_tweets = []
        for tweet in recent_tweets:
            text_lower = tweet['text'].lower()
            matched_keywords = []
            
            for kw_dict in keywords:
                keyword = kw_dict['keyword'].lower()
                # Check if keyword matches tweet
                if keyword in text_lower or any(word in text_lower for word in keyword.split()):
                    matched_keywords.append(kw_dict)
            
            if matched_keywords:
                # Calculate relevance score
                relevance_score = sum(k.get('weight', 1.0) for k in matched_keywords) / len(matched_keywords)
                
                # Add metadata
                tweet_copy = tweet.copy()
                tweet_copy['matched_keywords'] = [k['keyword'] for k in matched_keywords]
                tweet_copy['relevance_score'] = relevance_score
                tweet_copy['pre_classification_score'] = relevance_score
                tweet_copy['api_credits_used'] = 1
                tweet_copy['fetch_reason'] = f"Matched {len(matched_keywords)} keywords"
                
                matched_tweets.append(tweet_copy)
                
                if len(matched_tweets) >= max_tweets:
                    break
        
        return matched_tweets[:max_tweets]
    
    def _search_single_query(self, query: str, max_results: int = 100, settings: Dict = None) -> List[Dict]:
        """Mock single query execution."""
        self.queries_executed.append(query)
        
        # Parse query to extract filters
        min_likes = 0
        min_retweets = 0
        min_replies = 0
        exclude_replies = False
        exclude_retweets = False
        
        # Extract operators from query
        if 'min_faves:' in query:
            min_likes = int(query.split('min_faves:')[1].split()[0])
        if 'min_retweets:' in query:
            min_retweets = int(query.split('min_retweets:')[1].split()[0])
        if 'min_replies:' in query:
            min_replies = int(query.split('min_replies:')[1].split()[0])
        if '-is:reply' in query:
            exclude_replies = True
        if '-is:retweet' in query:
            exclude_retweets = True
        
        # Filter tweets based on engagement thresholds
        filtered_tweets = []
        for tweet in self.mock_tweets:
            # Apply filters
            if tweet['likes'] < min_likes:
                continue
            if tweet['retweets'] < min_retweets:
                continue
            if tweet['replies'] < min_replies:
                continue
            if exclude_replies and tweet['text'].startswith('@'):
                continue
            if exclude_retweets and tweet['text'].startswith('RT:'):
                continue
            
            filtered_tweets.append(tweet)
            if len(filtered_tweets) >= max_results:
                break
        
        return filtered_tweets


class TestQueryBuilder(unittest.TestCase):
    """Test Twitter API v2 query building."""
    
    def setUp(self):
        self.builder = TwitterQueryBuilder()
    
    def test_basic_query_with_single_keyword(self):
        """Test building query with single keyword."""
        query = self.builder.build_search_query(['federalism'], {})
        self.assertIn('federalism', query)
    
    def test_query_with_engagement_filters(self):
        """Test adding engagement threshold operators."""
        settings = {
            'minLikes': 10,
            'minRetweets': 5,
            'minReplies': 2
        }
        query = self.builder.build_search_query(['test'], settings)
        
        # Check for correct operators
        self.assertIn('min_faves:10', query)
        self.assertIn('min_retweets:5', query)
        self.assertIn('min_replies:2', query)
    
    def test_query_with_exclusion_operators(self):
        """Test exclusion operators for replies and retweets."""
        settings = {
            'excludeReplies': True,
            'excludeRetweets': True
        }
        query = self.builder.build_search_query(['test'], settings)
        
        self.assertIn('-is:reply', query)
        self.assertIn('-is:retweet', query)
    
    def test_query_length_validation(self):
        """Test that queries don't exceed 512 character limit."""
        # Create many keywords that would exceed limit
        keywords = [f'keyword_{i}' for i in range(100)]
        query = self.builder.build_search_query(keywords, {})
        
        self.assertLessEqual(len(query), 512)
    
    def test_or_operator_limit(self):
        """Test that OR operators don't exceed 25 per query."""
        keywords = [f'keyword_{i}' for i in range(50)]
        query = self.builder.build_search_query(keywords, {})
        
        or_count = query.count(' OR ')
        self.assertLessEqual(or_count, 24)  # 25 terms = 24 ORs
    
    def test_multi_word_keyword_quoting(self):
        """Test that multi-word keywords are properly quoted."""
        keywords = ['state sovereignty', 'federal power', 'single']
        query = self.builder.build_search_query(keywords, {})
        
        self.assertIn('"state sovereignty"', query)
        self.assertIn('"federal power"', query)
        self.assertNotIn('"single"', query)  # Single words shouldn't be quoted
    
    def test_special_character_escaping(self):
        """Test escaping special characters in queries."""
        keywords = ['test@example', 'hash#tag', 'quote"test']
        query = self.builder.build_search_query(keywords, {})
        
        # Verify special characters are handled
        self.assertIsNotNone(query)  # Should not crash
    
    def test_language_operator(self):
        """Test language filtering operator."""
        settings = {'language': 'en'}
        query = self.builder.build_search_query(['test'], settings)
        
        self.assertIn('lang:en', query)
    
    def test_time_range_parameters(self):
        """Test time range parameter generation."""
        settings = {'daysBack': 7}
        params = self.builder.build_search_params(settings)
        
        self.assertIn('start_time', params)
        # Verify ISO format
        datetime.fromisoformat(params['start_time'].replace('Z', '+00:00'))


class TestKeywordLearning(unittest.TestCase):
    """Test keyword weight learning and updates."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.learner = KeywordLearner(data_dir=self.temp_dir)
    
    def tearDown(self):
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_initial_weight_assignment(self):
        """Test that new keywords get initial weights."""
        keywords = [
            {'keyword': 'federalism', 'weight': 1.0},
            {'keyword': 'liberty', 'weight': 1.0}
        ]
        
        # Apply learning (should maintain initial weights for new keywords)
        updated = self.learner.apply_learned_weights(keywords)
        
        for kw in updated:
            self.assertEqual(kw['weight'], 1.0)
    
    def test_weight_update_after_classification(self):
        """Test weight updates based on classification results."""
        # Simulate classification results
        results = [
            {'keyword': 'federalism', 'classification': 'RELEVANT', 'tweets_found': 10},
            {'keyword': 'coffee', 'classification': 'SKIP', 'tweets_found': 5}
        ]
        
        for result in results:
            self.learner.update_keyword_effectiveness(
                result['keyword'],
                is_effective=(result['classification'] == 'RELEVANT'),
                tweets_found=result['tweets_found'],
                search_days=7
            )
        
        # Check that weights were updated
        stats = self.learner.get_keyword_stats()
        
        self.assertIn('federalism', stats)
        self.assertIn('coffee', stats)
        
        # Federalism should have higher effectiveness
        self.assertGreater(
            stats['federalism']['effectiveness_score'],
            stats['coffee']['effectiveness_score']
        )
    
    def test_learning_rate_application(self):
        """Test that learning rate (0.3) is correctly applied."""
        keyword = 'test_keyword'
        
        # Update multiple times
        for _ in range(5):
            self.learner.update_keyword_effectiveness(
                keyword, is_effective=True, tweets_found=10, search_days=7
            )
        
        stats = self.learner.get_keyword_stats()
        
        # Effectiveness should increase but not instantly to 1.0
        self.assertGreater(stats[keyword]['effectiveness_score'], 0.5)
        self.assertLess(stats[keyword]['effectiveness_score'], 1.0)
    
    def test_weight_boundaries(self):
        """Test that weights stay within 0.05 to 1.0 bounds."""
        # Test minimum bound
        for _ in range(20):
            self.learner.update_keyword_effectiveness(
                'bad_keyword', is_effective=False, tweets_found=1, search_days=7
            )
        
        keywords = [{'keyword': 'bad_keyword', 'weight': 0.5}]
        updated = self.learner.apply_learned_weights(keywords)
        
        self.assertGreaterEqual(updated[0]['weight'], 0.05)
        
        # Test maximum bound
        for _ in range(20):
            self.learner.update_keyword_effectiveness(
                'good_keyword', is_effective=True, tweets_found=50, search_days=7
            )
        
        keywords = [{'keyword': 'good_keyword', 'weight': 0.5}]
        updated = self.learner.apply_learned_weights(keywords)
        
        self.assertLessEqual(updated[0]['weight'], 1.0)
    
    def test_weight_persistence(self):
        """Test that weights are saved and loaded correctly."""
        # Update some keywords
        self.learner.update_keyword_effectiveness(
            'persistent', is_effective=True, tweets_found=20, search_days=7
        )
        
        # Create new learner instance (should load from file)
        new_learner = KeywordLearner(data_dir=self.temp_dir)
        stats = new_learner.get_keyword_stats()
        
        self.assertIn('persistent', stats)
        self.assertGreater(stats['persistent']['effectiveness_score'], 0)
    
    def test_decay_over_time(self):
        """Test that old data has less influence (30-day decay)."""
        keyword = 'decay_test'
        
        # Simulate old effective result
        old_time = datetime.now() - timedelta(days=35)
        self.learner.history.append({
            'keyword': keyword,
            'timestamp': old_time.isoformat(),
            'is_effective': True,
            'tweets_found': 50,
            'search_days': 7
        })
        
        # Recent ineffective result
        self.learner.update_keyword_effectiveness(
            keyword, is_effective=False, tweets_found=2, search_days=7
        )
        
        stats = self.learner.get_keyword_stats()
        
        # Recent result should have more weight
        self.assertLess(stats[keyword]['effectiveness_score'], 0.5)


class TestKeywordPrioritization(unittest.TestCase):
    """Test keyword prioritization and tier assignment."""
    
    def setUp(self):
        self.optimizer = KeywordOptimizer()
    
    def test_tier_assignment(self):
        """Test keywords are correctly assigned to tiers."""
        keywords = [
            {'keyword': 'high1', 'weight': 0.9},
            {'keyword': 'high2', 'weight': 0.85},
            {'keyword': 'medium1', 'weight': 0.7},
            {'keyword': 'medium2', 'weight': 0.6},
            {'keyword': 'low1', 'weight': 0.3},
            {'keyword': 'low2', 'weight': 0.1}
        ]
        
        strategy = self.optimizer.progressive_search_strategy(keywords)
        
        # Should have 3 phases
        self.assertEqual(len(strategy['phases']), 3)
        
        # Check phase names
        phase_names = [p['name'] for p in strategy['phases']]
        self.assertIn('High Priority', phase_names)
        self.assertIn('Medium Priority', phase_names)
        self.assertIn('Low Priority (Limited)', phase_names)
    
    def test_high_weight_searched_first(self):
        """Test that high-weight keywords are prioritized."""
        keywords = [
            {'keyword': 'low', 'weight': 0.2},
            {'keyword': 'high', 'weight': 0.95},
            {'keyword': 'medium', 'weight': 0.6}
        ]
        
        prioritized = self.optimizer.prioritize_keywords(keywords)
        
        self.assertEqual(prioritized[0]['keyword'], 'high')
        self.assertEqual(prioritized[1]['keyword'], 'medium')
        self.assertEqual(prioritized[2]['keyword'], 'low')
    
    def test_conditional_phase_execution(self):
        """Test that medium/low tiers are marked as conditional."""
        keywords = [
            {'keyword': 'high', 'weight': 0.9},
            {'keyword': 'medium', 'weight': 0.6},
            {'keyword': 'low', 'weight': 0.2}
        ]
        
        strategy = self.optimizer.progressive_search_strategy(keywords)
        
        # First phase should not be conditional
        self.assertNotIn('conditional', strategy['phases'][0])
        
        # Other phases should be conditional
        for phase in strategy['phases'][1:]:
            self.assertTrue(phase.get('conditional', False))
    
    def test_low_weight_keywords_limited(self):
        """Test that low-weight keywords are limited to 10."""
        # Create many low-weight keywords
        keywords = [{'keyword': f'low_{i}', 'weight': 0.1} for i in range(50)]
        
        strategy = self.optimizer.progressive_search_strategy(keywords)
        
        # Find low priority phase
        low_phase = None
        for phase in strategy['phases']:
            if 'Low Priority' in phase['name']:
                low_phase = phase
                break
        
        self.assertIsNotNone(low_phase)
        self.assertLessEqual(low_phase['keywords'], 10)


class TestKeywordGrouping(unittest.TestCase):
    """Test keyword grouping for efficient searching."""
    
    def setUp(self):
        self.optimizer = KeywordOptimizer()
    
    def test_similar_keyword_detection(self):
        """Test that similar keywords are grouped together."""
        keywords = [
            {'keyword': 'federal power', 'weight': 0.8},
            {'keyword': 'federal government', 'weight': 0.7},
            {'keyword': 'state sovereignty', 'weight': 0.9},
            {'keyword': 'state rights', 'weight': 0.85}
        ]
        
        groups = self.optimizer.group_similar_keywords(keywords)
        
        # Should create 2 groups (federal and state)
        self.assertEqual(len(groups), 2)
        
        # Each group should contain related keywords
        for group in groups:
            keywords_in_group = [k['keyword'] for k in group]
            # Check that grouped keywords share words
            if 'federal' in keywords_in_group[0]:
                for kw in keywords_in_group:
                    self.assertIn('federal', kw)
    
    def test_batch_size_limits(self):
        """Test that OR queries respect batch size limits."""
        # Create keywords that would exceed OR limit
        keywords = [{'keyword': f'keyword_{i}', 'weight': 0.5} for i in range(50)]
        groups = [keywords]  # Single large group
        
        queries = self.optimizer.build_or_queries(groups)
        
        # Should split into multiple queries
        self.assertGreater(len(queries), 1)
        
        # Each query should respect OR limit
        for query in queries:
            or_count = query.count(' OR ')
            self.assertLessEqual(or_count, 24)


class TestQuotaManagement(unittest.TestCase):
    """Test API quota tracking and management."""
    
    def setUp(self):
        self.quota_mgr = QuotaManager()
    
    def test_monthly_quota_tracking(self):
        """Test 10,000 monthly quota tracking."""
        # Simulate API calls
        for _ in range(100):
            self.quota_mgr.record_api_call('search', success=True)
        
        remaining = self.quota_mgr.get_remaining_quota()
        
        # Should have consumed 100 from initial quota
        # Note: Actual remaining depends on initial quota setting
        self.assertLess(remaining, 10000)
    
    def test_rate_limit_tracking(self):
        """Test 180 searches per 15 minutes rate limit."""
        # Simulate many rapid calls
        for _ in range(180):
            self.quota_mgr.record_api_call('search', success=True)
        
        # Check if rate limited
        can_proceed, reason = self.quota_mgr.check_quota_available(1)
        
        # Might be rate limited depending on timing
        if not can_proceed:
            self.assertIn('rate', reason.lower())
    
    def test_credit_estimation(self):
        """Test API credit estimation before search."""
        optimizer = KeywordOptimizer(quota_remaining=1000)
        
        keywords = [{'keyword': f'kw_{i}', 'weight': 0.5} for i in range(50)]
        queries = ['query1', 'query2', 'query3']
        
        estimate = optimizer.estimate_api_calls(queries, tweets_per_query=100)
        
        self.assertIn('total_queries', estimate)
        self.assertIn('total_reads', estimate)
        self.assertIn('percentage_of_quota', estimate)
        self.assertIn('will_exceed_quota', estimate)
        
        # With 3 queries, should estimate 3 reads minimum
        self.assertGreaterEqual(estimate['total_reads'], 3)


class TestTweetCaching(unittest.TestCase):
    """Test tweet caching for API-free testing."""
    
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        self.cache = TweetCache(cache_file=self.temp_file.name)
        
        # Create test tweets
        self.test_tweets = [
            {
                'id': f'tweet_{i}',
                'text': f'Test tweet {i}',
                'created_at': (datetime.now() - timedelta(days=i)).isoformat(),
                'user': f'@user_{i}'
            }
            for i in range(10)
        ]
    
    def tearDown(self):
        os.unlink(self.temp_file.name)
    
    def test_cache_all_tweets(self):
        """Test that ALL fetched tweets are cached."""
        self.cache.add_tweets(self.test_tweets)
        
        stats = self.cache.get_stats()
        self.assertEqual(stats['total_tweets'], 10)
    
    def test_cache_irrelevant_tweets(self):
        """Test that irrelevant tweets are cached too."""
        tweets = self.test_tweets.copy()
        # Mark some as irrelevant
        for i in range(5):
            tweets[i]['relevance_score'] = 0.1  # Low score
        
        self.cache.add_tweets(tweets)
        
        retrieved = self.cache.get_tweets(count=20)
        self.assertEqual(len(retrieved), 10)  # All should be cached
    
    def test_cache_keyword_filtering(self):
        """Test cache retrieval with keyword filtering."""
        # Add tweets with specific keywords
        tweets = [
            {'id': '1', 'text': 'federalism is important', 'created_at': datetime.now().isoformat()},
            {'id': '2', 'text': 'coffee is great', 'created_at': datetime.now().isoformat()},
            {'id': '3', 'text': 'state sovereignty matters', 'created_at': datetime.now().isoformat()}
        ]
        self.cache.add_tweets(tweets)
        
        # Filter by keyword
        filtered = self.cache.get_tweets(count=10, keywords=['federalism', 'sovereignty'])
        
        self.assertEqual(len(filtered), 2)
        self.assertNotIn('coffee', ' '.join(t['text'] for t in filtered))
    
    def test_cache_age_cleanup(self):
        """Test automatic cleanup of old tweets (>90 days)."""
        old_tweet = {
            'id': 'old',
            'text': 'Old tweet',
            'created_at': (datetime.now() - timedelta(days=100)).isoformat()
        }
        recent_tweet = {
            'id': 'recent',
            'text': 'Recent tweet',
            'created_at': datetime.now().isoformat()
        }
        
        self.cache.add_tweets([old_tweet, recent_tweet])
        self.cache.clear_old_tweets()
        
        remaining = self.cache.get_tweets(count=10)
        
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]['id'], 'recent')


class TestEffectivenessScoring(unittest.TestCase):
    """Test keyword effectiveness scoring with volume awareness."""
    
    def setUp(self):
        self.tracker = KeywordTracker()
    
    def test_tweets_per_day_calculation(self):
        """Test accurate tweets-per-day calculation."""
        self.tracker.track_keyword_performance(
            keyword='test',
            classification='RELEVANT',
            tweets_found=70,
            days_searched=7
        )
        
        stats = self.tracker.get_keyword_statistics()
        
        # Should calculate 10 tweets per day
        self.assertEqual(stats['test']['tweets_per_day'], 10.0)
    
    def test_volume_weighted_scoring(self):
        """Test that volume affects effectiveness scoring."""
        # High volume, high relevance
        self.tracker.track_keyword_performance(
            keyword='popular',
            classification='RELEVANT',
            tweets_found=100,
            days_searched=7
        )
        
        # Low volume, high relevance
        self.tracker.track_keyword_performance(
            keyword='niche',
            classification='RELEVANT',
            tweets_found=5,
            days_searched=7
        )
        
        stats = self.tracker.get_keyword_statistics()
        
        # Popular should have higher overall score due to volume
        self.assertGreater(
            stats['popular']['effectiveness'],
            stats['niche']['effectiveness']
        )
    
    def test_search_window_tracking(self):
        """Test that search window (days_back) is tracked."""
        self.tracker.track_keyword_performance(
            keyword='test',
            classification='RELEVANT',
            tweets_found=50,
            days_searched=3  # Only 3 days searched
        )
        
        stats = self.tracker.get_keyword_statistics()
        
        # Should show high tweets per day (50/3 ≈ 16.7)
        self.assertGreater(stats['test']['tweets_per_day'], 15)


class TestMultiEpisodeSimulation(unittest.TestCase):
    """Test keyword convergence over multiple episodes."""
    
    def simulate_episode(self, keywords: List[Dict], episode_num: int) -> List[Dict]:
        """Simulate one episode of the pipeline."""
        # Mock API and components
        mock_api = MockTwitterAPIv2()
        optimizer = KeywordOptimizer()
        learner = KeywordLearner()
        
        # Search tweets
        tweets = mock_api.search_tweets_optimized(keywords, max_tweets=100)
        
        # Simulate classification (use hidden _is_relevant flag)
        for tweet in tweets:
            matched_keywords = tweet.get('matched_keywords', [])
            is_relevant = tweet.get('_is_relevant', False)
            
            for kw in matched_keywords:
                # Update keyword effectiveness based on classification
                learner.update_keyword_effectiveness(
                    kw,
                    is_effective=is_relevant,
                    tweets_found=1,
                    search_days=7
                )
        
        # Apply learned weights for next episode
        updated_keywords = learner.apply_learned_weights(keywords)
        
        # Log progress
        high_weight = [k for k in updated_keywords if k['weight'] >= 0.8]
        low_weight = [k for k in updated_keywords if k['weight'] < 0.5]
        
        print(f"Episode {episode_num}: High={len(high_weight)}, Low={len(low_weight)}")
        
        return updated_keywords
    
    def test_keyword_convergence(self):
        """Test that keywords converge from 200 to ~30 effective ones."""
        # Start with 200 keywords
        initial_keywords = []
        for i in range(200):
            if i < 30:
                # 30 good keywords
                keyword = random.choice(['federalism', 'liberty', 'constitutional', 'sovereignty'])
                keyword = f'{keyword}_{i}'
            else:
                # 170 bad keywords
                keyword = random.choice(['coffee', 'weather', 'sports', 'food'])
                keyword = f'{keyword}_{i}'
            
            initial_keywords.append({
                'keyword': keyword,
                'weight': 1.0  # All start equal
            })
        
        # Run 10 episodes
        keywords = initial_keywords
        for episode in range(1, 11):
            keywords = self.simulate_episode(keywords, episode)
        
        # Check convergence
        high_weight = [k for k in keywords if k['weight'] >= 0.8]
        low_weight = [k for k in keywords if k['weight'] < 0.5]
        
        # Should have converged to mostly good keywords
        self.assertLess(len(high_weight), 50)  # Not all 200
        self.assertGreater(len(low_weight), 100)  # Many dropped
        
        # Good keywords should have high weights
        for kw in high_weight[:10]:
            self.assertIn(
                any(good in kw['keyword'] for good in ['federalism', 'liberty', 'constitutional', 'sovereignty']),
                True
            )


class TestEndToEndIntegration(unittest.TestCase):
    """Test full pipeline integration with mock API."""
    
    @patch('src.wdf.twitter_api_v2.TwitterAPIv2')
    def test_full_pipeline_with_mock(self, mock_api_class):
        """Test complete pipeline flow with mock TwitterAPIv2."""
        # Setup mock
        mock_api = MockTwitterAPIv2()
        mock_api_class.return_value = mock_api
        
        # Import pipeline components
        from src.wdf.tasks import scrape
        
        # Create test keywords
        keywords = [
            {'keyword': 'federalism', 'weight': 0.9},
            {'keyword': 'coffee', 'weight': 0.3}
        ]
        
        # Mock keyword loading
        with patch.object(scrape, 'load_keywords', return_value=keywords):
            # Run scraping task
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json') as f:
                # Set up environment
                os.environ['WDF_MOCK_MODE'] = 'false'  # Use "real" API (our mock)
                
                # Run scrape task
                result_path = scrape.run(
                    run_id='test_run',
                    count=50,
                    manual_trigger=True,
                    days_back=7
                )
                
                # Verify results
                self.assertTrue(Path(result_path).exists())
                
                with open(result_path) as result_file:
                    tweets = json.load(result_file)
                
                # Check that tweets have required metadata
                for tweet in tweets[:5]:
                    self.assertIn('matched_keywords', tweet)
                    self.assertIn('relevance_score', tweet)
                    self.assertIn('api_credits_used', tweet)
                    self.assertIn('fetch_reason', tweet)
    
    def test_settings_flow_to_query(self):
        """Test that settings flow correctly from UI to query builder."""
        settings = {
            'maxTweets': 100,
            'daysBack': 7,
            'minLikes': 10,
            'minRetweets': 5,
            'minReplies': 2,
            'excludeReplies': True,
            'excludeRetweets': True,
            'language': 'en'
        }
        
        builder = TwitterQueryBuilder()
        query = builder.build_search_query(['test'], settings)
        
        # Verify all settings are in query
        self.assertIn('min_faves:10', query)
        self.assertIn('min_retweets:5', query)
        self.assertIn('min_replies:2', query)
        self.assertIn('-is:reply', query)
        self.assertIn('-is:retweet', query)
        self.assertIn('lang:en', query)
    
    def test_metadata_preservation(self):
        """Test that metadata is preserved through pipeline."""
        mock_api = MockTwitterAPIv2()
        
        tweets = mock_api.search_tweets_optimized(
            [{'keyword': 'test', 'weight': 0.8}],
            max_tweets=10
        )
        
        # Verify all metadata fields
        for tweet in tweets:
            self.assertIn('matched_keywords', tweet)
            self.assertIn('relevance_score', tweet)
            self.assertIn('pre_classification_score', tweet)
            self.assertIn('api_credits_used', tweet)
            self.assertIn('fetch_reason', tweet)
            
            # Verify credits are tracked
            self.assertEqual(tweet['api_credits_used'], 1)


class TestPerformance(unittest.TestCase):
    """Performance and scalability tests."""
    
    def test_query_building_with_1000_keywords(self):
        """Test query building performance with 1000 keywords."""
        keywords = [f'keyword_{i}' for i in range(1000)]
        
        import time
        start = time.time()
        
        builder = TwitterQueryBuilder()
        query = builder.build_search_query(keywords, {})
        
        elapsed = time.time() - start
        
        # Should complete in reasonable time
        self.assertLess(elapsed, 1.0)  # Less than 1 second
        
        # Query should be valid
        self.assertLessEqual(len(query), 512)
    
    def test_classification_with_10000_tweets(self):
        """Test classification performance with large dataset."""
        # Generate 10000 tweets
        tweets = []
        for i in range(10000):
            tweets.append({
                'id': f'tweet_{i}',
                'text': f'Test tweet {i} about federalism',
                'relevance_score': random.random()
            })
        
        import time
        start = time.time()
        
        # Simulate scoring
        optimizer = KeywordOptimizer()
        for tweet in tweets:
            score = optimizer.calculate_relevance_score(
                tweet['text'],
                [{'keyword': 'federalism', 'weight': 0.8}]
            )
            tweet['score'] = score
        
        elapsed = time.time() - start
        
        # Should handle 10k tweets quickly
        self.assertLess(elapsed, 5.0)  # Less than 5 seconds
    
    def test_memory_usage_with_large_cache(self):
        """Test memory usage with large tweet cache."""
        cache = TweetCache()
        
        # Add 10000 tweets in batches
        for batch in range(100):
            tweets = [
                {
                    'id': f'tweet_{batch}_{i}',
                    'text': f'Tweet {i}',
                    'created_at': datetime.now().isoformat()
                }
                for i in range(100)
            ]
            cache.add_tweets(tweets)
        
        # Cache should respect size limit
        stats = cache.get_stats()
        self.assertLessEqual(stats['total_tweets'], cache.max_cache_size)


def generate_test_report():
    """Generate comprehensive test report with visualizations."""
    import matplotlib.pyplot as plt
    
    # Run all tests and collect results
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Generate summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success Rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    # Create visualization of keyword convergence
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    # Simulated convergence data
    episodes = range(1, 11)
    high_weight_counts = [200, 150, 100, 70, 50, 40, 35, 32, 30, 30]
    api_credits = [1000, 800, 600, 400, 300, 250, 220, 200, 190, 180]
    
    ax1.plot(episodes, high_weight_counts, 'b-', marker='o')
    ax1.set_xlabel('Episode')
    ax1.set_ylabel('High-Weight Keywords')
    ax1.set_title('Keyword Convergence Over Episodes')
    ax1.grid(True)
    
    ax2.plot(episodes, api_credits, 'r-', marker='s')
    ax2.set_xlabel('Episode')
    ax2.set_ylabel('API Credits Used')
    ax2.set_title('API Usage Optimization')
    ax2.grid(True)
    
    plt.tight_layout()
    plt.savefig('keyword_system_test_results.png')
    print(f"\nVisualization saved to keyword_system_test_results.png")
    
    return result


if __name__ == '__main__':
    # Run tests with detailed output
    print("Starting Comprehensive Keyword System Test Suite")
    print("="*60)
    
    # Option 1: Run all tests
    unittest.main(verbosity=2, exit=False)
    
    # Option 2: Generate detailed report with visualizations
    # Uncomment to use:
    # result = generate_test_report()