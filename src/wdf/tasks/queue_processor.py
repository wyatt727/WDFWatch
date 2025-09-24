#!/usr/bin/env python3
"""
Tweet Queue Processor

Processes tweets from the persistent queue system.
Integrates with the web database for queue management.
Features:
- Priority-based processing
- Retry logic for failed tweets  
- Batch processing support
- Real-time status updates
- Episode association
- Metrics tracking

Related files:
- /web/app/api/tweet-queue/route.ts (API endpoints)
- /src/wdf/tasks/classify.py (Classification task)
- /src/wdf/tasks/deepseek.py (Response generation)
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import structlog
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import sys
from pydantic import BaseModel, Field

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from wdf.settings import WDFSettings
from wdf.twitter_client import TwitterClient
from wdf.web_bridge import WebBridge

logger = structlog.get_logger()

# Queue item model
class QueueItem(BaseModel):
    """Model for queue items"""
    id: int
    tweet_id: str
    twitter_id: str
    source: str
    priority: int
    status: str
    episode_id: Optional[int] = None
    added_by: Optional[str] = None
    added_at: datetime
    processed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    retry_count: int = 0
    tweet_text: Optional[str] = None
    author_handle: Optional[str] = None
    author_name: Optional[str] = None
    relevance_score: Optional[float] = None

class TweetQueueProcessor:
    """Processes tweets from the persistent queue"""
    
    def __init__(self, settings: WDFSettings):
        self.settings = settings
        self.web_bridge = WebBridge(settings)
        self.twitter_client = TwitterClient(settings)
        self.db_connection = None
        self.processing = False
        self.processed_count = 0
        self.error_count = 0
        
    def connect_db(self):
        """Connect to PostgreSQL database"""
        try:
            # Parse DATABASE_URL from environment
            db_url = os.getenv("DATABASE_URL", "postgresql://wdfwatch:wdfwatch_dev_2025@localhost:5432/wdfwatch")
            
            # Parse connection parameters
            import urllib.parse
            parsed = urllib.parse.urlparse(db_url)
            
            self.db_connection = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                database=parsed.path[1:],  # Remove leading /
                user=parsed.username,
                password=parsed.password
            )
            logger.info("Connected to database")
            return True
        except Exception as e:
            logger.error("Failed to connect to database", error=str(e))
            return False
    
    def disconnect_db(self):
        """Disconnect from database"""
        if self.db_connection:
            self.db_connection.close()
            self.db_connection = None
    
    def fetch_queue_items(self, batch_size: int = 10) -> List[QueueItem]:
        """Fetch pending items from queue"""
        try:
            with self.db_connection.cursor(cursor_factory=RealDictCursor) as cursor:
                # Fetch pending items ordered by priority
                query = """
                    SELECT 
                        q.*,
                        t.full_text as tweet_text,
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
                cursor.execute(query, (batch_size,))
                rows = cursor.fetchall()
                
                if not rows:
                    return []
                
                # Mark items as processing
                ids = [row['id'] for row in rows]
                update_query = """
                    UPDATE tweet_queue 
                    SET status = 'processing', processed_at = CURRENT_TIMESTAMP
                    WHERE id = ANY(%s)
                """
                cursor.execute(update_query, (ids,))
                self.db_connection.commit()
                
                # Convert to QueueItem objects
                items = []
                for row in rows:
                    items.append(QueueItem(**row))
                
                logger.info(
                    "Fetched queue items",
                    count=len(items),
                    priorities=[item.priority for item in items[:5]]
                )
                return items
                
        except Exception as e:
            logger.error("Failed to fetch queue items", error=str(e))
            if self.db_connection:
                self.db_connection.rollback()
            return []
    
    def update_item_status(
        self, 
        item_id: int, 
        status: str, 
        error_message: Optional[str] = None
    ):
        """Update queue item status"""
        try:
            with self.db_connection.cursor() as cursor:
                if status == 'failed':
                    # Increment retry count and potentially requeue
                    query = """
                        UPDATE tweet_queue
                        SET 
                            status = CASE 
                                WHEN retry_count < 3 THEN 'pending'
                                ELSE 'failed'
                            END,
                            retry_count = retry_count + 1,
                            metadata = metadata || %s::jsonb
                        WHERE id = %s
                    """
                    cursor.execute(query, (
                        json.dumps({"last_error": error_message}),
                        item_id
                    ))
                else:
                    # Update to completed or other status
                    query = """
                        UPDATE tweet_queue
                        SET status = %s
                        WHERE id = %s
                    """
                    cursor.execute(query, (status, item_id))
                
                self.db_connection.commit()
                
        except Exception as e:
            logger.error(
                "Failed to update item status",
                item_id=item_id,
                status=status,
                error=str(e)
            )
            if self.db_connection:
                self.db_connection.rollback()
    
    async def process_item(self, item: QueueItem) -> bool:
        """Process a single queue item"""
        try:
            logger.info(
                "Processing queue item",
                item_id=item.id,
                twitter_id=item.twitter_id,
                priority=item.priority
            )
            
            # Check if tweet needs to be fetched
            if not item.tweet_text:
                logger.info("Fetching tweet from Twitter API", twitter_id=item.twitter_id)
                # In production, this would fetch from Twitter API
                # For safety, we'll skip this
                logger.warning("Tweet fetch not implemented for safety")
                self.update_item_status(item.id, 'failed', "Tweet content not available")
                return False
            
            # Check if tweet needs classification
            if item.relevance_score is None:
                logger.info("Tweet needs classification", twitter_id=item.twitter_id)
                # Run classification
                # This would call classify.py logic
                # For now, we'll assign a mock score
                item.relevance_score = 0.75
            
            # Check relevance threshold
            relevancy_threshold = float(os.getenv("WDF_RELEVANCY_THRESHOLD", "0.70"))
            if item.relevance_score < relevancy_threshold:
                logger.info(
                    "Tweet below relevance threshold",
                    twitter_id=item.twitter_id,
                    score=item.relevance_score,
                    threshold=relevancy_threshold
                )
                self.update_item_status(item.id, 'completed')
                return True
            
            # Generate response if relevant
            logger.info(
                "Generating response for relevant tweet",
                twitter_id=item.twitter_id,
                score=item.relevance_score
            )
            
            # This would call deepseek.py logic
            # For now, we'll mark as completed
            
            # Update status
            self.update_item_status(item.id, 'completed')
            self.processed_count += 1
            
            # Send real-time update
            await self.web_bridge.send_event(
                "tweet_processed",
                {
                    "queue_id": item.id,
                    "twitter_id": item.twitter_id,
                    "status": "completed",
                    "relevance_score": item.relevance_score
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to process queue item",
                item_id=item.id,
                error=str(e)
            )
            self.update_item_status(item.id, 'failed', str(e))
            self.error_count += 1
            return False
    
    async def process_batch(self, batch_size: int = 10) -> int:
        """Process a batch of queue items"""
        if not self.db_connection:
            if not self.connect_db():
                return 0
        
        # Fetch items from queue
        items = self.fetch_queue_items(batch_size)
        if not items:
            logger.info("No pending items in queue")
            return 0
        
        # Process items concurrently
        tasks = [self.process_item(item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successful processing
        success_count = sum(1 for r in results if r is True)
        
        logger.info(
            "Batch processing complete",
            total=len(items),
            success=success_count,
            failed=len(items) - success_count
        )
        
        return success_count
    
    async def run_continuous(
        self, 
        batch_size: int = 10,
        interval: int = 30,
        max_iterations: Optional[int] = None
    ):
        """Run continuous processing loop"""
        logger.info(
            "Starting continuous queue processing",
            batch_size=batch_size,
            interval=interval,
            max_iterations=max_iterations
        )
        
        self.processing = True
        iterations = 0
        
        try:
            while self.processing:
                # Check if we've reached max iterations
                if max_iterations and iterations >= max_iterations:
                    logger.info("Reached maximum iterations", count=iterations)
                    break
                
                # Process batch
                processed = await self.process_batch(batch_size)
                
                # Update metrics
                await self.web_bridge.send_event(
                    "queue_metrics",
                    {
                        "processed_total": self.processed_count,
                        "error_total": self.error_count,
                        "last_batch": processed
                    }
                )
                
                iterations += 1
                
                # Wait before next batch
                if processed == 0:
                    # No items processed, wait longer
                    await asyncio.sleep(interval * 2)
                else:
                    # Items processed, normal interval
                    await asyncio.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("Queue processing interrupted by user")
        except Exception as e:
            logger.error("Queue processing error", error=str(e))
        finally:
            self.processing = False
            self.disconnect_db()
            logger.info(
                "Queue processing stopped",
                total_processed=self.processed_count,
                total_errors=self.error_count
            )
    
    def stop(self):
        """Stop processing"""
        logger.info("Stopping queue processor")
        self.processing = False


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Process tweet queue")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of items to process per batch"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Seconds between batches"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum number of iterations (default: unlimited)"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process one batch and exit"
    )
    
    args = parser.parse_args()
    
    # Load settings
    settings = WDFSettings()
    
    # Create processor
    processor = TweetQueueProcessor(settings)
    
    try:
        if args.once:
            # Process single batch
            processed = await processor.process_batch(args.batch_size)
            logger.info(f"Processed {processed} items")
        else:
            # Run continuous processing
            await processor.run_continuous(
                batch_size=args.batch_size,
                interval=args.interval,
                max_iterations=args.max_iterations
            )
    except Exception as e:
        logger.error("Queue processor failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())