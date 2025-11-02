"""Tweet queue processing utilities for worker jobs.

This module replaces the legacy ``src/wdf/tasks/queue_processor.py`` script with
backend-native services that integrate directly with FastAPI workers and RQ.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class QueueItem:
    """Representation of a queue entry pulled from the database."""

    id: int
    tweet_id: str
    twitter_id: str
    source: str
    priority: int
    status: str
    episode_id: Optional[int]
    added_by: Optional[str]
    added_at: datetime
    metadata: Dict[str, Any]
    retry_count: int
    tweet_text: Optional[str]
    author_handle: Optional[str]
    author_name: Optional[str]
    relevance_score: Optional[float]


class TweetQueueService:
    """Service encapsulating database access for the tweet queue."""

    def __init__(self) -> None:
        self.db_url = settings.DATABASE_URL_CLEAN

    def _get_connection(self):
        return psycopg2.connect(self.db_url)

    def fetch_pending_items(self, batch_size: int = 10) -> List[QueueItem]:
        """Fetch a locked batch of pending items and mark them as processing."""
        query = """
            SELECT 
                q.*, 
                t.full_text AS tweet_text,
                t.author_handle,
                t.author_name,
                t.relevance_score
            FROM tweet_queue q
            LEFT JOIN tweets t ON t.twitter_id = q.twitter_id
            WHERE q.status = 'pending'
            ORDER BY q.priority DESC, q.added_at ASC
            LIMIT %s
            FOR UPDATE SKIP LOCKED
        """

        mark_processing = """
            UPDATE tweet_queue
               SET status = 'processing',
                   processed_at = CURRENT_TIMESTAMP
             WHERE id = ANY(%s)
        """

        items: List[QueueItem] = []

        with self._get_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (batch_size,))
            rows = cursor.fetchall()

            if not rows:
                return []

            ids = [row["id"] for row in rows]
            cursor.execute(mark_processing, (ids,))
            conn.commit()

            for row in rows:
                metadata = row.get("metadata") or {}
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except json.JSONDecodeError:
                        metadata = {"raw": metadata}

                items.append(
                    QueueItem(
                        id=row["id"],
                        tweet_id=row.get("tweet_id", ""),
                        twitter_id=row.get("twitter_id", ""),
                        source=row.get("source", "unknown"),
                        priority=row.get("priority", 0),
                        status=row.get("status", "pending"),
                        episode_id=row.get("episode_id"),
                        added_by=row.get("added_by"),
                        added_at=row.get("added_at") or datetime.utcnow(),
                        metadata=metadata,
                        retry_count=row.get("retry_count", 0),
                        tweet_text=row.get("tweet_text"),
                        author_handle=row.get("author_handle"),
                        author_name=row.get("author_name"),
                        relevance_score=row.get("relevance_score"),
                    )
                )

        logger.info("Fetched %d queue items", len(items))
        return items

    def mark_completed(self, item_id: int, *, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Mark a queue item as completed."""
        query = """
            UPDATE tweet_queue
               SET status = 'completed',
                   metadata = metadata || %s::jsonb,
                   processed_at = CURRENT_TIMESTAMP
             WHERE id = %s
        """

        payload = json.dumps(metadata or {})

        with self._get_connection() as conn, conn.cursor() as cursor:
            cursor.execute(query, (payload, item_id))
            conn.commit()

    def mark_failed(self, item_id: int, *, error: str) -> None:
        """Increment retry count; fail permanently after three attempts."""
        query = """
            UPDATE tweet_queue
               SET status = CASE WHEN retry_count < 3 THEN 'pending' ELSE 'failed' END,
                   retry_count = retry_count + 1,
                   metadata = metadata || %s::jsonb
             WHERE id = %s
        """

        payload = json.dumps({"last_error": error})

        with self._get_connection() as conn, conn.cursor() as cursor:
            cursor.execute(query, (payload, item_id))
            conn.commit()


# Global singleton
tweet_queue_service = TweetQueueService()


