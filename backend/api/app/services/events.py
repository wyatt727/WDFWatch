"""
Event publishing service using Redis pub/sub.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from app.config import settings
from app.services.queue import get_redis_connection

logger = logging.getLogger(__name__)


class EventsService:
    """Service for publishing events to Redis pub/sub."""
    
    def __init__(self):
        """Initialize events service."""
        self.redis = get_redis_connection()
        self.channel_prefix = "wdfwatch:events"
    
    def publish(self, event_type: str, data: Dict[str, Any], channel: Optional[str] = None):
        """
        Publish event to Redis pub/sub.
        
        Args:
            event_type: Event type (e.g., 'pipeline.started', 'pipeline.completed')
            data: Event data
            channel: Optional channel name (defaults to event_type)
        """
        if channel is None:
            channel = f"{self.channel_prefix}:{event_type}"
        
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        try:
            self.redis.publish(channel, json.dumps(event))
            logger.debug(f"Published event: {event_type} to {channel}")
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
    
    def publish_pipeline_event(
        self,
        episode_id: str,
        stage: str,
        status: str,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        errors: Optional[list[str]] = None,
        items_processed: Optional[int] = None,
        items_total: Optional[int] = None,
    ):
        """
        Publish pipeline-specific event with structured progress.
        
        Args:
            episode_id: Episode identifier
            stage: Stage name
            status: Stage status (started, running, completed, failed)
            progress: Overall progress percentage (0-100)
            message: Optional message
            errors: Optional list of errors
            items_processed: Number of items processed so far
            items_total: Total number of items to process
        """
        # Calculate progress percentage if items are provided
        if items_processed is not None and items_total is not None and items_total > 0:
            calculated_progress = (items_processed / items_total) * 100
            if progress is None:
                progress = calculated_progress
        
        self.publish(
            f"pipeline.{status}",
            {
                "episode_id": episode_id,
                "stage": stage,
                "progress": progress,
                "message": message,
                "errors": errors,
                "items_processed": items_processed,
                "items_total": items_total,
                "percentage": progress,
            },
            channel=f"{self.channel_prefix}:episode:{episode_id}",
        )
    
    def publish_job_event(
        self,
        job_id: str,
        status: str,
        progress: Optional[float] = None,
        message: Optional[str] = None,
    ):
        """Publish job-specific event."""
        self.publish(
            f"job.{status}",
            {
                "job_id": job_id,
                "progress": progress,
                "message": message,
            },
            channel=f"{self.channel_prefix}:job:{job_id}",
        )

    def publish_queue_event(
        self,
        queue_id: int,
        status: str,
        *,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Publish queue-specific events for UI consumption."""
        self.publish(
            f"queue.{status}",
            {
                "queue_id": queue_id,
                "status": status,
                "message": message,
                "metadata": metadata or {},
            },
            channel=f"{self.channel_prefix}:queue",
        )


# Global instance
events_service = EventsService()

