"""
Performance profiling utilities for pipeline stages.
"""

import functools
import logging
import time
from typing import Dict, Any, Callable

from app.services.events import events_service

logger = logging.getLogger(__name__)


def time_execution(func: Callable) -> Callable:
    """
    Decorator to time function execution and log performance metrics.
    
    Usage:
        @time_execution
        def my_function():
            # Function implementation
            pass
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            elapsed_time = time.time() - start_time
            
            # Log performance metrics
            logger.info(
                f"Function {func.__name__} completed in {elapsed_time:.2f}s",
                extra={
                    "function": func.__name__,
                    "duration_seconds": elapsed_time,
                    "duration_minutes": elapsed_time / 60,
                }
            )
            
            # Emit performance event if in job context
            try:
                from rq import get_current_job
                job = get_current_job()
                if job:
                    events_service.publish_job_event(
                        job_id=job.id,
                        status="running",
                        message=f"{func.__name__} completed",
                        data={
                            "duration_seconds": elapsed_time,
                            "function": func.__name__,
                        },
                    )
            except Exception:
                pass  # Not in job context, skip event
            
            return result
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(
                f"Function {func.__name__} failed after {elapsed_time:.2f}s",
                exc_info=True,
                extra={
                    "function": func.__name__,
                    "duration_seconds": elapsed_time,
                    "error": str(e),
                }
            )
            raise
    
    return wrapper


def get_performance_metrics() -> Dict[str, Any]:
    """
    Get current performance metrics.
    
    Returns:
        Dictionary with performance metrics
    """
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    
    return {
        "cpu_percent": process.cpu_percent(interval=0.1),
        "memory_mb": process.memory_info().rss / 1024 / 1024,
        "memory_percent": process.memory_percent(),
        "threads": process.num_threads(),
    }

