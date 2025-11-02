"""Tests for queue processing with backend worker jobs."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from backend.api.app.services.tweet_queue import QueueItem
from backend.api.app.workers.jobs import process_tweet_queue_job


def _build_queue_item(**overrides) -> QueueItem:
    """Helper to create queue items with sensible defaults."""

    defaults = {
        "id": 1,
        "tweet_id": "queue_00001",
        "twitter_id": "1234567890",
        "source": "manual",
        "priority": 5,
        "status": "pending",
        "episode_id": None,
        "added_by": "tester",
        "added_at": datetime.now(timezone.utc),
        "metadata": {},
        "retry_count": 0,
        "tweet_text": "Sample tweet text",
        "author_handle": "tester",
        "author_name": "Test User",
        "relevance_score": 0.85,
    }

    defaults.update(overrides)
    return QueueItem(**defaults)


@patch("backend.api.app.workers.jobs.events_service")
@patch("backend.api.app.workers.jobs.tweet_queue_service")
def test_process_queue_no_items(mock_service: MagicMock, mock_events: MagicMock):
    """Job should return early when there are no pending items."""

    mock_service.fetch_pending_items.return_value = []

    result = process_tweet_queue_job(batch_size=5)

    assert result == {"processed": 0, "failed": 0, "skipped": 0, "batch_size": 5}
    mock_service.fetch_pending_items.assert_called_once_with(batch_size=5)
    mock_events.publish_job_event.assert_any_call(
        job_id=mock_events.publish_job_event.call_args_list[-1][1]["job_id"],
        status="completed",
        progress=100.0,
        message="No pending items in queue",
    )


@patch("backend.api.app.workers.jobs.events_service")
@patch("backend.api.app.workers.jobs.tweet_queue_service")
def test_process_queue_marks_skipped(mock_service: MagicMock, mock_events: MagicMock):
    """Items below the relevance threshold should be skipped but marked complete."""

    item = _build_queue_item(id=2, relevance_score=0.4)
    mock_service.fetch_pending_items.return_value = [item]

    result = process_tweet_queue_job(batch_size=1, relevance_threshold=0.7)

    assert result["skipped"] == 1
    mock_service.mark_completed.assert_called_once_with(
        item.id,
        metadata={
            "reason": "below_threshold",
            "relevance_score": item.relevance_score,
            "threshold": 0.7,
        },
    )
    mock_events.publish_queue_event.assert_any_call(
        queue_id=item.id,
        status="skipped",
        message="Tweet below relevance threshold",
        metadata={"score": item.relevance_score, "threshold": 0.7},
    )


@patch("backend.api.app.workers.jobs.events_service")
@patch("backend.api.app.workers.jobs.tweet_queue_service")
def test_process_queue_marks_failed_when_missing_text(mock_service: MagicMock, mock_events: MagicMock):
    """Items without tweet content should increment failure counters."""

    item = _build_queue_item(id=3, tweet_text=None)
    mock_service.fetch_pending_items.return_value = [item]

    result = process_tweet_queue_job(batch_size=1)

    assert result["failed"] == 1
    mock_service.mark_failed.assert_called_once_with(item.id, error="Tweet content unavailable")
    mock_events.publish_queue_event.assert_any_call(
        queue_id=item.id,
        status="failed",
        message="Tweet content unavailable",
    )


