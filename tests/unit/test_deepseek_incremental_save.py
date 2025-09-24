"""
Test that the deepseek module saves responses incrementally after each tweet is processed.
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wdf.tasks import deepseek


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create test directories and files
        transcripts_dir = temp_path / "transcripts"
        transcripts_dir.mkdir()
        
        # Create a classified.json file with test tweets
        classified_path = transcripts_dir / "classified.json"
        test_tweets = [
            {
                "id": "tweet1",
                "text": "Test tweet 1",
                "user": "@user1",
                "created_at": "2025-06-28T23:39:41.718683",
                "classification": "RELEVANT"
            },
            {
                "id": "tweet2",
                "text": "Test tweet 2",
                "user": "@user2",
                "created_at": "2025-06-28T23:39:41.718683",
                "classification": "RELEVANT"
            },
            {
                "id": "tweet3",
                "text": "Test tweet 3",
                "user": "@user3",
                "created_at": "2025-06-28T23:39:41.718683",
                "classification": "SKIP"
            }
        ]
        classified_path.write_text(json.dumps(test_tweets), encoding="utf-8")
        
        # Create a summary.md file
        summary_path = transcripts_dir / "summary.md"
        summary_path.write_text("Test podcast summary", encoding="utf-8")
        
        # Create a VIDEO_URL.txt file
        video_url_path = transcripts_dir / "VIDEO_URL.txt"
        video_url_path.write_text("https://example.com/video", encoding="utf-8")
        
        # Create an empty responses.json file
        responses_path = transcripts_dir / "responses.json"
        responses_path.write_text("[]", encoding="utf-8")
        
        # Mock the settings
        with patch("wdf.tasks.deepseek.settings") as mock_settings:
            mock_settings.transcript_dir = str(transcripts_dir)
            mock_settings.get_run_dir.return_value = temp_path / "artefacts" / "test_run"
            (temp_path / "artefacts").mkdir()
            (temp_path / "artefacts" / "test_run").mkdir()
            
            # Mock the file paths in the deepseek module
            old_classified_path = deepseek.CLASSIFIED_PATH
            old_summary_path = deepseek.SUMMARY_PATH
            old_video_url_path = deepseek.VIDEO_URL_PATH
            old_responses_path = deepseek.RESPONSES_PATH
            
            deepseek.CLASSIFIED_PATH = classified_path
            deepseek.SUMMARY_PATH = summary_path
            deepseek.VIDEO_URL_PATH = video_url_path
            deepseek.RESPONSES_PATH = responses_path
            
            yield mock_settings
            
            # Restore the paths
            deepseek.CLASSIFIED_PATH = old_classified_path
            deepseek.SUMMARY_PATH = old_summary_path
            deepseek.VIDEO_URL_PATH = old_video_url_path
            deepseek.RESPONSES_PATH = old_responses_path


@patch("wdf.tasks.deepseek.Client")
def test_incremental_save(mock_client_class, mock_settings):
    """Test that responses are saved incrementally."""
    # Mock the Ollama client
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    # Configure the mock to return different responses for each tweet
    call_count = 0
    def mock_generate(**kwargs):
        nonlocal call_count
        call_count += 1
        return {"response": f"Response for tweet {call_count}"}
    
    mock_client.generate.side_effect = mock_generate
    
    # Patch the json.dump method to track when responses are written
    original_json_dump = json.dump
    responses_saved = []
    
    def mock_json_dump(obj, fp, *args, **kwargs):
        # Only track writes to responses.json
        if hasattr(fp, 'name') and str(deepseek.RESPONSES_PATH) in fp.name:
            # Make a deep copy of the object to avoid reference issues
            responses_saved.append(json.loads(json.dumps(obj)))
        return original_json_dump(obj, fp, *args, **kwargs)
    
    # Run the deepseek response generation with our mocks
    with patch('json.dump', mock_json_dump):
        result = deepseek.run(run_id="test_run")
    
    # Verify that responses were saved incrementally
    assert len(responses_saved) >= 2, "Responses should be saved after each tweet"
    
    # Check that the first saved response only contains the first tweet
    first_relevant_tweet = responses_saved[0]
    found_first_response = False
    for tweet in first_relevant_tweet:
        if tweet.get("id") == "tweet1":
            assert tweet.get("response") == "Response for tweet 1"
            assert tweet.get("status") == "pending"
            found_first_response = True
    assert found_first_response, "First response should contain tweet1 with a response"
    
    # Check that the second saved response contains both tweets
    second_relevant_tweet = responses_saved[-1]  # Use the last saved response
    found_second_response = False
    for tweet in second_relevant_tweet:
        if tweet.get("id") == "tweet2":
            assert tweet.get("response") == "Response for tweet 2"
            assert tweet.get("status") == "pending"
            found_second_response = True
    assert found_second_response, "Last response should contain tweet2 with a response"
    
    # Check the final result file
    final_responses = json.loads(deepseek.RESPONSES_PATH.read_text(encoding="utf-8"))
    
    # Verify both relevant tweets have responses
    has_tweet1_response = False
    has_tweet2_response = False
    
    for tweet in final_responses:
        if tweet.get("id") == "tweet1":
            assert tweet.get("response") == "Response for tweet 1"
            assert tweet.get("status") == "pending"
            has_tweet1_response = True
        elif tweet.get("id") == "tweet2":
            assert tweet.get("response") == "Response for tweet 2"
            assert tweet.get("status") == "pending"
            has_tweet2_response = True
    
    assert has_tweet1_response, "Final response should contain tweet1 with a response"
    assert has_tweet2_response, "Final response should contain tweet2 with a response" 