"""
Database service for pipeline operations.
Provides database access for pipeline-specific operations.
"""

import logging
from typing import Optional, Dict, Any, List

import psycopg2
from psycopg2.extras import RealDictCursor

from app.config import settings

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for database operations."""
    
    def __init__(self):
        """Initialize database service."""
        self.db_url = settings.DATABASE_URL_CLEAN
    
    def get_connection(self):
        """Get database connection."""
        return psycopg2.connect(self.db_url)
    
    def get_episode(self, episode_id: int) -> Optional[Dict[str, Any]]:
        """Get episode from database."""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT id, title, episode_dir, claude_episode_dir,
                               claude_context_generated, status, created_at
                        FROM podcast_episodes
                        WHERE id = %s
                    """, (episode_id,))
                    result = cursor.fetchone()
                    return dict(result) if result else None
        except Exception as e:
            logger.error(f"Failed to get episode {episode_id}: {e}")
            return None
    
    def update_episode_status(self, episode_id: int, status: str) -> bool:
        """Update episode status."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        UPDATE podcast_episodes
                        SET status = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (status, episode_id))
                    conn.commit()
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update episode status: {e}")
            return False
    
    def sync_tweets_to_database(self, tweets: List[Dict], episode_id: int) -> int:
        """Sync tweets to database."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    count = 0
                    for tweet in tweets:
                        cursor.execute("""
                            INSERT INTO tweets (
                                twitter_id, author_handle, full_text, text_preview,
                                created_at, updated_at, status, episode_id
                            ) VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s)
                            ON CONFLICT (twitter_id)
                            DO UPDATE SET
                                episode_id = EXCLUDED.episode_id,
                                updated_at = CURRENT_TIMESTAMP
                        """, (
                            tweet.get('id', tweet.get('twitter_id')),
                            tweet.get('user', '@unknown'),
                            tweet.get('text', ''),
                            tweet.get('text', '')[:280],
                            tweet.get('created_at'),
                            'unclassified',
                            episode_id
                        ))
                        count += 1
                    conn.commit()
                    logger.info(f"Synced {count} tweets to database for episode {episode_id}")
                    return count
        except Exception as e:
            logger.error(f"Failed to sync tweets: {e}")
            return 0


# Global instance
db_service = DatabaseService()

