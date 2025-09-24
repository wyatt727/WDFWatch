"""
Web UI moderation task

This module handles the human-in-the-loop approval workflow for the web UI.
Instead of using a CLI interface, it monitors the database for approved drafts
and publishes them to Twitter.

Integrates with: web/scripts/web_bridge.py, Twitter API
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional
import time

import structlog
from prometheus_client import Counter, Histogram

from ..settings import settings
from ..twitter_client import get_twitter_client

# Import web bridge for database operations
try:
    web_scripts_path = Path(__file__).parent.parent.parent.parent / "web" / "scripts"
    sys.path.insert(0, str(web_scripts_path))
    from web_bridge import WebUIBridge
    logger_import = structlog.get_logger()
    logger_import.debug("Web bridge imported successfully")
except ImportError:
    logger_import = structlog.get_logger()
    logger_import.error("Web bridge not available - web moderation requires web UI")
    raise ImportError("Web moderation requires web UI bridge module")

# Set up structured logging
logger = structlog.get_logger()

# Prometheus metrics
MODERATION_LATENCY = Histogram(
    "web_moderation_latency_seconds", 
    "Time taken to check and publish approved drafts",
    ["run_id"],
    buckets=[1, 5, 10, 30, 60]
)
DRAFTS_PUBLISHED = Counter(
    "drafts_published_total",
    "Number of drafts published"
)
MODERATION_ERRORS = Counter(
    "web_moderation_errors_total",
    "Number of errors during web moderation"
)


def get_approved_drafts(bridge: WebUIBridge) -> List[Dict]:
    """
    Get approved drafts from the database that haven't been published yet
    
    Args:
        bridge: WebUIBridge instance
        
    Returns:
        List of approved drafts with tweet information
    """
    try:
        with bridge.connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    dr.id as draft_id,
                    dr.text as response,
                    dr.final_text,
                    t.twitter_id,
                    t.full_text as tweet_text,
                    t.author_handle
                FROM draft_replies dr
                JOIN tweets t ON dr.tweet_id = t.id
                WHERE dr.status = 'approved'
                AND t.status != 'posted'
                ORDER BY dr.updated_at ASC
                LIMIT 50
            """)
            
            columns = [desc[0] for desc in cursor.description]
            drafts = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
        logger.info(f"Found {len(drafts)} approved drafts to publish")
        return drafts
        
    except Exception as e:
        logger.error(f"Failed to get approved drafts: {e}")
        raise


def publish_draft(draft: Dict, bridge: WebUIBridge) -> bool:
    """
    Publish an approved draft as a Twitter reply
    
    Args:
        draft: Draft dictionary with tweet and response information
        bridge: WebUIBridge instance
        
    Returns:
        True if published successfully, False otherwise
    """
    twitter_client = get_twitter_client()
    
    # Use final_text if available (user edited), otherwise use original response
    response_text = draft.get('final_text') or draft.get('response')
    
    try:
        # Publish the reply
        success = twitter_client.reply_to_tweet(
            tweet_id=draft['twitter_id'],
            reply_text=response_text
        )
        
        if success:
            # Update database to mark as posted
            with bridge.connection.cursor() as cursor:
                # Update tweet status
                cursor.execute("""
                    UPDATE tweets 
                    SET status = 'posted' 
                    WHERE twitter_id = %s
                """, (draft['twitter_id'],))
                
                # Update draft status
                cursor.execute("""
                    UPDATE draft_replies 
                    SET status = 'posted' 
                    WHERE id = %s
                """, (draft['draft_id'],))
                
                # Create audit log entry
                cursor.execute("""
                    INSERT INTO audit_logs (
                        action, entity_type, entity_id, 
                        details, created_at
                    ) VALUES (
                        'draft_posted', 'draft_reply', %s,
                        %s, CURRENT_TIMESTAMP
                    )
                """, (
                    draft['draft_id'],
                    json.dumps({
                        'tweet_id': draft['twitter_id'],
                        'response': response_text,
                        'automated': True
                    })
                ))
                
                bridge.connection.commit()
                
            # Emit SSE event
            bridge.emit_sse_event({
                "type": "tweet_status",
                "tweetId": draft['twitter_id'],
                "newStatus": "posted"
            })
            
            logger.info(
                "Published draft successfully",
                draft_id=draft['draft_id'],
                tweet_id=draft['twitter_id']
            )
            DRAFTS_PUBLISHED.inc()
            return True
            
        else:
            logger.error(
                "Failed to publish draft",
                draft_id=draft['draft_id'],
                tweet_id=draft['twitter_id']
            )
            return False
            
    except Exception as e:
        bridge.connection.rollback()
        logger.error(
            "Error publishing draft",
            draft_id=draft['draft_id'],
            tweet_id=draft['twitter_id'],
            error=str(e)
        )
        MODERATION_ERRORS.inc()
        return False


def run(run_id: Optional[str] = None, poll_interval: int = 30, max_iterations: int = 10) -> Path:
    """
    Monitor for approved drafts and publish them to Twitter
    
    Args:
        run_id: Optional run ID for tracking
        poll_interval: Seconds between database checks (default: 30)
        max_iterations: Maximum number of polling iterations (default: 10)
        
    Returns:
        Path to the published results file
    """
    start_time = time.time()
    
    logger.info(
        "Starting web moderation task",
        run_id=run_id,
        poll_interval=poll_interval,
        max_iterations=max_iterations
    )
    
    # Get bridge instance
    bridge = WebUIBridge()
    
    # Track published drafts
    published_drafts = []
    
    try:
        # Poll for approved drafts
        for iteration in range(max_iterations):
            logger.info(f"Polling iteration {iteration + 1}/{max_iterations}")
            
            # Get approved drafts
            approved_drafts = get_approved_drafts(bridge)
            
            if approved_drafts:
                logger.info(f"Processing {len(approved_drafts)} approved drafts")
                
                # Publish each draft
                for draft in approved_drafts:
                    if publish_draft(draft, bridge):
                        published_drafts.append({
                            'draft_id': draft['draft_id'],
                            'tweet_id': draft['twitter_id'],
                            'response': draft.get('final_text') or draft.get('response'),
                            'published_at': time.time()
                        })
                    
                    # Rate limiting between posts
                    time.sleep(2)
            else:
                logger.info("No approved drafts found")
            
            # Sleep before next iteration (unless it's the last one)
            if iteration < max_iterations - 1:
                time.sleep(poll_interval)
    
    finally:
        bridge.close()
    
    # Write published drafts to file
    published_path = Path(settings.transcript_dir) / "published.json"
    with open(published_path, "w") as f:
        json.dump(published_drafts, f, indent=2)
    
    # Copy to artefacts directory if run_id is provided
    if run_id:
        artefact_dir = settings.get_run_dir(run_id)
        artefact_published = artefact_dir / "published.json"
        artefact_published.write_text(published_path.read_text())
        
        logger.info(
            "Copied published drafts to artefacts directory",
            path=str(artefact_published)
        )
    
    elapsed_time = time.time() - start_time
    MODERATION_LATENCY.labels(run_id=run_id or "unknown").observe(elapsed_time)
    
    logger.info(
        "Web moderation completed",
        published_count=len(published_drafts),
        elapsed_time=elapsed_time
    )
    
    return published_path


if __name__ == "__main__":
    # Configure logging when run directly
    logging.basicConfig(level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )
    
    # Run the moderation task
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", help="Run ID for tracking")
    parser.add_argument("--poll-interval", type=int, default=30, help="Seconds between polls")
    parser.add_argument("--max-iterations", type=int, default=10, help="Maximum polling iterations")
    args = parser.parse_args()
    
    published_path = run(
        run_id=args.run_id,
        poll_interval=args.poll_interval,
        max_iterations=args.max_iterations
    )
    print(f"Published drafts saved to: {published_path}")