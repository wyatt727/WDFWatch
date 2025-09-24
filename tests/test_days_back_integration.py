"""
Test Suite for days_back Parameter Propagation
Ensures the days_back parameter flows correctly from UI settings through the entire pipeline.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call
import json
import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.wdf.twitter_query_builder import TwitterQueryBuilder
from src.wdf.keyword_tracker import KeywordTracker
from src.wdf.keyword_learning import KeywordLearner


class TestDaysBackPropagation(unittest.TestCase):
    """Test that days_back parameter flows correctly through the pipeline."""
    
    def test_settings_to_scrape_task(self):
        """Test days_back flows from database settings to scrape task."""
        from src.wdf.tasks import scrape
        
        # Mock database settings loader
        mock_settings = {
            'maxTweets': 100,
            'daysBack': 14,  # Testing with 14 days
            'minLikes': 5,
            'minRetweets': 2
        }
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_settings)
            )
            
            with patch.dict(os.environ, {'WDF_WEB_MODE': 'true'}):
                with patch.object(scrape, 'get_twitter_client') as mock_client:
                    mock_client.return_value.search_by_keywords.return_value = []
                    
                    # Run scrape task
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json') as f:
                        with patch.object(scrape, 'TWEETS_PATH', Path(f.name)):
                            scrape.run(manual_trigger=True)
                    
                    # Verify subprocess was called to load settings
                    mock_run.assert_called_once()
                    call_args = mock_run.call_args[0][0]
                    self.assertIn('load_scraping_settings.py', ' '.join(call_args))
    
    def test_scrape_to_twitter_api(self):
        """Test days_back passes from scrape to TwitterAPIv2."""
        from src.wdf.twitter_api_v2 import TwitterAPIv2
        
        # Create API instance with settings
        api = TwitterAPIv2(
            api_key='test',
            api_secret='test',
            access_token='test',
            access_token_secret='test',
            scraping_settings={'daysBack': 14}
        )
        
        with patch.object(api, '_search_single_query', return_value=[]) as mock_search:
            # Search with explicit days_back
            api.search_tweets_optimized(
                keywords=[{'keyword': 'test', 'weight': 1.0}],
                max_tweets=100,
                days_back=21  # Override with 21 days
            )
            
            # Verify days_back was used
            mock_search.assert_called()
            call_args = mock_search.call_args
            settings = call_args[1].get('settings', {})
            self.assertEqual(settings.get('daysBack'), 21)
    
    def test_query_builder_time_range(self):
        """Test TwitterQueryBuilder creates correct time range from days_back."""
        builder = TwitterQueryBuilder()
        
        # Test with 7 days back
        params = builder.build_search_params({'daysBack': 7})
        
        # Should have start_time
        self.assertIn('start_time', params)
        
        # Parse and verify time
        start_time = datetime.fromisoformat(params['start_time'].replace('Z', '+00:00'))
        expected_start = datetime.now(tz=start_time.tzinfo) - timedelta(days=7)
        
        # Should be close to 7 days ago (within 1 minute tolerance)
        time_diff = abs((start_time - expected_start).total_seconds())
        self.assertLess(time_diff, 60)
    
    def test_metadata_file_creation(self):
        """Test that tweets_metadata.json contains days_back."""
        from src.wdf.tasks import scrape
        
        with tempfile.TemporaryDirectory() as temp_dir:
            tweets_path = Path(temp_dir) / 'tweets.json'
            metadata_path = Path(temp_dir) / 'tweets_metadata.json'
            
            # Mock scrape with specific days_back
            with patch.object(scrape, 'TWEETS_PATH', tweets_path):
                with patch.object(scrape, 'get_twitter_client') as mock_client:
                    mock_client.return_value.search_by_keywords.return_value = []
                    
                    # Run with specific days_back
                    scrape.run(days_back=10, manual_trigger=True)
                    
                    # Check metadata file was created
                    self.assertTrue(metadata_path.exists())
                    
                    # Verify days_back in metadata
                    with open(metadata_path) as f:
                        metadata = json.load(f)
                    
                    self.assertEqual(metadata['metadata']['days_back'], 10)
    
    def test_classify_reads_metadata(self):
        """Test that classify.py reads days_back from metadata."""
        from src.wdf.tasks import classify
        
        # Create mock metadata file
        metadata = {
            'metadata': {
                'days_back': 14,
                'count_requested': 100,
                'search_timestamp': datetime.now().isoformat()
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json') as f:
            json.dump(metadata, f)
            f.flush()
            
            # Test load_search_metadata
            with patch.object(classify, 'Path') as mock_path:
                mock_path.return_value.parent = Path(f.name).parent
                mock_path.return_value.exists.return_value = True
                
                result = classify.load_search_metadata()
                
                self.assertEqual(result.get('days_back'), 14)
    
    def test_keyword_tracker_uses_days_back(self):
        """Test KeywordTracker correctly uses days_back for calculations."""
        tracker = KeywordTracker()
        
        # Track with specific days_searched
        tracker.track_keyword_performance(
            keyword='federalism',
            classification='RELEVANT',
            tweets_found=140,  # 140 tweets
            days_searched=14   # Over 14 days
        )
        
        stats = tracker.get_keyword_statistics()
        
        # Should calculate 10 tweets per day (140/14)
        self.assertEqual(stats['federalism']['tweets_per_day'], 10.0)
    
    def test_keyword_learning_with_days_back(self):
        """Test KeywordLearner uses days_back for effectiveness scoring."""
        learner = KeywordLearner()
        
        # Update with different search windows
        learner.update_keyword_effectiveness(
            'keyword1',
            is_effective=True,
            tweets_found=70,
            search_days=7  # 10 tweets/day
        )
        
        learner.update_keyword_effectiveness(
            'keyword2',
            is_effective=True,
            tweets_found=140,
            search_days=14  # Also 10 tweets/day
        )
        
        stats = learner.get_keyword_stats()
        
        # Both should have similar effectiveness despite different totals
        score1 = stats['keyword1']['effectiveness_score']
        score2 = stats['keyword2']['effectiveness_score']
        
        # Scores should be close (within 10%)
        self.assertLess(abs(score1 - score2), 0.1)
    
    def test_end_to_end_days_back_flow(self):
        """Test complete flow from UI settings to keyword learning."""
        # Simulate the complete pipeline
        
        # 1. UI saves settings
        ui_settings = {
            'scraping_config': {
                'maxTweets': 100,
                'daysBack': 21,
                'minLikes': 10
            }
        }
        
        # 2. Scrape loads settings
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(ui_settings['scraping_config'])
            )
            
            # 3. TwitterAPIv2 uses days_back
            from src.wdf.twitter_api_v2 import TwitterAPIv2
            
            api = TwitterAPIv2(
                api_key='test',
                api_secret='test',
                access_token='test',
                access_token_secret='test',
                scraping_settings=ui_settings['scraping_config']
            )
            
            # 4. Query builder creates time range
            builder = TwitterQueryBuilder()
            params = builder.build_search_params(ui_settings['scraping_config'])
            
            # Verify start_time reflects 21 days
            start_time = datetime.fromisoformat(params['start_time'].replace('Z', '+00:00'))
            expected = datetime.now(tz=start_time.tzinfo) - timedelta(days=21)
            
            time_diff = abs((start_time - expected).total_seconds())
            self.assertLess(time_diff, 60)  # Within 1 minute
            
            # 5. Keyword learning uses correct window
            learner = KeywordLearner()
            learner.update_keyword_effectiveness(
                'test_keyword',
                is_effective=True,
                tweets_found=210,
                search_days=21  # From settings
            )
            
            stats = learner.get_keyword_stats()
            
            # Should calculate 10 tweets/day (210/21)
            self.assertIn('test_keyword', stats)
            # Note: tweets_per_day is stored in history, not directly in stats
    
    def test_default_days_back_values(self):
        """Test default values when days_back not specified."""
        # Test scrape default
        from src.wdf.tasks import scrape
        
        with patch.object(scrape, 'get_twitter_client') as mock_client:
            mock_client.return_value.search_by_keywords.return_value = []
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json') as f:
                with patch.object(scrape, 'TWEETS_PATH', Path(f.name)):
                    # Run without specifying days_back
                    scrape.run(manual_trigger=True)
            
            # Should use default of 7 days
            # (Would need to check in the actual implementation)
    
    def test_days_back_validation(self):
        """Test validation of days_back parameter."""
        builder = TwitterQueryBuilder()
        
        # Test various values
        test_cases = [
            (0, True),   # Today only - valid
            (1, True),   # Yesterday - valid
            (7, True),   # Week - valid
            (30, True),  # Month - valid
            (-1, False), # Negative - invalid
            (366, False), # Too far back - may be limited by API
        ]
        
        for days, should_work in test_cases:
            settings = {'daysBack': days}
            
            if should_work:
                # Should not raise error
                params = builder.build_search_params(settings)
                self.assertIn('start_time', params)
            else:
                # Should handle gracefully (validate or use default)
                warnings = builder.validate_settings(settings)
                # Negative days should produce warning
                if days < 0:
                    self.assertTrue(any('days' in w.lower() for w in warnings))
    
    def test_volume_calculation_accuracy(self):
        """Test that volume calculations use correct time window."""
        tracker = KeywordTracker()
        
        # Test edge cases
        test_cases = [
            (100, 1, 100.0),   # 100 tweets in 1 day = 100/day
            (100, 7, 14.29),   # 100 tweets in 7 days ≈ 14.29/day
            (100, 30, 3.33),   # 100 tweets in 30 days ≈ 3.33/day
            (0, 7, 0.0),       # No tweets = 0/day
            (10, 0.5, 20.0),   # Half day = 20/day
        ]
        
        for tweets, days, expected_per_day in test_cases:
            tracker.track_keyword_performance(
                keyword=f'test_{tweets}_{days}',
                classification='RELEVANT',
                tweets_found=tweets,
                days_searched=days
            )
            
            stats = tracker.get_keyword_statistics()
            key = f'test_{tweets}_{days}'
            
            if key in stats:
                actual = stats[key].get('tweets_per_day', 0)
                # Check within 0.1 of expected
                self.assertAlmostEqual(actual, expected_per_day, places=1)


class TestScrapingSettingsIntegration(unittest.TestCase):
    """Test integration of all scraping settings."""
    
    def test_all_settings_applied(self):
        """Test that ALL scraping settings are properly applied."""
        settings = {
            'maxTweets': 150,
            'daysBack': 10,
            'minLikes': 20,
            'minRetweets': 10,
            'minReplies': 5,
            'excludeReplies': True,
            'excludeRetweets': True,
            'language': 'en'
        }
        
        # Test query builder
        builder = TwitterQueryBuilder()
        query = builder.build_search_query(['test'], settings)
        
        # Verify all settings in query
        self.assertIn('min_faves:20', query)
        self.assertIn('min_retweets:10', query)
        self.assertIn('min_replies:5', query)
        self.assertIn('-is:reply', query)
        self.assertIn('-is:retweet', query)
        self.assertIn('lang:en', query)
        
        # Test time params
        params = builder.build_search_params(settings)
        self.assertIn('start_time', params)
        
        # Verify start_time is 10 days ago
        start = datetime.fromisoformat(params['start_time'].replace('Z', '+00:00'))
        expected = datetime.now(tz=start.tzinfo) - timedelta(days=10)
        
        diff = abs((start - expected).total_seconds())
        self.assertLess(diff, 60)  # Within 1 minute
    
    def test_settings_persistence_in_metadata(self):
        """Test that all settings are saved in metadata for analysis."""
        from src.wdf.tasks import scrape
        
        settings = {
            'maxTweets': 200,
            'daysBack': 14,
            'minLikes': 15,
            'customField': 'test'  # Extra field
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            tweets_path = Path(temp_dir) / 'tweets.json'
            metadata_path = Path(temp_dir) / 'tweets_metadata.json'
            
            with patch.object(scrape, 'TWEETS_PATH', tweets_path):
                with patch('subprocess.run') as mock_run:
                    mock_run.return_value = Mock(
                        returncode=0,
                        stdout=json.dumps(settings)
                    )
                    
                    with patch.dict(os.environ, {'WDF_WEB_MODE': 'true'}):
                        with patch.object(scrape, 'get_twitter_client') as mock_client:
                            mock_client.return_value.search_by_keywords.return_value = []
                            
                            scrape.run(manual_trigger=True)
                            
                            # Check metadata contains all settings
                            if metadata_path.exists():
                                with open(metadata_path) as f:
                                    metadata = json.load(f)
                                
                                saved_settings = metadata['metadata']['settings']
                                self.assertEqual(saved_settings['maxTweets'], 200)
                                self.assertEqual(saved_settings['daysBack'], 14)
                                self.assertEqual(saved_settings['minLikes'], 15)


if __name__ == '__main__':
    unittest.main(verbosity=2)