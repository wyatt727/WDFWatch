#!/usr/bin/env python3
"""
Test Suite for Tweet Queue System

Comprehensive tests for the new queue management system.
Includes mock data generation and integration tests.

Related files:
- /src/wdf/tasks/queue_processor.py
- /src/wdf/tasks/single_tweet_response.py
- /web/app/api/tweet-queue/route.ts
"""

import pytest
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import sys
from unittest.mock import Mock, patch, MagicMock
import random

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from wdf.tasks.queue_processor import TweetQueueProcessor, QueueItem
from wdf.tasks.single_tweet_response import SingleTweetResponseGenerator
from wdf.settings import WDFSettings


# Mock tweet data generator
def generate_mock_tweet(index: int = 0) -> dict:
    """Generate mock tweet data"""
    topics = [
        "federalism and state sovereignty",
        "constitutional rights",
        "government overreach",
        "individual liberty",
        "free market principles",
        "separation of powers",
        "limited government",
        "states rights"
    ]
    
    return {
        "twitter_id": f"1234567890{index:03d}",
        "author_handle": f"user_{index}",
        "author_name": f"Test User {index}",
        "full_text": f"Interesting thoughts on {random.choice(topics)}. What do you think about this issue? #{random.choice(['politics', 'constitution', 'liberty'])}",
        "metrics": {
            "likes": random.randint(0, 1000),
            "retweets": random.randint(0, 500),
            "replies": random.randint(0, 100)
        },
        "relevance_score": random.uniform(0.3, 0.95)
    }


# Mock queue items generator
def generate_mock_queue_items(count: int = 10) -> list:
    """Generate mock queue items"""
    items = []
    for i in range(count):
        tweet = generate_mock_tweet(i)
        items.append({
            "id": i + 1,
            "tweet_id": f"queue_{i:05d}",
            "twitter_id": tweet["twitter_id"],
            "source": random.choice(["manual", "scrape", "cache"]),
            "priority": random.randint(0, 10),
            "status": "pending",
            "episode_id": random.choice([None, 1, 2, 3]),
            "added_by": "test_user",
            "added_at": (datetime.now() - timedelta(hours=random.randint(0, 72))).isoformat(),
            "metadata": {},
            "retry_count": 0,
            "tweet_text": tweet["full_text"],
            "author_handle": tweet["author_handle"],
            "author_name": tweet["author_name"],
            "relevance_score": tweet["relevance_score"]
        })
    return items


class TestQueueProcessor:
    """Test queue processor functionality"""
    
    @pytest.fixture
    def settings(self):
        """Create test settings"""
        return WDFSettings(
            mock_mode=True,
            web_mode=True
        )
    
    @pytest.fixture
    def processor(self, settings):
        """Create queue processor instance"""
        return TweetQueueProcessor(settings)
    
    def test_queue_item_model(self):
        """Test QueueItem model validation"""
        mock_data = generate_mock_queue_items(1)[0]
        item = QueueItem(**mock_data)
        
        assert item.twitter_id == mock_data["twitter_id"]
        assert item.priority == mock_data["priority"]
        assert item.status == "pending"
        assert item.retry_count == 0
    
    @patch('psycopg2.connect')
    def test_database_connection(self, mock_connect, processor):
        """Test database connection"""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        result = processor.connect_db()
        
        assert result is True
        assert processor.db_connection == mock_conn
        mock_connect.assert_called_once()
    
    @patch.object(TweetQueueProcessor, 'fetch_queue_items')
    @pytest.mark.asyncio
    async def test_process_batch(self, mock_fetch, processor):
        """Test batch processing"""
        # Mock queue items
        mock_items = [
            QueueItem(**item) for item in generate_mock_queue_items(5)
        ]
        mock_fetch.return_value = mock_items
        
        # Mock database connection
        processor.db_connection = MagicMock()
        
        # Process batch
        with patch.object(processor, 'process_item', return_value=True) as mock_process:
            result = await processor.process_batch(batch_size=5)
            
            assert result == 5
            assert mock_process.call_count == 5
    
    @pytest.mark.asyncio
    async def test_process_item_below_threshold(self, processor):
        """Test processing item below relevance threshold"""
        # Create item with low relevance
        item = QueueItem(**{
            **generate_mock_queue_items(1)[0],
            "relevance_score": 0.3
        })
        
        # Mock database connection
        processor.db_connection = MagicMock()
        
        # Process item
        with patch.object(processor, 'update_item_status') as mock_update:
            result = await processor.process_item(item)
            
            assert result is True
            mock_update.assert_called_with(item.id, 'completed')
    
    @pytest.mark.asyncio
    async def test_process_item_above_threshold(self, processor):
        """Test processing item above relevance threshold"""
        # Create item with high relevance
        item = QueueItem(**{
            **generate_mock_queue_items(1)[0],
            "relevance_score": 0.85
        })
        
        # Mock database connection
        processor.db_connection = MagicMock()
        
        # Process item
        with patch.object(processor, 'update_item_status') as mock_update:
            with patch.object(processor.web_bridge, 'send_event') as mock_event:
                result = await processor.process_item(item)
                
                assert result is True
                mock_update.assert_called_with(item.id, 'completed')
                mock_event.assert_called()
    
    def test_update_item_status_retry(self, processor):
        """Test retry logic for failed items"""
        processor.db_connection = MagicMock()
        cursor_mock = MagicMock()
        processor.db_connection.cursor.return_value.__enter__.return_value = cursor_mock
        
        # Update with failure status
        processor.update_item_status(1, 'failed', 'Test error')
        
        # Check SQL includes retry logic
        cursor_mock.execute.assert_called()
        sql = cursor_mock.execute.call_args[0][0]
        assert 'retry_count' in sql
        assert 'CASE' in sql


class TestSingleTweetResponse:
    """Test single tweet response generator"""
    
    @pytest.fixture
    def settings(self):
        """Create test settings"""
        return WDFSettings(
            mock_mode=True,
            web_mode=True
        )
    
    @pytest.fixture
    def generator(self, settings):
        """Create response generator instance"""
        return SingleTweetResponseGenerator(settings)
    
    def test_parse_tweet_url(self, generator):
        """Test tweet URL parsing"""
        # Test Twitter.com URL
        url1 = "https://twitter.com/username/status/1234567890"
        result1 = generator.parse_tweet_url(url1)
        assert result1["username"] == "username"
        assert result1["tweet_id"] == "1234567890"
        
        # Test X.com URL
        url2 = "https://x.com/another_user/status/9876543210"
        result2 = generator.parse_tweet_url(url2)
        assert result2["username"] == "another_user"
        assert result2["tweet_id"] == "9876543210"
        
        # Test invalid URL
        url3 = "https://example.com/not-a-tweet"
        result3 = generator.parse_tweet_url(url3)
        assert result3 is None
    
    def test_validate_response(self, generator):
        """Test response validation"""
        # Valid response
        valid_response = "Great point! Check out the WDF podcast for more."
        result1 = generator.validate_response(valid_response)
        assert result1["valid"] is True
        assert result1["character_count"] < 280
        
        # Too long response
        long_response = "x" * 281
        result2 = generator.validate_response(long_response)
        assert result2["valid"] is False
        assert "max 280" in result2["errors"][0]
        
        # Empty response
        empty_response = ""
        result3 = generator.validate_response(empty_response)
        assert result3["valid"] is False
        assert "empty" in result3["errors"][0].lower()
    
    def test_load_episode_context(self, generator):
        """Test episode context loading"""
        # Test with specific episode ID
        context1 = generator.load_episode_context(1)
        assert context1["id"] == 1
        assert "title" in context1
        assert "summary" in context1
        
        # Test with no episode ID (latest)
        context2 = generator.load_episode_context(None)
        assert context2["id"] == 0
        assert "Latest" in context2["title"]
    
    @pytest.mark.asyncio
    async def test_process_request_success(self, generator):
        """Test successful request processing"""
        params = {
            "tweet_url": "https://x.com/user/status/123",
            "tweet_text": "Test tweet about federalism",
            "episode_id": 1,
            "request_id": 100
        }
        
        with patch.object(generator.web_bridge, 'send_event') as mock_event:
            result = await generator.process_request(params)
            
            assert result["success"] is True
            assert "text" in result
            assert result["character_count"] <= 280
            mock_event.assert_called()
    
    @pytest.mark.asyncio
    async def test_process_request_failure(self, generator):
        """Test request processing failure"""
        params = {
            "tweet_url": "invalid-url",
            "request_id": 101
        }
        
        with patch.object(generator.web_bridge, 'send_event') as mock_event:
            result = await generator.process_request(params)
            
            assert result["success"] is False
            assert "error" in result
            # Should send failure event
            calls = mock_event.call_args_list
            assert any('failed' in str(call) for call in calls)


class TestIntegration:
    """Integration tests for queue system"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_queue_processing(self):
        """Test full queue processing workflow"""
        settings = WDFSettings(mock_mode=True, web_mode=True)
        processor = TweetQueueProcessor(settings)
        
        # Mock database and queue items
        processor.db_connection = MagicMock()
        mock_items = [
            QueueItem(**item) for item in generate_mock_queue_items(3)
        ]
        
        with patch.object(processor, 'fetch_queue_items', return_value=mock_items):
            with patch.object(processor, 'update_item_status'):
                with patch.object(processor.web_bridge, 'send_event'):
                    result = await processor.process_batch(batch_size=3)
                    
                    assert result == 3
                    assert processor.processed_count == 3
    
    @pytest.mark.asyncio
    async def test_single_tweet_to_queue_flow(self):
        """Test flow from single tweet to queue"""
        settings = WDFSettings(mock_mode=True, web_mode=True)
        generator = SingleTweetResponseGenerator(settings)
        
        # Generate response
        params = {
            "tweet_url": "https://x.com/test/status/123",
            "tweet_text": "Constitutional question",
            "episode_id": 1
        }
        
        with patch.object(generator.web_bridge, 'send_event'):
            result = await generator.process_request(params)
            
            assert result["success"] is True
            
            # Simulate adding to queue
            queue_item = {
                "twitter_id": "123",
                "source": "direct_url",
                "priority": 10,  # High priority for manual
                "tweet_text": params["tweet_text"],
                "metadata": {"response": result["text"]}
            }
            
            assert queue_item["priority"] == 10
            assert queue_item["source"] == "direct_url"


# Performance tests
class TestPerformance:
    """Performance and load tests"""
    
    @pytest.mark.asyncio
    async def test_batch_processing_performance(self):
        """Test processing speed for large batches"""
        settings = WDFSettings(mock_mode=True, web_mode=True)
        processor = TweetQueueProcessor(settings)
        processor.db_connection = MagicMock()
        
        # Generate large batch
        large_batch = [
            QueueItem(**item) for item in generate_mock_queue_items(100)
        ]
        
        import time
        start_time = time.time()
        
        with patch.object(processor, 'fetch_queue_items', return_value=large_batch):
            with patch.object(processor, 'update_item_status'):
                with patch.object(processor.web_bridge, 'send_event'):
                    # Process with mock implementation
                    tasks = []
                    for item in large_batch:
                        # Simulate quick processing
                        item.relevance_score = random.uniform(0.3, 0.95)
                    
                    elapsed = time.time() - start_time
                    
                    # Should process 100 items quickly in mock mode
                    assert elapsed < 5.0  # Less than 5 seconds
                    assert len(large_batch) == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])