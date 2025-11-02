"""
Retry configuration and utilities for RQ jobs.
Provides exponential backoff retry logic.
"""

import logging
from typing import Dict, Any, Optional

from app.config import settings
from app.services.events import events_service
from rq import get_current_job

logger = logging.getLogger(__name__)


def calculate_retry_delay(attempt: int) -> int:
    """
    Calculate retry delay using exponential backoff.
    
    Args:
        attempt: Current retry attempt (0-indexed)
        
    Returns:
        Delay in seconds
    """
    base_delay = settings.JOB_RETRY_DELAY
    backoff_multiplier = settings.JOB_RETRY_BACKOFF
    
    delay = int(base_delay * (backoff_multiplier ** attempt))
    
    # Cap at 1 hour
    max_delay = 3600
    return min(delay, max_delay)


def get_retry_metadata() -> Dict[str, Any]:
    """
    Get retry metadata from current job.
    
    Returns:
        Dictionary with retry information
    """
    job = get_current_job()
    if not job:
        return {
            "retry_count": 0,
            "max_retries": settings.JOB_MAX_RETRIES,
            "next_retry_delay": None,
        }
    
    retry_count = getattr(job, "retry_count", 0) or 0
    
    return {
        "retry_count": retry_count,
        "max_retries": settings.JOB_MAX_RETRIES,
        "next_retry_delay": calculate_retry_delay(retry_count) if retry_count < settings.JOB_MAX_RETRIES else None,
        "job_id": job.id,
    }


def get_retry_config() -> Dict[str, Any]:
    """
    Get retry configuration for RQ jobs.
    
    Returns:
        Dictionary with retry configuration
    """
    return {
        "max": settings.JOB_MAX_RETRIES,
        "interval": [
            calculate_retry_delay(i) for i in range(settings.JOB_MAX_RETRIES)
        ],
    }


def enqueue_with_retries(
    queue,
    func,
    *args,
    retry: Optional[Dict[str, Any]] = None,
    **kwargs
):
    """
    Enqueue a job with retry configuration.
    
    Args:
        queue: RQ queue instance
        func: Function to enqueue
        *args: Function arguments
        retry: Optional retry configuration dict
        **kwargs: Additional job parameters
        
    Returns:
        Enqueued job
    """
    if retry is None:
        retry = get_retry_config()
    
    return queue.enqueue(
        func,
        *args,
        retry=retry,
        **kwargs
    )


def handle_job_failure(job_id: str, exception: Exception, retry_count: int):
    """
    Handle job failure and publish retry event.
    
    Args:
        job_id: Job identifier
        exception: The exception that occurred
        retry_count: Current retry count
    """
    if retry_count < settings.JOB_MAX_RETRIES:
        retry_delay = calculate_retry_delay(retry_count)
        events_service.publish_job_event(
            job_id=job_id,
            status="retrying",
            message=f"Retrying after {retry_delay}s (attempt {retry_count + 1}/{settings.JOB_MAX_RETRIES + 1})",
            data={
                "retry_count": retry_count + 1,
                "max_retries": settings.JOB_MAX_RETRIES,
                "retry_delay": retry_delay,
                "error": str(exception),
            },
        )
    else:
        events_service.publish_job_event(
            job_id=job_id,
            status="failed",
            message=f"Job failed after {retry_count + 1} attempts: {exception}",
            data={
                "retry_count": retry_count + 1,
                "max_retries": settings.JOB_MAX_RETRIES,
                "final_error": str(exception),
            },
        )

