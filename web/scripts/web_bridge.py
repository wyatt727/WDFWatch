#!/usr/bin/env python3
"""
Web UI Bridge for Python Pipeline
Provides integration between Python pipeline and Next.js web UI
Emits SSE events and updates database when pipeline stages complete
"""

import os
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional, Any, Union
import httpx
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

class WebUIBridge:
    """Bridge between Python pipeline and web UI database/SSE events"""
    
    def __init__(self):
        # Get DATABASE_URL and strip Prisma-specific query parameters that psycopg2 doesn't understand
        raw_db_url = os.getenv("DATABASE_URL", "postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5432/wdfwatch")
        # Remove schema and connection_limit parameters that Prisma uses but psycopg2 doesn't support
        self.db_url = raw_db_url.split('?')[0]  # Strip all query parameters
        self.web_url = os.getenv("WEB_URL", "http://localhost:3000")
        self.api_key = os.getenv("WEB_API_KEY", "development-internal-api-key")
        self._connection = None
        
    @property
    def connection(self):
        """Lazy database connection"""
        if self._connection is None or self._connection.closed:
            self._connection = psycopg2.connect(self.db_url)
        return self._connection
        
    def emit_sse_event(self, event: Dict) -> None:
        """Emit SSE event to web UI"""
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{self.web_url}/api/internal/events",
                    json=event,
                    headers={"X-API-Key": self.api_key}
                )
                response.raise_for_status()
                logger.info(f"SSE event emitted: {event['type']}")
        except Exception as e:
            logger.error(f"Failed to emit SSE event: {e}")
            
    def notify_pipeline_start(self, stage: str) -> None:
        """Notify that a pipeline stage has started"""
        self.emit_sse_event({
            "type": "pipeline_status",
            "stage": stage,
            "status": "started",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    def notify_pipeline_complete(self, stage: str) -> None:
        """Notify that a pipeline stage has completed"""
        self.emit_sse_event({
            "type": "pipeline_status",
            "stage": stage,
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    def notify_pipeline_error(self, stage: str, error: str) -> None:
        """Notify that a pipeline stage has failed"""
        self.emit_sse_event({
            "type": "pipeline_status",
            "stage": stage,
            "status": "failed",
            "message": error,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    def sync_tweets(self, tweets: List[Dict]) -> None:
        """Sync tweets from pipeline to database"""
        self.notify_pipeline_start("tweet_sync")
        
        try:
            with self.connection.cursor() as cursor:
                for tweet in tweets:
                    cursor.execute("""
                        INSERT INTO tweets (
                            twitter_id, author_handle, full_text, 
                            text_preview, created_at, status, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (twitter_id) DO UPDATE
                        SET full_text = EXCLUDED.full_text,
                            text_preview = EXCLUDED.text_preview,
                            updated_at = CURRENT_TIMESTAMP
                    """, (
                        tweet['id'],
                        tweet['user'],
                        tweet['text'],
                        tweet['text'][:280],
                        tweet.get('created_at', datetime.utcnow()),
                        'unclassified'
                    ))
                    
                self.connection.commit()
                logger.info(f"Synced {len(tweets)} tweets to database")
                
            self.notify_pipeline_complete("tweet_sync")
            
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Failed to sync tweets: {e}")
            self.notify_pipeline_error("tweet_sync", str(e))
            raise
            
    def notify_tweets_classified(self, classified_tweets: List[Dict]) -> None:
        """Update tweet classifications in database"""
        self.notify_pipeline_start("classification_sync")
        
        try:
            with self.connection.cursor() as cursor:
                relevant_count = 0
                
                for tweet in classified_tweets:
                    # Use score threshold for status determination
                    score = tweet.get('relevance_score', tweet.get('score', 0))
                    status = 'relevant' if score >= 0.70 else 'skipped'
                    if status == 'relevant':
                        relevant_count += 1
                        
                    cursor.execute("""
                        UPDATE tweets 
                        SET status = %s, 
                            relevance_score = %s,
                            classification_rationale = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE twitter_id = %s
                    """, (
                        status,
                        tweet.get('relevance_score', tweet.get('score')),
                        tweet.get('rationale'),
                        tweet['id']
                    ))
                    
                self.connection.commit()
                
            # Emit SSE event
            self.emit_sse_event({
                "type": "tweets_classified",
                "count": len(classified_tweets),
                "relevant": relevant_count
            })
            
            self.notify_pipeline_complete("classification_sync")
            logger.info(f"Updated {len(classified_tweets)} tweet classifications")
            
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Failed to update classifications: {e}")
            self.notify_pipeline_error("classification_sync", str(e))
            raise
            
    def create_draft(self, tweet_id: str, response: str, model: str) -> int:
        """Create a draft response in the database
        
        IMPORTANT: 
        - Deletes any existing pending drafts for this tweet before creating new one
        - SKIPS creation if tweet already has approved/posted/scheduled draft
        """
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                # Get tweet database ID
                cursor.execute(
                    "SELECT id FROM tweets WHERE twitter_id = %s",
                    (tweet_id,)
                )
                tweet_row = cursor.fetchone()
                
                if not tweet_row:
                    raise ValueError(f"Tweet {tweet_id} not found in database")
                
                # CHECK for existing approved/posted/scheduled drafts
                # If tweet is already in queue or posted, skip creation
                cursor.execute("""
                    SELECT id, status FROM draft_replies 
                    WHERE tweet_id = %s AND status IN ('approved', 'posted', 'scheduled')
                    LIMIT 1
                """, (tweet_row['id'],))
                
                existing_approved = cursor.fetchone()
                if existing_approved:
                    logger.info(
                        f"Skipping draft creation for tweet {tweet_id} - "
                        f"already has {existing_approved['status']} draft"
                    )
                    return 0  # Return 0 to indicate no draft created
                
                # DELETE any existing drafts for this tweet that are still pending
                # This ensures we only keep the latest response generation
                cursor.execute("""
                    DELETE FROM draft_replies 
                    WHERE tweet_id = %s AND status = 'pending'
                """, (tweet_row['id'],))
                
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    logger.info(f"Deleted {deleted_count} old pending draft(s) for tweet {tweet_id}")
                    
                # Create new draft
                cursor.execute("""
                    INSERT INTO draft_replies (
                        tweet_id, model_name, text, status, version, updated_at
                    ) VALUES (%s, %s, %s, 'pending', 1, CURRENT_TIMESTAMP)
                    RETURNING id
                """, (tweet_row['id'], model, response))
                
                draft_id = cursor.fetchone()['id']
                
                # Update tweet status
                cursor.execute("""
                    UPDATE tweets SET status = 'drafted' 
                    WHERE twitter_id = %s AND status = 'relevant'
                """, (tweet_id,))
                
                self.connection.commit()
                
                # Emit SSE event
                self.emit_sse_event({
                    "type": "draft_ready",
                    "draftId": str(draft_id),
                    "tweetId": tweet_id
                })
                
                # Also emit tweet status change
                self.emit_sse_event({
                    "type": "tweet_status",
                    "tweetId": tweet_id,
                    "newStatus": "drafted"
                })
                
                logger.info(f"Created draft {draft_id} for tweet {tweet_id}")
                return draft_id
                
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Failed to create draft: {e}")
            raise
            
    def update_quota(self, used: int, remaining: int) -> None:
        """Update quota usage and emit SSE event"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO twitter_quota (
                        date, used_reads, total_allowed
                    ) VALUES (CURRENT_DATE, %s, %s)
                    ON CONFLICT (date) DO UPDATE
                    SET used_reads = %s,
                        updated_at = CURRENT_TIMESTAMP
                """, (used, used + remaining, used))
                
                self.connection.commit()
                
            # Emit SSE event
            self.emit_sse_event({
                "type": "quota_update",
                "used": used,
                "remaining": remaining
            })
            
            logger.info(f"Updated quota: {used} used, {remaining} remaining")
            
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Failed to update quota: {e}")
            
    def get_enabled_keywords(self, episode_id: Optional[str] = None) -> List[Dict[str, float]]:
        """Fetch enabled keywords from the database
        
        Args:
            episode_id: Optional episode ID to fetch episode-specific keywords
            
        Returns:
            List of keyword dictionaries with 'keyword' and 'weight' fields
        """
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                if episode_id:
                    # Get keywords for specific episode ONLY
                    cursor.execute("""
                        SELECT DISTINCT keyword, MAX(weight) as weight 
                        FROM keywords 
                        WHERE episode_id = %s AND enabled = true
                        GROUP BY keyword
                        ORDER BY weight DESC, keyword
                    """, (episode_id,))
                    logger.info(f"Fetching keywords for episode {episode_id} ONLY (no global keywords)")
                else:
                    # Get ONLY global keywords (not episode-specific)
                    # This prevents accidentally mixing keywords from different episodes
                    cursor.execute("""
                        SELECT keyword, weight 
                        FROM keywords 
                        WHERE episode_id IS NULL AND enabled = true
                        ORDER BY weight DESC, keyword
                    """)
                    logger.info("Fetching only global keywords (no episode context)")
                
                keywords = cursor.fetchall()
                
                # Check if no keywords found
                if not keywords:
                    if episode_id:
                        logger.warning(
                            f"No keywords found for episode {episode_id}. "
                            "Make sure summarization has been run first."
                        )
                    else:
                        logger.warning(
                            "No global keywords found and no episode_id provided. "
                            "Consider adding global keywords or providing an episode_id."
                        )
                
                logger.info(
                    f"Fetched {len(keywords)} enabled keywords from database",
                    extra={
                        "episode_id": episode_id,
                        "keyword_count": len(keywords),
                        "source": "episode_only" if episode_id else "global_only"
                    }
                )
                return keywords
                
        except Exception as e:
            logger.error(f"Failed to fetch keywords: {e}")
            return []
    
    def sync_keywords_to_file(self, keywords: List[Dict[str, float]], output_path: str) -> None:
        """Write keywords to JSON file for pipeline compatibility
        
        Args:
            keywords: List of keyword dictionaries
            output_path: Path to write keywords JSON file
        """
        try:
            # Convert to simple list of strings for compatibility with existing pipeline
            keyword_list = [kw['keyword'] for kw in keywords]
            
            with open(output_path, 'w') as f:
                json.dump(keyword_list, f, indent=2)
                
            logger.info(f"Synced {len(keyword_list)} keywords to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to sync keywords to file: {e}")
            raise
    
    def save_keywords_to_database(self, episode_dir: str, keywords: List[str], source: str = "claude") -> None:
        """Save keywords to database for a specific episode
        
        Args:
            episode_dir: Episode directory name (e.g., "episode_999_fixing_db")
            keywords: List of keyword strings
            source: Source of keywords (claude, manual, etc.)
        """
        try:
            with self.connection.cursor() as cursor:
                # First, find the database episode ID by claude_episode_dir
                cursor.execute("""
                    SELECT id FROM podcast_episodes 
                    WHERE claude_episode_dir = %s
                """, (episode_dir,))
                
                result = cursor.fetchone()
                if not result:
                    logger.warning(f"No episode found with claude_episode_dir: {episode_dir}")
                    return
                
                episode_id = result[0]
                logger.info(f"Found database episode ID {episode_id} for directory {episode_dir}")
                
                # Delete existing keywords for this episode from the same source
                cursor.execute("""
                    DELETE FROM keywords 
                    WHERE episode_id = %s AND source = %s
                """, (episode_id, source))
                
                # Insert new keywords
                for keyword in keywords:
                    cursor.execute("""
                        INSERT INTO keywords (episode_id, keyword, weight, source, enabled)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (episode_id, keyword) DO UPDATE
                        SET weight = EXCLUDED.weight,
                            source = EXCLUDED.source,
                            enabled = EXCLUDED.enabled
                    """, (episode_id, keyword, 1.0, source, True))
                
                self.connection.commit()
                logger.info(f"Saved {len(keywords)} keywords to database for episode {episode_id} (dir: {episode_dir})")
                
                # Emit SSE event
                self.emit_sse_event({
                    "type": "keywords_updated",
                    "episodeId": episode_id,
                    "count": len(keywords),
                    "source": source
                })
                
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Failed to save keywords to database: {e}")
            raise
            
    def get_api_keys(self) -> Dict[str, Dict[str, str]]:
        """Fetch decrypted API keys from web UI
        
        Returns:
            Dictionary with service names as keys and API credentials as values
        """
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.web_url}/api/internal/api-keys",
                    headers={"X-API-Key": self.api_key}
                )
                response.raise_for_status()
                api_keys = response.json()
                logger.info("Successfully fetched API keys from web UI")
                return api_keys
        except Exception as e:
            logger.error(f"Failed to fetch API keys from web UI: {e}")
            # Return empty dict on error
            return {"twitter": {}, "gemini": {}, "openai": {}}
    
    # Claude Pipeline Methods
    
    def emit_event(self, event: Dict) -> None:
        """Alias for emit_sse_event for compatibility with claude_pipeline_bridge"""
        self.emit_sse_event(event)
    
    def get_episode(self, episode_id: int) -> Optional[Dict]:
        """Get episode data from database"""
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT id, title, transcript_text, summary_text, video_url,
                           episode_dir, claude_episode_dir, claude_context_generated, 
                           claude_pipeline_status, pipeline_type
                    FROM podcast_episodes 
                    WHERE id = %s
                """, (episode_id,))
                return cursor.fetchone()
        except Exception as e:
            logger.error(f"Failed to get episode {episode_id}: {e}")
            return None
    
    def update_claude_episode_dir(self, episode_id: int, episode_dir: str) -> None:
        """Update Claude episode directory in database"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE podcast_episodes 
                    SET claude_episode_dir = %s,
                        pipeline_type = 'claude',
                        claude_pipeline_status = 'initialized',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (episode_dir, episode_id))
                self.connection.commit()
                logger.info(f"Updated Claude episode dir for episode {episode_id}: {episode_dir}")
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Failed to update Claude episode dir: {e}")
            raise
    
    def update_claude_pipeline_status(self, episode_id: int, status: str) -> None:
        """Update Claude pipeline status in database"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE podcast_episodes 
                    SET claude_pipeline_status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (status, episode_id))
                self.connection.commit()
                
            # Emit status update event
            self.emit_sse_event({
                'type': 'claude_pipeline_status',
                'episodeId': episode_id,
                'status': status
            })
            
            logger.info(f"Updated Claude pipeline status for episode {episode_id}: {status}")
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Failed to update Claude pipeline status: {e}")
            raise
    
    def track_claude_run(self, episode_id: int, run_id: str, stage: str, 
                        status: str, input_tokens: int = 0, output_tokens: int = 0,
                        cost: float = 0, error_message: str = None) -> None:
        """Track Claude pipeline run in database"""
        try:
            with self.connection.cursor() as cursor:
                if status == 'running':
                    cursor.execute("""
                        INSERT INTO claude_pipeline_runs 
                        (episode_id, run_id, stage, claude_mode, status, started_at)
                        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (run_id) DO UPDATE
                        SET status = EXCLUDED.status
                    """, (episode_id, run_id, stage, stage, status))
                else:
                    cursor.execute("""
                        UPDATE claude_pipeline_runs 
                        SET status = %s,
                            input_tokens = %s,
                            output_tokens = %s,
                            cost_usd = %s,
                            error_message = %s,
                            completed_at = CURRENT_TIMESTAMP,
                            duration_seconds = EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at))
                        WHERE run_id = %s
                    """, (status, input_tokens, output_tokens, cost, error_message, run_id))
                
                self.connection.commit()
                logger.info(f"Tracked Claude run {run_id}: {stage} - {status}")
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Failed to track Claude run: {e}")
    
    def track_claude_costs(self, costs: Dict[str, float]) -> None:
        """Track Claude costs by mode"""
        try:
            with self.connection.cursor() as cursor:
                for mode, cost in costs.items():
                    cursor.execute("""
                        INSERT INTO claude_costs (date, mode, total_cost_usd, run_count)
                        VALUES (CURRENT_DATE, %s, %s, 1)
                        ON CONFLICT (date, mode) 
                        DO UPDATE SET 
                            total_cost_usd = claude_costs.total_cost_usd + EXCLUDED.total_cost_usd,
                            run_count = claude_costs.run_count + 1,
                            updated_at = CURRENT_TIMESTAMP
                    """, (mode, cost))
                
                self.connection.commit()
                logger.info(f"Tracked Claude costs: {costs}")
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Failed to track Claude costs: {e}")
    
    def save_episode_context(self, episode_id: int, context_type: str,
                            context_content: str, claude_mode: str = None) -> None:
        """Save episode context to database"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO episode_contexts 
                    (episode_id, context_type, context_content, claude_mode, is_active)
                    VALUES (%s, %s, %s, %s, true)
                    ON CONFLICT (episode_id, context_type) 
                    WHERE claude_mode IS NULL
                    DO UPDATE SET 
                        context_content = EXCLUDED.context_content,
                        version = episode_contexts.version + 1,
                        updated_at = CURRENT_TIMESTAMP
                """, (episode_id, context_type, context_content, claude_mode))
                
                self.connection.commit()
                logger.info(f"Saved episode context for episode {episode_id}")
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Failed to save episode context: {e}")
            raise
    
    def get_episode_context(self, episode_id: int, context_type: str = None,
                           claude_mode: str = None) -> Optional[str]:
        """Get episode context from database"""
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                query = """
                    SELECT context_content 
                    FROM episode_contexts 
                    WHERE episode_id = %s AND is_active = true
                """
                params = [episode_id]
                
                if context_type:
                    query += " AND context_type = %s"
                    params.append(context_type)
                
                if claude_mode:
                    query += " AND claude_mode = %s"
                    params.append(claude_mode)
                
                query += " ORDER BY version DESC LIMIT 1"
                
                cursor.execute(query, params)
                result = cursor.fetchone()
                return result['context_content'] if result else None
        except Exception as e:
            logger.error(f"Failed to get episode context: {e}")
            return None
    
    def get_unclassified_tweets(self, episode_id: int) -> List[Dict]:
        """Get unclassified tweets for an episode"""
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT id, twitter_id, full_text, author_handle
                    FROM tweets 
                    WHERE episode_id = %s AND status = 'unclassified'
                    ORDER BY created_at DESC
                """, (episode_id,))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Failed to get unclassified tweets: {e}")
            return []
    
    def create_draft_reply(self, tweet_id: int, text: str, model_name: str, 
                          metadata: Dict = None) -> None:
        """Create a draft reply in the database
        
        IMPORTANT: 
        - Deletes any existing pending drafts for this tweet before creating new one
        - SKIPS creation if tweet already has approved/posted/scheduled draft
        """
        try:
            with self.connection.cursor() as cursor:
                # CHECK for existing approved/posted/scheduled drafts
                # If tweet is already in queue or posted, skip creation
                cursor.execute("""
                    SELECT id, status FROM draft_replies 
                    WHERE tweet_id = %s AND status IN ('approved', 'posted', 'scheduled')
                    LIMIT 1
                """, (tweet_id,))
                
                existing_approved = cursor.fetchone()
                if existing_approved:
                    logger.info(
                        f"Skipping draft creation for tweet ID {tweet_id} - "
                        f"already has {existing_approved[1]} draft"
                    )
                    return  # Skip creation
                
                # DELETE any existing drafts for this tweet that are still pending
                # This ensures we only keep the latest response generation
                cursor.execute("""
                    DELETE FROM draft_replies 
                    WHERE tweet_id = %s AND status = 'pending'
                """, (tweet_id,))
                
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    logger.info(f"Deleted {deleted_count} old pending draft(s) for tweet ID {tweet_id}")
                
                # Create new draft
                cursor.execute("""
                    INSERT INTO draft_replies 
                    (tweet_id, model_name, text, status, character_count, created_at)
                    VALUES (%s, %s, %s, 'pending', %s, CURRENT_TIMESTAMP)
                """, (tweet_id, model_name, text, len(text)))
                
                self.connection.commit()
                logger.info(f"Created draft reply for tweet {tweet_id}")
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Failed to create draft reply: {e}")
            raise
    
    def approve_draft(self, tweet_id: int, approved_by: str, metadata: Dict = None) -> None:
        """Approve a draft reply"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE draft_replies 
                    SET status = 'approved',
                        approved_by = %s,
                        approved_at = CURRENT_TIMESTAMP
                    WHERE tweet_id = %s AND status = 'pending'
                """, (approved_by, tweet_id))
                
                self.connection.commit()
                logger.info(f"Approved draft for tweet {tweet_id}")
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Failed to approve draft: {e}")
            raise
    
    def calculate_claude_cost(self, input_tokens: int, output_tokens: int, 
                             mode: str) -> float:
        """
        Calculate Claude API cost.
        Rates for Claude 3 Sonnet (as of 2024):
        - Input: $3 per million tokens
        - Output: $15 per million tokens
        """
        input_cost = (input_tokens / 1_000_000) * 3.0
        output_cost = (output_tokens / 1_000_000) * 15.0
        return round(input_cost + output_cost, 4)
    
    def get_claude_costs_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get Claude costs summary for the last N days"""
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        mode,
                        SUM(total_cost_usd) as total_cost,
                        SUM(run_count) as total_runs,
                        AVG(total_cost_usd / NULLIF(run_count, 0)) as avg_cost_per_run
                    FROM claude_costs
                    WHERE date >= CURRENT_DATE - INTERVAL '%s days'
                    GROUP BY mode
                    ORDER BY total_cost DESC
                """, (days,))
                
                costs_by_mode = cursor.fetchall()
                
                # Get total
                cursor.execute("""
                    SELECT 
                        SUM(total_cost_usd) as total_cost,
                        SUM(run_count) as total_runs
                    FROM claude_costs
                    WHERE date >= CURRENT_DATE - INTERVAL '%s days'
                """, (days,))
                
                totals = cursor.fetchone()
                
                return {
                    'by_mode': costs_by_mode,
                    'total_cost': float(totals['total_cost'] or 0),
                    'total_runs': totals['total_runs'] or 0,
                    'period_days': days
                }
        except Exception as e:
            logger.error(f"Failed to get Claude costs summary: {e}")
            return {
                'by_mode': [],
                'total_cost': 0,
                'total_runs': 0,
                'period_days': days
            }
    
    def track_pipeline_run(self, run_id: str, stage: str, status: str, 
                          error: str = None) -> None:
        """Track overall pipeline run (compatibility method)"""
        # This is handled by track_claude_run for Claude pipeline
        pass
    
    def close(self):
        """Close database connection"""
        if self._connection and not self._connection.closed:
            self._connection.close()


# Integration functions for use in existing pipeline tasks
def get_bridge():
    """Get or create WebUIBridge instance"""
    if not hasattr(get_bridge, '_instance'):
        get_bridge._instance = WebUIBridge()
    return get_bridge._instance


def sync_if_web_mode(tweets: List[Dict]) -> None:
    """Sync tweets to web UI if in web mode"""
    if os.getenv("WDF_WEB_MODE", "false").lower() == "true":
        bridge = get_bridge()
        bridge.sync_tweets(tweets)


def notify_classification_if_web_mode(classified: List[Dict]) -> None:
    """Notify web UI of classifications if in web mode"""
    if os.getenv("WDF_WEB_MODE", "false").lower() == "true":
        bridge = get_bridge()
        bridge.notify_tweets_classified(classified)


def create_draft_if_web_mode(tweet_id: str, response: str, model: str) -> Optional[int]:
    """Create draft in web UI if in web mode"""
    if os.getenv("WDF_WEB_MODE", "false").lower() == "true":
        bridge = get_bridge()
        return bridge.create_draft(tweet_id, response, model)
    return None


def sync_responses_to_database(responses_file: str, episode_dir: str = None) -> int:
    """
    Sync responses from Claude pipeline JSON file to database as drafts.
    
    IMPORTANT: This function cleans up old pending drafts before creating new ones
    to prevent accumulation of unused responses.
    
    Args:
        responses_file: Path to the responses.json file
        episode_dir: Episode directory name for logging
        
    Returns:
        Number of drafts created
    """
    bridge = get_bridge()
    created_count = 0
    
    try:
        # Load responses from file
        import json
        from pathlib import Path
        
        responses_path = Path(responses_file)
        if not responses_path.exists():
            logger.warning(f"Responses file not found: {responses_file}")
            return 0
            
        with open(responses_path, 'r') as f:
            responses = json.load(f)
            
        if not responses:
            logger.info("No responses to sync")
            return 0
            
        logger.info(f"Syncing {len(responses)} responses to database from {episode_dir or 'unknown episode'}")
        
        # First, clean up ALL old pending drafts for these tweets
        # This prevents accumulation across multiple response generation runs
        tweet_ids = [r.get('id', r.get('twitter_id', r.get('tweet_id'))) for r in responses if r.get('response')]
        
        if tweet_ids:
            with bridge.connection.cursor() as cursor:
                # Get database tweet IDs for these twitter IDs
                placeholders = ','.join(['%s'] * len(tweet_ids))
                cursor.execute(f"""
                    SELECT id, twitter_id FROM tweets 
                    WHERE twitter_id IN ({placeholders})
                """, tweet_ids)
                
                tweet_mapping = {row[1]: row[0] for row in cursor.fetchall()}
                
                if tweet_mapping:
                    # Delete ALL pending drafts for these tweets
                    db_tweet_ids = list(tweet_mapping.values())
                    placeholders = ','.join(['%s'] * len(db_tweet_ids))
                    cursor.execute(f"""
                        DELETE FROM draft_replies 
                        WHERE tweet_id IN ({placeholders}) AND status = 'pending'
                    """, db_tweet_ids)
                    
                    deleted_count = cursor.rowcount
                    if deleted_count > 0:
                        logger.info(f"Cleaned up {deleted_count} old pending drafts before syncing new responses")
                    
                bridge.connection.commit()
        
        # Now create new drafts for each response
        for item in responses:
            # Skip items without responses
            if not item.get('response'):
                continue
                
            # Get tweet ID (handle different field names)
            tweet_id = item.get('id', item.get('twitter_id', item.get('tweet_id')))
            if not tweet_id:
                logger.warning(f"No tweet ID found in response item: {item}")
                continue
                
            # Get response text and model
            response_text = item['response']
            model_name = item.get('model', item.get('response_method', 'claude'))
            
            # Skip placeholder responses
            if '[Skipped' in response_text or not response_text.strip():
                continue
                
            try:
                # Create draft (this now skips tweets with approved/posted/scheduled drafts)
                draft_id = bridge.create_draft(tweet_id, response_text, model_name)
                if draft_id > 0:  # Only count actual creations (0 means skipped)
                    created_count += 1
                    logger.debug(f"Created draft {draft_id} for tweet {tweet_id}")
                elif draft_id == 0:
                    logger.debug(f"Skipped tweet {tweet_id} - already has approved/posted/scheduled draft")
            except Exception as e:
                logger.error(f"Failed to create draft for tweet {tweet_id}: {e}")
                continue
                
        logger.info(f"Successfully synced {created_count} responses to database as drafts")
        
        # Emit SSE event for UI update
        if created_count > 0:
            bridge.emit_sse_event({
                "type": "responses_synced",
                "count": created_count,
                "episode_dir": episode_dir
            })
        
        return created_count
        
    except Exception as e:
        logger.error(f"Failed to sync responses to database: {e}")
        return 0


def get_keywords_if_web_mode(episode_id: Optional[str] = None) -> Optional[List[str]]:
    """Get enabled keywords from database if in web mode
    
    Args:
        episode_id: Optional episode ID to fetch episode-specific keywords
        
    Returns:
        List of keyword strings if in web mode, None otherwise
    """
    if os.getenv("WDF_WEB_MODE", "false").lower() == "true":
        bridge = get_bridge()
        keywords = bridge.get_enabled_keywords(episode_id)
        # Convert to simple list of strings
        return [kw['keyword'] for kw in keywords]
    return None


def get_api_keys_if_web_mode() -> Optional[Dict[str, Dict[str, str]]]:
    """Get API keys from web UI if in web mode
    
    Returns:
        Dictionary of API keys by service if in web mode, None otherwise
    """
    if os.getenv("WDF_WEB_MODE", "false").lower() == "true":
        bridge = get_bridge()
        return bridge.get_api_keys()
    return None


# Claude Pipeline Integration Functions

def is_claude_pipeline_enabled() -> bool:
    """Check if Claude pipeline is enabled"""
    return os.getenv("WDF_USE_CLAUDE_PIPELINE", "false").lower() == "true"


def get_claude_episode_context(episode_id: int, context_type: str = None, 
                               claude_mode: str = None) -> Optional[str]:
    """Get Claude episode context from database if available
    
    Args:
        episode_id: Episode ID
        context_type: Optional context type filter
        claude_mode: Optional Claude mode filter
        
    Returns:
        Episode context string if available, None otherwise
    """
    if os.getenv("WDF_WEB_MODE", "false").lower() == "true":
        bridge = get_bridge()
        return bridge.get_episode_context(episode_id, context_type, claude_mode)
    return None


def save_claude_episode_context(episode_id: int, context_type: str,
                                context_content: str, claude_mode: str = None) -> None:
    """Save Claude episode context to database if in web mode
    
    Args:
        episode_id: Episode ID
        context_type: Type of context (e.g., 'episode_specific', 'specialized')
        context_content: The context content to save
        claude_mode: Optional Claude mode (e.g., 'summarize', 'classify')
    """
    if os.getenv("WDF_WEB_MODE", "false").lower() == "true":
        bridge = get_bridge()
        bridge.save_episode_context(episode_id, context_type, context_content, claude_mode)


def update_claude_pipeline_status(episode_id: int, status: str) -> None:
    """Update Claude pipeline status if in web mode
    
    Args:
        episode_id: Episode ID
        status: Pipeline status (e.g., 'summarizing', 'classifying', 'completed')
    """
    if os.getenv("WDF_WEB_MODE", "false").lower() == "true":
        bridge = get_bridge()
        bridge.update_claude_pipeline_status(episode_id, status)


def track_claude_costs(costs: Dict[str, float]) -> None:
    """Track Claude API costs if in web mode
    
    Args:
        costs: Dictionary mapping mode to cost (e.g., {'summarize': 0.15, 'classify': 0.08})
    """
    if os.getenv("WDF_WEB_MODE", "false").lower() == "true":
        bridge = get_bridge()
        bridge.track_claude_costs(costs)


def get_claude_costs_summary(days: int = 30) -> Optional[Dict[str, Any]]:
    """Get Claude costs summary if in web mode
    
    Args:
        days: Number of days to include in summary
        
    Returns:
        Cost summary dict if in web mode, None otherwise
    """
    if os.getenv("WDF_WEB_MODE", "false").lower() == "true":
        bridge = get_bridge()
        return bridge.get_claude_costs_summary(days)
    return None


def load_episode_config(episode_id: Union[int, str]) -> Optional[Dict]:
    """Load episode configuration from database if in web mode
    
    Args:
        episode_id: Episode ID
        
    Returns:
        Episode config dict if available, None otherwise
    """
    if os.getenv("WDF_WEB_MODE", "false").lower() == "true":
        bridge = get_bridge()
        episode = bridge.get_episode(int(episode_id))
        if episode:
            return {
                'episode_id': episode['id'],
                'episode_dir': episode.get('episode_dir'),
                'claude_episode_dir': episode.get('claude_episode_dir'),
                'pipeline_type': episode.get('pipeline_type', 'legacy'),
                'claude_status': episode.get('claude_pipeline_status'),
                'transcript': episode.get('transcript_text'),
                'summary': episode.get('summary_text'),
                'video_url': episode.get('video_url')
            }
    return None