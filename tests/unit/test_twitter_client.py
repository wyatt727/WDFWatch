"""
Unit tests for the Twitter client
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import redis

from wdf.settings import settings
from wdf.twitter_client import (
    Tweet, 
    TweetReply, 
    MockTwitterClient, 
    RealTwitterClient, 
    get_twitter_client,
    is_tweet_published,
    record_tweet_published
)


def test_mock_twitter_client_init():
    """Test MockTwitterClient initialization"""
    client = MockTwitterClient(seed=42)
    assert client.rand.random() == 0.6394267984578837  # Deterministic with seed 42


def test_mock_twitter_client_search_by_keywords(tmp_path, monkeypatch):
    """Test MockTwitterClient search_by_keywords method"""
    # Set up test transcript directory
    test_dir = tmp_path / "test_transcripts"
    test_dir.mkdir()
    monkeypatch.setattr("wdf.twitter_client.settings.transcript_dir", str(test_dir))
    
    # Don't create fewshots.json so it falls back to keyword generation
    client = MockTwitterClient(seed=42)
    keywords = ["liberty", "federalism", "constitution"]
    count = 5
    
    tweets = client.search_by_keywords(keywords, count=count)
    
    assert len(tweets) == count
    assert all(isinstance(t, Tweet) for t in tweets)


@patch("wdf.twitter_client.is_tweet_published")
def test_mock_twitter_client_reply_to_tweet(mock_is_published):
    """Test MockTwitterClient reply_to_tweet method"""
    # Set up the mock to return False the first time (not published)
    # and True the second time (already published)
    mock_is_published.side_effect = [False, True]
    
    client = MockTwitterClient(seed=42)
    tweet_id = "test_id_123"
    text = "This is a test reply"
    run_id = "test_run"
    
    # First reply should succeed
    result = client.reply_to_tweet(tweet_id, text, run_id)
    assert result is True
    
    # Second reply to the same tweet should fail (already published)
    result = client.reply_to_tweet(tweet_id, text, run_id)
    assert result is False


@patch("wdf.twitter_client.is_tweet_published")
def test_mock_twitter_client_publish_batch(mock_is_published):
    """Test MockTwitterClient publish_batch method"""
    # First three calls return False (not published yet)
    # Next three calls return True (already published)
    mock_is_published.side_effect = [False, False, False, True, True, True]
    
    client = MockTwitterClient(seed=42)
    replies = [
        TweetReply(tweet_id="id1", text="Reply 1", timestamp="2023-01-01T12:00:00"),
        TweetReply(tweet_id="id2", text="Reply 2", timestamp="2023-01-01T12:01:00"),
        TweetReply(tweet_id="id3", text="Reply 3", timestamp="2023-01-01T12:02:00")
    ]
    
    results = client.publish_batch(replies, run_id="test_run")
    
    assert len(results) == 3
    assert all(results.values())  # All should succeed
    
    # Try again, all should fail as already published
    results = client.publish_batch(replies, run_id="test_run")
    assert len(results) == 3
    assert not any(results.values())  # All should fail


@patch("wdf.twitter_client.settings")
def test_get_twitter_client_mock_mode(mock_settings):
    """Test get_twitter_client returns MockTwitterClient in mock mode"""
    mock_settings.mock_mode = True
    mock_settings.random_seed = 42
    
    client = get_twitter_client()
    
    assert isinstance(client, MockTwitterClient)


@patch("wdf.twitter_client.settings")
@patch("wdf.twitter_client.RealTwitterClient")
def test_get_twitter_client_real_mode(mock_real_client, mock_settings):
    """Test get_twitter_client returns RealTwitterClient in real mode"""
    mock_settings.mock_mode = False
    mock_instance = MagicMock()
    mock_real_client.return_value = mock_instance
    
    client = get_twitter_client()
    
    assert client is mock_instance
    mock_real_client.assert_called_once()


@patch("wdf.twitter_client.sqlite3")
def test_is_tweet_published(mock_sqlite3):
    """Test is_tweet_published function"""
    # Setup mock cursor
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_sqlite3.connect.return_value = mock_conn
    
    # Test tweet exists
    mock_cursor.fetchone.return_value = (1,)
    assert is_tweet_published("existing_tweet_id") is True
    
    # Test tweet doesn't exist
    mock_cursor.fetchone.return_value = None
    assert is_tweet_published("non_existing_tweet_id") is False


@patch("wdf.twitter_client.sqlite3")
def test_record_tweet_published(mock_sqlite3):
    """Test record_tweet_published function"""
    # Setup mock
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_sqlite3.connect.return_value = mock_conn
    
    # Call function
    record_tweet_published("test_id", "Test response", "test_run")
    
    # Verify
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()
    mock_conn.close.assert_called_once()


class TestRealTwitterClient:
    """Tests for RealTwitterClient"""
    
    @patch("redis.Redis.from_url")
    def test_real_twitter_client_init(self, mock_redis_from_url):
        """Test RealTwitterClient initialization"""
        # Setup mock
        mock_redis = MagicMock()
        mock_redis_from_url.return_value = mock_redis
        
        # Create client
        client = RealTwitterClient(
            api_key="test_key",
            api_secret="test_secret",
            token="test_token",
            token_secret="test_token_secret"
        )
        
        # Verify
        assert client.api_key == "test_key"
        assert client.api_secret == "test_secret"
        assert client.token == "test_token"
        assert client.token_secret == "test_token_secret"
        assert client.redis is mock_redis
    
    @patch("redis.Redis.from_url")
    def test_real_twitter_client_env_vars(self, mock_redis_from_url):
        """Test RealTwitterClient initialization from environment variables"""
        # Setup mock
        mock_redis = MagicMock()
        mock_redis_from_url.return_value = mock_redis
        
        # Setup environment variables
        os.environ["TWITTER_API_KEY"] = "env_key"
        os.environ["TWITTER_API_SECRET"] = "env_secret"
        os.environ["TWITTER_TOKEN"] = "env_token"
        os.environ["TWITTER_TOKEN_SECRET"] = "env_token_secret"
        
        try:
            # Create client
            client = RealTwitterClient()
            
            # Verify
            assert client.api_key == "env_key"
            assert client.api_secret == "env_secret"
            assert client.token == "env_token"
            assert client.token_secret == "env_token_secret"
        finally:
            # Clean up
            del os.environ["TWITTER_API_KEY"]
            del os.environ["TWITTER_API_SECRET"]
            del os.environ["TWITTER_TOKEN"]
            del os.environ["TWITTER_TOKEN_SECRET"]
    
    @patch("redis.Redis.from_url")
    @patch("wdf.twitter_client.is_tweet_published")
    def test_real_twitter_client_reply_to_tweet(self, mock_is_published, mock_redis_from_url):
        """Test RealTwitterClient reply_to_tweet method"""
        # Set up the mock to return False (not published) then True (published)
        mock_is_published.side_effect = [False, True]
        
        # Setup mock redis
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False
        mock_redis_from_url.return_value = mock_redis
        
        # Create client
        client = RealTwitterClient()
        
        # Test reply
        result = client.reply_to_tweet("test_id", "Test reply", "test_run")
        
        # Verify
        assert result is True
        mock_redis.sadd.assert_called_once_with(client._seen_ids_key, "test_id")
        
        # Test already replied
        mock_redis.sismember.return_value = True
        result = client.reply_to_tweet("test_id", "Test reply", "test_run")
        
        # Verify
        assert result is False 